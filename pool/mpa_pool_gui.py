import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, render_template_string
from pool.mpa_pool_server import balances, miners

app = Flask(__name__)

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
    a { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Pool Dashboard</h1>
    <p class="muted">Auto-refresh every 2s · <a href="/api/pool">JSON API</a></p>

    <div class="cards">
      <div class="card"><div class="title">Active miners</div><div class="value">{{ miners|length }}</div></div>
      <div class="card"><div class="title">Total shares</div><div class="value">{{ total_shares }}</div></div>
      <div class="card"><div class="title">Total pending payout</div><div class="value">{{ '%.4f'|format(total_balance) }} MPA</div></div>
    </div>

    <h3>Miners</h3>
    <table>
      <thead><tr><th>Miner</th><th>Shares</th><th>Difficulty</th><th>Balance (MPA)</th></tr></thead>
      <tbody>
      {% for m, v in miners.items() %}
        <tr>
          <td>{{ m }}</td>
          <td>{{ v.get('shares', 0) }}</td>
          <td>{{ v.get('difficulty', 1) }}</td>
          <td>{{ '%.4f'|format(balances.get(m, 0)) }}</td>
        </tr>
      {% else %}
        <tr><td colspan="4" class="muted">No connected miners yet.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  <script>
    setTimeout(() => window.location.reload(), 2000);
  </script>
</body>
</html>
"""


@app.route("/")
def home():
    total_shares = sum(v.get("shares", 0) for v in miners.values())
    total_balance = sum(balances.values())
    return render_template_string(
        tpl,
        miners=miners,
        balances=balances,
        total_shares=total_shares,
        total_balance=total_balance,
    )


@app.route("/api/pool")
def pool_api():
    return jsonify(
        {
            "miners": miners,
            "balances": balances,
            "total_shares": sum(v.get("shares", 0) for v in miners.values()),
            "total_balance": sum(balances.values()),
        }
    )


if __name__ == "__main__":
    app.run(port=8080)
