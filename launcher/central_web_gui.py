import json
import os
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from flask import Flask, redirect, render_template_string, request, url_for

app = Flask(__name__)
ROOT = os.path.dirname(os.path.abspath(__file__))
POOL_API = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334")


def _resolve_python() -> str:
    exe = sys.executable or ""
    base = os.path.basename(exe).lower()
    if exe and "python" in base and os.path.exists(exe):
        return exe

    env_python = os.environ.get("MPA_PYTHON", "").strip()
    if env_python:
        return env_python

    return shutil.which("python3") or shutil.which("python") or "python3"


PYTHON = _resolve_python()
MINER_BASE_PORT = 8090

SERVICES = {
    "p2p": {
        "name": "P2P Node",
        "port": 5000,
        "commands": [[PYTHON, os.path.join(ROOT, "..", "p2p", "node.py")]],
    },
    "explorer": {
        "name": "Blockchain Map Explorer",
        "port": 8050,
        "commands": [[PYTHON, os.path.join(ROOT, "..", "explorer", "blockchain_map_gui.py")]],
    },
    "wallet": {
        "name": "Wallet Web GUI",
        "port": 8070,
        "commands": [[PYTHON, os.path.join(ROOT, "..", "wallet", "wallet_web_gui.py")]],
    },
    "pool": {
        "name": "Pool Web GUI",
        "port": 8080,
        "commands": [
            [PYTHON, os.path.join(ROOT, "..", "pool", "mpa_pool_server.py")],
            [PYTHON, os.path.join(ROOT, "..", "pool", "mpa_pool_gui.py")],
        ],
    },
}

children = []


def _service_url(hostname: str, port: int) -> str:
    return f"http://{hostname}:{port}"


