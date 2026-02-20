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
    :root { --bg:#0a0f1c; --panel:#111827; --panel-2:#0f172a; --accent:#f7931a; --text:#e5e7eb; --muted:#93a4bf; }
    * { box-sizing: border-box; }
    body { font-family: Inter, Segoe UI, Arial, sans-serif; background: radial-gradient(circle at 10% 10%, #1a2440 0, var(--bg) 45%); color:var(--text); margin:0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
    .hero { display:flex; justify-content:space-between; align-items:center; background:linear-gradient(135deg,#111827,#1f2937); border:1px solid #263044; border-radius:16px; padding:16px 18px; margin-bottom:14px; }
    .hero h1 { margin:0; font-size:24px; }
    .tag { background:rgba(247,147,26,.15); color:#ffbf6d; border:1px solid rgba(247,147,26,.4); border-radius:999px; padding:6px 12px; font-size:12px; font-weight:700; letter-spacing:.4px; }
    .grid { display:grid; grid-template-columns: 1.2fr 1.8fr; gap:14px; margin-bottom:14px; }
    .panel { background:linear-gradient(165deg,var(--panel),var(--panel-2)); border:1px solid #263044; border-radius:14px; padding:16px; }
    .ok { color:#34d399; font-weight:700; }
    .stop { color:#f87171; font-weight:700; }
    .muted { color:var(--muted); }
    .err { color:#fca5a5; margin-top: 8px; }
    .row { display:grid; grid-template-columns:repeat(4,minmax(140px,1fr)); gap:12px; }
    .metric { background:#121b2f; border:1px solid #273149; border-radius:12px; padding:12px; }
    .metric .k { color:#8fa2c6; font-size: 12px; text-transform: uppercase; letter-spacing:.4px; }
    .metric .v { font-size: 22px; font-weight: 700; margin-top:4px; }
    input { width:100%; padding:10px; border-radius:10px; border:1px solid #374151; background:#0a1222; color:#e2e8f0; margin-top:6px; }
    button { border:0; padding:10px 14px; border-radius:10px; cursor:pointer; font-weight:700; margin-top:8px; }
    .start { background:linear-gradient(135deg,#f59e0b,#f97316); color:white; }
    .stopbtn { background:linear-gradient(135deg,#ef4444,#b91c1c); color:white; }
    .save { background:linear-gradient(135deg,#2563eb,#1d4ed8); color:white; }
    a { color:#93c5fd; text-decoration:none; }
    .actions { margin-top:12px; display:flex; gap:10px; }
    @media (max-width: 980px) { .grid{grid-template-columns:1fr;} .row{grid-template-columns:repeat(2,minmax(130px,1fr));} }
  </style>
</head>
<body>
  <div class="container">
    <div class="hero">
      <h1>MPA Miner — NiceHash Style Dashboard</h1>
      <div>
        <span class="tag">{{ algorithm }}</span>
        <a href="/api/miner" style="margin-left:10px">JSON API</a>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <form method="post" action="/set_wallet">
          <strong>Wallet address for rewards</strong>
          <input name="wallet" value="{{ wallet }}" />
          <button class="save" type="submit">Save wallet</button>
        </form>
        <div class="actions">
          <form method="post" action="/start" style="display:inline-block">
            <button class="start" type="submit">Start Mining</button>
          </form>
          <form method="post" action="/stop" style="display:inline-block">
            <button class="stopbtn" type="submit">Stop Mining</button>
          </form>
        </div>
      </div>

      <div class="panel">
        <strong>Status:</strong>
        <span class="{{ 'ok' if running else 'stop' }}">{{ 'RUNNING' if running else 'STOPPED' }}</span><br/>
        <strong>Miner ID:</strong> <span class="muted">{{ miner_id }}</span><br/>
        <strong>Mode:</strong> {{ mode }} (Target CPU: {{ cpu_target }}%)<br/>
        <strong>Best recent MPAALG hash:</strong> <span class="muted">{{ last_pow }}</span><br/>
        <strong>CPU load:</strong> {{ "%.1f"|format(cpu_load|float) }}% · <strong>CPU temp:</strong> {{ cpu_temp }}<br/>
        <strong>Pool:</strong> {{ pool_host }}:{{ pool_port }}<br/>
        <strong>Sync:</strong> Start block {{ start_block }} · Last block {{ last_seen_block }}
        {% if error %}<div class="err">{{ error }}</div>{% endif %}
      </div>
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
