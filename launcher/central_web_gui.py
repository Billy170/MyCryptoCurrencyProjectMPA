import os
import socket
import subprocess
import sys
import time

from flask import Flask, redirect, render_template_string, request, url_for

app = Flask(__name__)
ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
MINER_BASE_PORT = 8090

SERVICES = {
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


def start_service(key: str):
    svc = SERVICES[key]
    for cmd in svc["commands"]:
        target_port = 8070 if "wallet_web_gui.py" in " ".join(cmd) else 8080 if "mpa_pool_gui.py" in " ".join(cmd) else 3333
        if is_service_online(target_port):
            continue
        _start_cmd(cmd)


def start_miners(count: int):
    count = max(1, min(16, count))
    cpu_count = max(1, os.cpu_count() or 1)
    workers_each = max(1, cpu_count // count)

    for i in range(count):
        port = MINER_BASE_PORT + i
        if is_service_online(port):
            continue
        env = os.environ.copy()
        env["MPA_MINER_PORT"] = str(port)
        env["MPA_MINER_ID"] = f"web-miner-{i+1}"
        env["MPA_MINER_WORKERS"] = str(workers_each)
        _start_cmd([PYTHON, os.path.join(ROOT, "..", "miner", "miner_web_gui.py")], env=env)


def miner_online_count(count: int) -> int:
    return sum(1 for i in range(count) if is_service_online(MINER_BASE_PORT + i))


def start_all(miner_count: int):
    for key in SERVICES:
        start_service(key)
    start_miners(miner_count)


TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Central Web GUI</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
    .card { background:#111827; border-radius:12px; padding:14px; border:1px solid #1f2937; margin-bottom:14px; }
    .ok { color:#34d399; } .down { color:#fca5a5; }
    button, a.btn { background:#2563eb; color:#fff; border:0; border-radius:8px; padding:8px 12px; text-decoration:none; cursor:pointer; display:inline-block; margin-right:8px; }
    input { padding:8px; border-radius:8px; border:1px solid #334155; background:#0b1220; color:#e2e8f0; }
    .tabs { display:grid; grid-template-columns: 1fr 1fr; gap:10px; }
    iframe { width:100%; height:420px; border:1px solid #1f2937; border-radius:8px; background:#fff; }
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
      <a class="btn" href="{{ url_for('open_all') }}">Start / Refresh All In One Tab</a>
      <a class="btn" href="{{ url_for('workspace') }}">Open One-Tab Workspace</a>
      <div style="margin-top:8px;">Online miners: {{ miners_online }} / {{ miner_count }}</div>
    </div>

    <div class="card">
      {% for s in services %}
        <div><strong>{{ s.name }}</strong> — {% if s.online %}<span class="ok">Online</span>{% else %}<span class="down">Offline</span>{% endif %}</div>
      {% endfor %}
    </div>

    <div class="tabs">
      <div class="card"><h3>Pool</h3><iframe src="http://{{ host }}:8080/"></iframe></div>
      <div class="card"><h3>Wallet</h3><iframe src="http://{{ host }}:8070/"></iframe></div>
      <div class="card"><h3>Miner #1</h3><iframe src="http://{{ host }}:8090/"></iframe></div>
      <div class="card"><h3>Explorer</h3><iframe src="http://{{ host }}:8050/"></iframe></div>
    </div>
  </div>
</body>
</html>
"""


@app.get("/")
def home():
    
    try:
        miner_count = int(request.cookies.get("miner_count", "1"))
    except ValueError:
        miner_count = 1
    services = []
    for key, s in SERVICES.items():
        services.append({"key": key, **s, "online": is_service_online(s["port"])})
    host = request.host.split(":")[0]
    return render_template_string(
        TPL,
        services=services,
        miner_count=miner_count,
        miners_online=miner_online_count(miner_count),
        host=host,
    )


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


@app.get("/open/all")
def open_all():
    try:
        miner_count = max(1, min(16, int(request.cookies.get("miner_count", "1"))))
    except ValueError:
        miner_count = 1
    start_all(miner_count)
    time.sleep(1.0)
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
            if miner_online_count(miner_count) >= 1:
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