def is_service_online(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _start_cmd(cmd, env=None):
    children.append(subprocess.Popen(cmd, env=env))


def _target_port_for_command(cmd) -> int:
    text = " ".join(cmd)
    if "wallet_web_gui.py" in text:
        return 8070
    if "mpa_pool_gui.py" in text:
        return 8080
    if "mpa_pool_server.py" in text:
        return 3333
    if "blockchain_map_gui.py" in text:
        return 8050
    if "miner_web_gui.py" in text:
        return MINER_BASE_PORT
    if "p2p/node.py" in text:
        return 5000
    return 0


def _api_post(path: str, payload: dict):
    req = Request(
        f"{POOL_API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=2.0) as resp:
        return json.loads(resp.read().decode()), resp.getcode()


def start_service(key: str):
    svc = SERVICES[key]
    for cmd in svc["commands"]:
        target_port = _target_port_for_command(cmd)
        if target_port and is_service_online(target_port):
            continue
        _start_cmd(cmd)


def _post_local(port: int, path: str):
    req = Request(f"http://127.0.0.1:{port}{path}", data=b"", method="POST")
    with urlopen(req, timeout=1.5):
        return True


def start_miner(port: int):
    miner_idx = max(0, port - MINER_BASE_PORT)
    if not is_service_online(port):
        env = os.environ.copy()
        env["MPA_MINER_PORT"] = str(port)
        env["MPA_MINER_ID"] = f"web-miner-{miner_idx + 1}"
        _start_cmd([PYTHON, os.path.join(ROOT, "..", "miner", "miner_web_gui.py")], env=env)
        for _ in range(20):
            if is_service_online(port):
                break
            time.sleep(0.15)
    if is_service_online(port):
        try:
            _post_local(port, "/start")
        except Exception:
            pass


def stop_miner(port: int):
    if is_service_online(port):
        try:
            _post_local(port, "/stop")
        except Exception:
            pass


def start_miners(count: int):
    count = max(1, min(16, count))
    for i in range(count):
        start_miner(MINER_BASE_PORT + i)


def miner_online_ports(count: int):
    count = max(1, min(16, count))
    return [MINER_BASE_PORT + i for i in range(count) if is_service_online(MINER_BASE_PORT + i)]


def start_all(miner_count: int):
    for key in SERVICES:
        start_service(key)
    start_miners(miner_count)


def stop_all():
    alive = []
    for proc in children:
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            else:
                alive.append(proc)

    time.sleep(0.5)
    for proc in alive:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    for pattern in [
        "p2p/node.py",
        "pool/mpa_pool_server.py",
        "pool/mpa_pool_gui.py",
        "wallet/wallet_web_gui.py",
        "explorer/blockchain_map_gui.py",
        "miner/miner_web_gui.py",
    ]:
        try:
            subprocess.run(["pkill", "-f", pattern], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Central Web GUI</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    .container { max-width: 1300px; margin: 0 auto; padding: 20px; }
    .card { background:#111827; border-radius:12px; padding:14px; border:1px solid #1f2937; margin-bottom:14px; }
    .ok { color:#34d399; } .down { color:#fca5a5; }
    button, a.btn { background:#2563eb; color:#fff; border:0; border-radius:8px; padding:8px 12px; text-decoration:none; cursor:pointer; display:inline-block; margin-right:8px; margin-top:6px; }
    .danger { background:#ef4444 !important; }
    input { padding:8px; border-radius:8px; border:1px solid #334155; background:#0b1220; color:#e2e8f0; }
    .tabs { display:grid; grid-template-columns: 1fr 1fr; gap:10px; }
    iframe { width:100%; height:360px; border:1px solid #1f2937; border-radius:8px; background:#fff; }
    .miner-grid { display:grid; grid-template-columns: 1fr 1fr; gap:10px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA One-Tab Control Center</h1>
    <div class="card">
      <form method="post" action="/set_miner_count" style="display:inline-block; margin-right:10px;">
        <label>Miner instances:</label>
        <input name="miner_count" value="{{ miner_count }}" />
        <button type="submit">Save</button>
      </form>
      <form method="post" action="{{ url_for('open_all') }}" style="display:inline-block;">
        <input type="hidden" name="count" value="{{ miner_count }}" />
        <button class="btn" type="submit">Start / Refresh All</button>
      </form>
      <a class="btn" href="{{ url_for('workspace') }}">Open Workspace</a>
      <form method="post" action="{{ url_for('stop_all_route') }}" style="display:inline-block;">
        <button class="btn danger" type="submit">Stop All</button>
      </form>
      <div style="margin-top:8px;">Online miners: {{ miners_online|length }} / {{ miner_count }} — Ports: {{ miners_online }}</div>
    </div>

    <div class="card">
      {% for s in services %}
        <div><strong>{{ s.name }}</strong> — {% if s.online %}<span class="ok">Online</span>{% else %}<span class="down">Offline</span>{% endif %}</div>
      {% endfor %}
    </div>

    <div class="tabs">
      <div class="card"><h3>Pool</h3><iframe src="http://{{ host }}:8080/"></iframe></div>
      <div class="card"><h3>Wallet</h3><iframe src="http://{{ host }}:8070/"></iframe></div>
      <div class="card" style="grid-column:1 / span 2;"><h3>Blockchain Map</h3><iframe src="http://{{ host }}:8050/"></iframe></div>
    </div>

    <div class="card">
      <h3>All Miners</h3>
      <div class="miner-grid">
        {% for port in miner_ports %}
          <div>
            <div style="margin-bottom:6px;">Miner on port {{ port }}</div>
            <form method="post" action="{{ url_for('start_miner_route', port=port) }}" style="display:inline-block; margin-bottom:6px;">
              <button type="submit">Start Miner</button>
            </form>
            <form method="post" action="{{ url_for('stop_miner_route', port=port) }}" style="display:inline-block; margin-bottom:6px;">
              <button class="danger" type="submit">Stop Miner</button>
            </form>
            <iframe src="http://{{ host }}:{{ port }}/"></iframe>
          </div>
        {% else %}
          <div class="down">No miner ports configured.</div>
        {% endfor %}
      </div>
    </div>
  </div>
</body>
</html>
"""


def _render_home():
    try:
        miner_count = int(request.cookies.get("miner_count", "1"))
    except ValueError:
        miner_count = 1
    services = []
    for key, s in SERVICES.items():
        services.append({"key": key, **s, "online": is_service_online(s["port"])})

    host = request.host.split(":")[0]
    configured_ports = [MINER_BASE_PORT + i for i in range(max(1, min(16, miner_count)))]
    discovered_online = [MINER_BASE_PORT + i for i in range(16) if is_service_online(MINER_BASE_PORT + i)]
    miner_ports = sorted(set(configured_ports + discovered_online))
    online_miners = discovered_online
    return render_template_string(
        TPL,
        services=services,
        miner_count=miner_count,
        miners_online=online_miners,
        miner_ports=miner_ports,
        host=host,
    )


@app.get("/")
def home():
    return _render_home()


@app.post("/set_miner_count")
def set_miner_count():
    raw = request.form.get("miner_count", "1").strip()
    try:
        count = max(1, min(16, int(raw)))
    except ValueError:
        count = 1
    resp = redirect(url_for("home"))
    resp.set_cookie("miner_count", str(count))
    return resp


@app.get("/workspace")
def workspace():
    return home()


@app.route("/open/all", methods=["GET", "POST"])
def open_all():
    raw = request.values.get("count") or request.cookies.get("miner_count", "1")
    try:
        miner_count = max(1, min(16, int(raw)))
    except ValueError:
        miner_count = 1
    start_all(miner_count)
    time.sleep(1.0)
    resp = redirect(url_for("workspace"))
    resp.set_cookie("miner_count", str(miner_count))
    return resp


@app.route("/stop/all", methods=["GET", "POST"])
def stop_all_route():
    stop_all()
    resp = redirect(url_for("home"))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/miner/start/<int:port>")
def start_miner_route(port: int):
    if MINER_BASE_PORT <= port <= MINER_BASE_PORT + 15:
        start_miner(port)
    return redirect(url_for("workspace"))


@app.post("/miner/stop/<int:port>")
def stop_miner_route(port: int):
    if MINER_BASE_PORT <= port <= MINER_BASE_PORT + 15:
        stop_miner(port)
    return redirect(url_for("workspace"))


@app.get("/open/<key>")
def open_service(key: str):
    host = request.host.split(":")[0]

    if key == "miner":
        raw_count = request.args.get("count") or request.cookies.get("miner_count", "1")
        try:
            miner_count = max(1, min(16, int(raw_count)))
        except ValueError:
            miner_count = 1
        start_miners(miner_count)
        for _ in range(20):
            if len(miner_online_ports(miner_count)) >= 1:
                break
            time.sleep(0.15)
        return redirect(_service_url(host, MINER_BASE_PORT))

    if key in SERVICES:
        start_service(key)
        target_port = SERVICES[key]["port"]
        for _ in range(20):
            if is_service_online(target_port):
                break
            time.sleep(0.15)
        return redirect(_service_url(host, target_port))

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060)
