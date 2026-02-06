import os
import socket
import subprocess
import sys
import time

from flask import Flask, redirect, render_template_string, request, url_for

app = Flask(__name__)
ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

SERVICES = {
    "wallet": {
        "name": "Wallet Web GUI",
        "port": 8070,
        "commands": [[PYTHON, os.path.join(ROOT, "..", "wallet", "wallet_web_gui.py")]],
    },
    "miner": {
        "name": "Miner Web GUI",
        "port": 8090,
        "commands": [[PYTHON, os.path.join(ROOT, "..", "miner", "miner_web_gui.py")]],
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


def start_service(key: str):
    svc = SERVICES[key]
    for cmd in svc["commands"]:
        target_port = None
        cmd_text = " ".join(cmd)
        if "wallet_web_gui.py" in cmd_text:
            target_port = 8070
        elif "miner_web_gui.py" in cmd_text:
            target_port = 8090
        elif "mpa_pool_gui.py" in cmd_text:
            target_port = 8080
        elif "mpa_pool_server.py" in cmd_text:
            target_port = 3333

        if target_port is not None and is_service_online(target_port):
            continue
        children.append(subprocess.Popen(cmd))


TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Central Web GUI</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    .container { max-width: 980px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 6px; }
    .muted { color:#93a4bf; margin-bottom: 18px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(240px,1fr)); gap:14px; }
    .card { background:#111827; border-radius:12px; padding:16px; border:1px solid #1f2937; }
    .name { font-size: 18px; margin-bottom:8px; }
    .ok { color:#34d399; }
    .down { color:#fca5a5; }
    a.btn { display:inline-block; margin-top:10px; text-decoration:none; background:#2563eb; color:white; padding:8px 12px; border-radius:8px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Central Web GUI</h1>
    <div class="muted">Άνοιγμα υπηρεσιών: wallet, miner, pool</div>
    <div class="grid">
      {% for s in services %}
      <div class="card">
        <div class="name">{{ s.name }}</div>
        {% if s.online %}
          <div class="ok">● Online</div>
        {% else %}
          <div class="down">● Offline (port {{ s.port }})</div>
        {% endif %}
        <a class="btn" href="{{ url_for('open_service', key=s.key) }}">Open</a>
      </div>
      {% endfor %}
    </div>
  </div>
</body>
</html>
"""


@app.get("/")
def home():
    services = []
    for key, s in SERVICES.items():
        services.append({"key": key, **s, "online": is_service_online(s["port"])})
    return render_template_string(TPL, services=services)


@app.get("/open/<key>")
def open_service(key: str):
    if key in SERVICES:
        start_service(key)
        target_port = SERVICES[key]["port"]
        for _ in range(20):
            if is_service_online(target_port):
                break
            time.sleep(0.15)
        host = request.host.split(":")[0]
        return redirect(_service_url(host, target_port))
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060)
