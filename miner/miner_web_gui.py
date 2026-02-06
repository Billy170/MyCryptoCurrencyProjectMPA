import os
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, redirect, render_template_string, url_for

try:
    from miner.gpu_check import check_gpu
except ImportError:
    from gpu_check import check_gpu

app = Flask(__name__)

state = {
    "running": False,
    "gpu_name": "unknown",
    "hashrate": 0,
    "shares": 0,
    "started_at": None,
}

_lock = threading.Lock()


def miner_loop():
    while True:
        with _lock:
            if not state["running"]:
                break
            state["hashrate"] = 120 + int(time.time()) % 30
            state["shares"] += 1
        time.sleep(0.5)


def start_mining():
    ok, gpu_name = check_gpu()
    with _lock:
        state["gpu_name"] = gpu_name
        if not ok:
            return False, gpu_name
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
    .row { display:flex; gap:14px; flex-wrap: wrap; }
    .metric { background:#1f2937; border-radius:10px; padding:12px; min-width: 160px; }
    .metric .k { color:#93c5fd; font-size: 13px; }
    .metric .v { font-size: 24px; font-weight: bold; }
    button { border:0; padding:10px 14px; border-radius:8px; cursor:pointer; font-weight:bold; }
    .start { background:#10b981; color:white; }
    .stopbtn { background:#ef4444; color:white; }
    a { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Miner Web GUI</h1>
    <p><a href="/api/miner">JSON API</a></p>

    <div class="panel">
      <strong>Status:</strong>
      <span class="{{ 'ok' if running else 'stop' }}">{{ 'RUNNING' if running else 'STOPPED' }}</span><br/>
      <strong>GPU:</strong> {{ gpu_name }}
    </div>

    <div class="row">
      <div class="metric"><div class="k">Hashrate</div><div class="v">{{ hashrate }} MH/s</div></div>
      <div class="metric"><div class="k">Shares</div><div class="v">{{ shares }}</div></div>
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
    setTimeout(() => window.location.reload(), 1500);
  </script>
</body>
</html>
"""


@app.get("/")
def home():
    with _lock:
        data = dict(state)
    return render_template_string(TPL, **data)


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
    app.run(port=8090)
