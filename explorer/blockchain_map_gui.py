import json
import os
import sys
from urllib.request import Request, urlopen

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
POOL_API_BASE = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334")




def send_sync(block_height: int):
    payload = {"role": "explorer", "node_id": "blockchain-map", "last_block": int(max(0, block_height - 1))}
    req = Request(
        f"{POOL_API_BASE}/api/sync",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=1.2):
        pass

def fetch_chain():
    try:
        with urlopen(f"{POOL_API_BASE}/api/chain", timeout=1.5) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"chain_height": 0, "blocks": [], "error": str(exc)}


def fetch_block(index: int):
    try:
        with urlopen(f"{POOL_API_BASE}/api/block/{index}", timeout=1.5) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Blockchain Map</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    .container { max-width: 1100px; margin:0 auto; padding:20px; }
    .muted { color:#93a4bf; }
    .row { display:flex; gap:12px; overflow-x:auto; padding:10px 0; }
    .block { min-width:240px; background:#111827; border:1px solid #1f2937; border-radius:10px; padding:12px; }
    .hash { font-family: monospace; font-size:12px; word-break:break-all; }
    .link { color:#93c5fd; text-decoration:none; }
    .panel { background:#111827; border-radius:10px; padding:12px; margin-top:12px; }
    pre { white-space:pre-wrap; word-break:break-word; background:#0b1220; border-radius:8px; padding:10px; }
  </style>
</head>
<body>
<div class="container">
  <h1>MPA Blockchain Map</h1>
  <div class="muted">Explorer-style map (like blockchain.com/explorer) · auto-refresh 2s</div>
  <div class="row">
    {% for b in blocks %}
    <div class="block">
      <div><strong>Block #{{ b.index }}</strong></div>
      <div>Txs: {{ b.tx_count }} | Nonce: {{ b.nonce }}</div>
      <div>Miner: {{ b.miner }}</div>
      <div class="hash">Hash: {{ b.hash }}</div>
      <div class="hash">Prev: {{ b.prev_hash }}</div>
      <a class="link" href="/?block={{ b.index }}">Open block</a>
    </div>
    {% endfor %}
  </div>

  <div class="panel">
    <strong>Chain height:</strong> {{ chain_height }}<br/>
    <strong>Network approval:</strong> {{ "approved" if approved else "pending" }}
    {% if selected_block is not none %}
      <h3>Block details #{{ selected_block.index }}</h3>
      <pre>{{ selected_block | tojson(indent=2) }}</pre>
    {% endif %}
    {% if error %}<div style="color:#fca5a5">{{ error }}</div>{% endif %}
  </div>
</div>
<script>setTimeout(()=>window.location.reload(),2000);</script>
</body>
</html>
"""


@app.get("/")
def home():
    chain = fetch_chain()
    blocks = chain.get("blocks", [])
    try:
        send_sync(int(chain.get("chain_height", 0)))
    except Exception:
        pass
    selected_block = None
    error = chain.get("error", "")

    block_id = request.args.get("block")
    if block_id is not None:
        try:
            idx = int(block_id)
            detail = fetch_block(idx)
            if detail.get("ok"):
                selected_block = detail["block"]
            else:
                error = detail.get("error", "")
        except ValueError:
            error = "invalid block id"

    return render_template_string(
        TPL,
        blocks=blocks,
        chain_height=chain.get("chain_height", 0),
        approved=bool((chain.get("sync") or {}).get("approved", True)),
        selected_block=selected_block,
        error=error,
    )


@app.get("/api/chain")
def api_chain():
    return jsonify(fetch_chain())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
