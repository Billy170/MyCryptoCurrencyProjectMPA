import os
import socket

from flask import Flask, render_template_string

app = Flask(__name__)

SERVICES = [
    {"name": "Wallet Web GUI", "url": "http://127.0.0.1:8070", "port": 8070},
    {"name": "Miner Web GUI", "url": "http://127.0.0.1:8090", "port": 8090},
    {"name": "Pool Web GUI", "url": "http://127.0.0.1:8080", "port": 8080},
]


def is_service_online(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


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
        <a class="btn" href="{{ s.url }}" target="_blank" rel="noopener">Open</a>
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
    for s in SERVICES:
        services.append({**s, "online": is_service_online(s["port"])})
    return render_template_string(TPL, services=services)


if __name__ == "__main__":
    app.run(port=8060)
