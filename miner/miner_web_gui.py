import json
import os
import socket
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

try:
    from miner.gpu_check import check_gpu
except Exception:
    try:
        from gpu_check import check_gpu
    except Exception:
        def check_gpu():
            raise RuntimeError("CUDA check unavailable")

app = Flask(__name__)
POOL_HOST = os.environ.get("MPA_POOL_HOST", "127.0.0.1")
POOL_PORT = int(os.environ.get("MPA_POOL_PORT", "3333"))
MINER_ID = f"web-miner-{os.getpid()}"

state = {
    "running": False,
    "gpu_name": "unknown",
    "hashrate": 0,
    "shares": 0,
    "accepted": 0,
    "rejected": 0,
    "started_at": None,
    "error": "",
    "simulation_mode": False,
    "wallet": "MY_WALLET",
}

_lock = threading.Lock()


def _resolve_mining_device():
    info = check_gpu()
    if isinstance(info, tuple) and len(info) >= 1:
        return str(info[0]), False
    return str(info), False


def _submit_share(wallet: str) -> bool:
    msg = {"method": "submit", "miner_id": MINER_ID, "wallet": wallet}
    with socket.create_connection((POOL_HOST, POOL_PORT), timeout=1.0) as s:
        s.send(json.dumps(msg).encode())
        resp = json.loads(s.recv(4096).decode())
    return resp.get("result") == "accepted"


def miner_loop():
    while True:
        with _lock:
            if not state["running"]:
                break
            wallet = state["wallet"]
            sim = state["simulation_mode"]
            state["hashrate"] = 8 + int(time.time()) % 5 if sim else 120 + int(time.time()) % 30
            state["shares"] += 1
        try:
            ok = _submit_share(wallet)
            with _lock:
                if ok:
                    state["accepted"] += 1
                    state["error"] = ""
                else:
                    state["rejected"] += 1
                    state["error"] = "Pool rejected share"
        except Exception as exc:
            with _lock:
                state["rejected"] += 1
                state["error"] = f"Pool connection error: {exc}"
        time.sleep(0.5)


def start_mining():
    try:
        gpu_name, simulation = _resolve_mining_device()
        error = ""
    except RuntimeError as exc:
        gpu_name, simulation = "not available (CPU sim)", True
        error = f"{exc}. Running in CPU simulation mode."
    except Exception as exc:
        gpu_name, simulation = "error (CPU sim)", True
        error = f"Unexpected GPU check error: {exc}. Running in CPU simulation mode."

    with _lock:
        state["gpu_name"] = gpu_name
        state["simulation_mode"] = simulation
        if error:
            state["error"] = error
        if state["running"]:
            return True, gpu_name
        state["running"] = True
        state["started_at"] = time.time()
    threading.Thread(target=miner_loop, daemon=True).start()
    return True, gpu_name


def stop_mining():
    with _lock:
        state["running"] = False


TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Miner Web GUI</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    .container { max-width: 760px; margin: 0 auto; padding: 20px; }
    .panel { background:#111827; border-radius: 12px; padding: 16px; margin-bottom: 14px; }
    .ok { color:#34d399; }
    .stop { color:#f87171; }
    .err { color:#fca5a5; margin-top: 8px; }
    .row { display:flex; gap:14px; flex-wrap: wrap; }
    .metric { background:#1f2937; border-radius:10px; padding:12px; min-width: 160px; }
    .metric .k { color:#93c5fd; font-size: 13px; }
    .metric .v { font-size: 24px; font-weight: bold; }
    input { width:100%; padding:10px; border-radius:8px; border:1px solid #334155; background:#0b1220; color:#e2e8f0; }
    button { border:0; padding:10px 14px; border-radius:8px; cursor:pointer; font-weight:bold; margin-top:8px; }
    .start { background:#10b981; color:white; }
    .stopbtn { background:#ef4444; color:white; }
    .save { background:#2563eb; color:white; }
    a { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Miner Web GUI</h1>
    <p><a href="/api/miner">JSON API</a></p>

    <div class="panel">
      <form method="post" action="/set_wallet">
        <strong>Wallet address for rewards:</strong>
        <input name="wallet" value="{{ wallet }}" />
        <button class="save" type="submit">Save wallet</button>
      </form>
    </div>

    <div class="panel">
      <strong>Status:</strong>
      <span class="{{ 'ok' if running else 'stop' }}">{{ 'RUNNING' if running else 'STOPPED' }}</span><br/>
      <strong>Device:</strong> {{ gpu_name }}<br/>
      <strong>Pool:</strong> {{ pool_host }}:{{ pool_port }}
      {% if simulation_mode %}<div class="err">CPU simulation mode enabled</div>{% endif %}
      {% if error %}<div class="err">{{ error }}</div>{% endif %}
    </div>

    <div class="row">
      <div class="metric"><div class="k">Hashrate</div><div class="v">{{ hashrate }} MH/s</div></div>
      <div class="metric"><div class="k">Shares</div><div class="v">{{ shares }}</div></div>
      <div class="metric"><div class="k">Accepted</div><div class="v">{{ accepted }}</div></div>
      <div class="metric"><div class="k">Rejected</div><div class="v">{{ rejected }}</div></div>
    </div>

    <div class="panel">
      <form method="post" action="/start" style="display:inline-block">
        <button class="start" type="submit">Start mining</button>
      </form>
      <form method="post" action="/stop" style="display:inline-block">
        <button class="stopbtn" type="submit">Stop mining</button>
      </form>
    </div>
  </div>
  <script>
    setTimeout(() => window.location.reload(), 2000);
  </script>
</body>
</html>
"""


@app.get("/")
def home():
    with _lock:
        data = dict(state)
    data["pool_host"] = POOL_HOST
    data["pool_port"] = POOL_PORT
    return render_template_string(TPL, **data)


@app.post("/set_wallet")
def set_wallet():
    wallet = request.form.get("wallet", "").strip()
    with _lock:
        state["wallet"] = wallet or state["wallet"]
    return redirect(url_for("home"))


@app.post("/start")
def start():
    start_mining()
    return redirect(url_for("home"))


@app.post("/stop")
def stop():
    stop_mining()
    return redirect(url_for("home"))


@app.get("/api/miner")
def api_miner():
    with _lock:
        return jsonify(dict(state))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
