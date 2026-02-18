import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from urllib.request import Request, urlopen
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
POOL_API_URL = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334/api/pool")




def send_sync(last_block: int):
    payload = {"role": "pool", "node_id": "pool-gui", "last_block": int(last_block)}
    req = Request(
        os.environ.get("MPA_POOL_API_URL_SYNC", "http://127.0.0.1:3334") + "/api/sync",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=4.0):
        pass

def fetch_pool_stats():
    try:
        with urlopen(POOL_API_URL, timeout=4.0) as resp:
            data = json.loads(resp.read().decode())
        data["online"] = True
        try:
            send_sync(int(data.get("chain_height", 0)) - 1)
        except Exception:
            pass
        data["api_url"] = POOL_API_URL
        data["error"] = ""
        return data
    except Exception as exc:
        return {
            "miners": {},
            "balances": {},
            "total_shares": 0,
            "total_balance": 0,
            "status": "offline",
            "online": False,
            "total_hashrate": 0,
            "api_url": POOL_API_URL,
            "error": str(exc),
        }


tpl = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Pool Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; }
    .container { max-width: 980px; margin: 0 auto; padding: 20px; }
    .cards { display:grid; grid-template-columns: repeat(3,minmax(120px,1fr)); gap:12px; margin-bottom:16px; }
    .card { background:#1e293b; border-radius:10px; padding:14px; }
    .title { color:#93c5fd; font-size:14px; }
    .value { font-size:24px; font-weight:bold; margin-top:4px; }
    table { width:100%; border-collapse: collapse; background:#111827; border-radius:10px; overflow:hidden; }
    th, td { padding:10px; border-bottom:1px solid #1f2937; text-align:left; }
    th { background:#1f2937; }
    .muted { color:#94a3b8; }
    .ok { color:#34d399; }
    .warn { color:#fca5a5; }
    a { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Pool Dashboard</h1>
    <p class="muted">Auto-refresh every 5s · <a href="/api/pool">JSON API</a></p>

    <div class="card" style="margin-bottom:16px;">
      <strong>Pool API:</strong> {{ api_url }}<br/>
      {% if online %}
        <span class="ok">Connected</span>
      {% else %}
        <span class="warn">Offline</span> — {{ error }}
      {% endif %}
      <br/><strong>Network block approval:</strong> {{ (sync or {}).get("approved", True) }}
    </div>

    <div class="cards">
      <div class="card"><div class="title">Active miners</div><div class="value">{{ miners|length }}</div></div>
      <div class="card"><div class="title">Total hashrate</div><div class="value">{{ total_hashrate }} MH/s</div></div>
      <div class="card"><div class="title">Total shares</div><div class="value">{{ total_shares }}</div></div>
      <div class="card"><div class="title">Total pending payout</div><div class="value">{{ '%.4f'|format(total_balance) }} MPA</div></div>
    </div>

    <h3>Miners</h3>
    <table>
      <thead><tr><th>Miner</th><th>Wallet</th><th>Algo</th><th>CPU Load</th><th>CPU Temp</th><th>Shares</th><th>Difficulty</th><th>Hashrate</th><th>Last PoW</th><th>Balance (MPA)</th></tr></thead>
      <tbody>
      {% for m, v in miners.items() %}
        <tr>
          <td>{{ m }}</td>
          <td>{{ v.get('wallet', '') }}</td>
          <td>{{ v.get('algo', 'MPAALG') }}</td>
          <td>{{ "%.1f"|format(v.get('cpu_load', 0)|float) }}%</td>
          <td>{{ v.get('cpu_temp', 'N/A') }}</td>
          <td>{{ v.get('shares', 0) }}</td>
          <td>{{ v.get('difficulty', 1) }}</td>
          <td>{{ v.get('hashrate', 0) }}</td>
          <td>{{ v.get('last_pow', '') }}</td>
          <td>{{ '%.4f'|format(v.get('wallet_balance', balances.get(v.get('wallet', ''), 0))) }}</td>
        </tr>
      {% else %}
        <tr><td colspan="10" class="muted">No connected miners yet.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  <script>
    setTimeout(() => window.location.reload(), 5000);
  </script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(tpl, **fetch_pool_stats())


@app.route("/api/pool")
def pool_api():
    return jsonify(fetch_pool_stats())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
