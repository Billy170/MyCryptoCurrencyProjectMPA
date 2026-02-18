import json
import multiprocessing
import os
import socket
import sys
import threading
import time
from urllib.request import Request, urlopen

try:
    import psutil
except Exception:
    psutil = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

from mpa_core.mpa_pow import ALGORITHM_NAME, mpaalg_hash

APP_PORT = int(os.environ.get("MPA_MINER_PORT", "8090"))
POOL_HOST = os.environ.get("MPA_POOL_HOST", "127.0.0.1")
POOL_PORT = int(os.environ.get("MPA_POOL_PORT", "3333"))
MINER_ID = os.environ.get("MPA_MINER_ID", f"web-miner-{os.getpid()}")
POOL_API = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334")
CPU_TARGET_PERCENT = 95

STATE_DIR = os.path.join(PROJECT_ROOT, ".mpa_state")
os.makedirs(STATE_DIR, exist_ok=True)
MINER_STATE_FILE = os.path.join(STATE_DIR, f"miner_{MINER_ID.replace(':', '_')}.json")

app = Flask(__name__)

state = {
    "running": False,
    "mode": "CPU_ONLY",
    "hashrate": 0,
    "shares": 0,
    "accepted": 0,
    "rejected": 0,
    "started_at": None,
    "error": "",
    "wallet": "MY_WALLET",
    "workers": 1,
    "miner_id": MINER_ID,
    "port": APP_PORT,
    "last_seen_block": 0,
    "start_block": 0,
    "cpu_target": CPU_TARGET_PERCENT,
    "algorithm": ALGORITHM_NAME,
    "last_pow": "",
    "cpu_load": 0.0,
    "cpu_temp": "N/A",
}



_lock = threading.Lock()
_cpu_processes = []
_cpu_stop_event = None


def _cpu_mine_worker(stop_event):
    data = os.urandom(32)
    duty_cycle = 0.95
    window = 0.2
    while not stop_event.is_set():
        start = time.time()
        while not stop_event.is_set() and (time.time() - start) < (window * duty_cycle):
            data = __import__("hashlib").sha256(data).digest()
        remaining = (window * (1 - duty_cycle))
        if remaining > 0:
            time.sleep(remaining)


def _calc_cpu_workers() -> int:
    cpu_total = max(1, os.cpu_count() or 1)
    return max(1, int(cpu_total * (CPU_TARGET_PERCENT / 100.0)))


def _start_cpu_workers():
    global _cpu_processes, _cpu_stop_event
    if _cpu_processes:
        return
    workers = _calc_cpu_workers()
    _cpu_stop_event = multiprocessing.Event()
    _cpu_processes = []
    for _ in range(workers):
        p = multiprocessing.Process(target=_cpu_mine_worker, args=(_cpu_stop_event,), daemon=True)
        p.start()
        _cpu_processes.append(p)
    with _lock:
        state["workers"] = workers


def _stop_cpu_workers():
    global _cpu_processes, _cpu_stop_event
    if _cpu_stop_event is not None:
        _cpu_stop_event.set()
    for p in _cpu_processes:
        p.join(timeout=0.5)
        if p.is_alive():
            p.terminate()
    _cpu_processes = []
    _cpu_stop_event = None


def _load_miner_state() -> dict:
    try:
        with open(MINER_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_miner_state():
    with _lock:
        snapshot = {
            "wallet": state.get("wallet", ""),
            "workers": int(state.get("workers", 1)),
            "last_seen_block": int(state.get("last_seen_block", 0)),
        }
    try:
        with open(MINER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f)
    except Exception:
        pass


def _post_sync(last_block: int):
    payload = {"role": "miner", "node_id": MINER_ID, "last_block": int(last_block)}
    req = Request(
        f"{POOL_API}/api/sync",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=1.2):
        pass


def _fetch_chain_height() -> int:
    with urlopen(f"{POOL_API}/api/chain", timeout=1.2) as resp:
        data = json.loads(resp.read().decode())
    return int(data.get("chain_height", 0) or 0)


def _sync_chain_height():
    try:
        h = _fetch_chain_height()
    except Exception:
        return
    with _lock:
        if h >= int(state.get("last_seen_block", 0)):
            state["last_seen_block"] = h
    try:
        _post_sync(h)
    except Exception:
        pass
    _save_miner_state()


def _bootstrap_saved_state():
    saved = _load_miner_state()
    with _lock:
        wallet = str(saved.get("wallet", "")).strip()
        if wallet:
            state["wallet"] = wallet
        try:
            state["last_seen_block"] = max(0, int(saved.get("last_seen_block", 0)))
        except Exception:
            state["last_seen_block"] = 0
        state["start_block"] = state["last_seen_block"]
    if int(state.get("last_seen_block", 0)) > 0:
        try:
            _post_sync(int(state.get("last_seen_block", 0)))
        except Exception:
            pass



def _read_cpu_load() -> float:
    try:
        if psutil is not None:
            return float(psutil.cpu_percent(interval=0.0))
    except Exception:
        pass
    return 0.0


def _read_cpu_temp() -> str:
    try:
        if psutil is not None and hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures() or {}
            for entries in temps.values():
                if entries:
                    val = getattr(entries[0], "current", None)
                    if val is not None:
                        return f"{float(val):.1f}°C"
    except Exception:
        pass
    for path in [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
    ]:
        try:
            raw = open(path, "r", encoding="utf-8").read().strip()
            temp = float(raw)
            if temp > 1000:
                temp = temp / 1000.0
            return f"{temp:.1f}°C"
        except Exception:
            continue
    return "N/A"





def _run_mpaalg_round(workers: int, round_seconds: float = 0.18):
    started = time.time()
    attempts = 0
    best_hash = "f" * 64
    nonce = int(time.time() * 1000)
    header = f"{MINER_ID}:{state.get('last_seen_block', 0)}:{started}"
    while (time.time() - started) < round_seconds:
        for _ in range(max(1, workers)):
            h = mpaalg_hash(header, nonce)
            if h < best_hash:
                best_hash = h
            attempts += 1
            nonce += 1
    elapsed = max(0.001, time.time() - started)
    hps = int(attempts / elapsed)
    return hps, best_hash[:24], nonce


def _submit_share(wallet: str, hashrate: int, pow_nonce: int = 0, pow_hash: str = "", cpu_load: float = 0.0, cpu_temp: str = "N/A") -> bool:
    msg = {"method": "submit", "miner_id": MINER_ID, "wallet": wallet, "hashrate": hashrate, "algo": ALGORITHM_NAME, "pow_nonce": int(pow_nonce), "pow_hash": pow_hash, "cpu_load": float(cpu_load), "cpu_temp": str(cpu_temp)}
    with socket.create_connection((POOL_HOST, POOL_PORT), timeout=6.0) as s:
        s.send(json.dumps(msg).encode())
        s.settimeout(8.0)
        resp = json.loads(s.recv(4096).decode())
    return resp.get("result") == "accepted"


def miner_loop():
    while True:
        with _lock:
            if not state["running"]:
                break
            wallet = state["wallet"]
            workers = max(1, int(state["workers"]))

        current_hashrate, best_pow, nonce = _run_mpaalg_round(workers)

        cpu_load = _read_cpu_load()
        cpu_temp = _read_cpu_temp()

        with _lock:
            state["hashrate"] = current_hashrate
            state["last_pow"] = best_pow
            state["cpu_load"] = cpu_load
            state["cpu_temp"] = cpu_temp

        accepted = 0
        rejected = 0
        for _ in range(workers):
            with _lock:
                if not state["running"]:
                    break
            try:
                ok = _submit_share(wallet, current_hashrate, pow_nonce=nonce, pow_hash=best_pow, cpu_load=cpu_load, cpu_temp=cpu_temp)
                if ok:
                    accepted += 1
                else:
                    rejected += 1
            except Exception:
                rejected += 1

        with _lock:
            state["shares"] += accepted + rejected
            state["accepted"] += accepted
            state["rejected"] += rejected
            if rejected > 0 and accepted == 0:
                state["error"] = "Pool connection/reject errors"
            elif accepted > 0:
                state["error"] = ""
        _sync_chain_height()
        time.sleep(0.5)


def start_mining():
    with _lock:
        if state["running"]:
            return True, "CPU"
        state["running"] = True
        state["started_at"] = time.time()
        state["start_block"] = int(state.get("last_seen_block", 0))
        state["mode"] = "CPU_ONLY"

    _start_cpu_workers()
    _save_miner_state()
    threading.Thread(target=miner_loop, daemon=True).start()
    return True, "CPU"


def stop_mining():
    with _lock:
        state["running"] = False
    _stop_cpu_workers()


TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Miner Web GUI</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    .container { max-width: 860px; margin: 0 auto; padding: 20px; }
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
    <h1>MPA Miner Web GUI (CPU ONLY)</h1>
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
      <strong>Miner ID:</strong> {{ miner_id }}<br/>
      <strong>Mode:</strong> {{ mode }} (Target CPU: {{ cpu_target }}%)<br/>
      <strong>Algorithm:</strong> {{ algorithm }}<br/>
      <strong>Best recent MPAALG hash:</strong> {{ last_pow }}<br/>
      <strong>CPU load:</strong> {{ "%.1f"|format(cpu_load|float) }}% · <strong>CPU temp:</strong> {{ cpu_temp }}<br/>
      <strong>Pool:</strong> {{ pool_host }}:{{ pool_port }}<br/>
      <strong>Start from block:</strong> {{ start_block }}<br/>
      <strong>Last saved block:</strong> {{ last_seen_block }}
      {% if error %}<div class="err">{{ error }}</div>{% endif %}
    </div>

    <div class="row">
      <div class="metric"><div class="k">Hashrate</div><div class="v">{{ hashrate }} MH/s</div></div>
      <div class="metric"><div class="k">CPU Workers</div><div class="v">{{ workers }}</div></div>
      <div class="metric"><div class="k">Shares</div><div class="v">{{ shares }}</div></div>
      <div class="metric"><div class="k">Accepted</div><div class="v">{{ accepted }}</div></div>
      <div class="metric"><div class="k">Rejected</div><div class="v">{{ rejected }}</div></div>
      <div class="metric"><div class="k">CPU Load</div><div class="v">{{ "%.1f"|format(cpu_load|float) }}%</div></div>
      <div class="metric"><div class="k">CPU Temp</div><div class="v">{{ cpu_temp }}</div></div>
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
    _save_miner_state()
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


_bootstrap_saved_state()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
