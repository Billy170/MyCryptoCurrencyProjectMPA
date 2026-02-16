import json
import os
import sys
import time
from urllib.request import Request, urlopen

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
POOL_API_BASE = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334")
STATE_DIR = os.path.join(PROJECT_ROOT, ".mpa_state")
os.makedirs(STATE_DIR, exist_ok=True)
EXPLORER_CHAIN_FILE = os.path.join(STATE_DIR, "explorer_chain_cache.json")


def _load_cached_chain() -> list:
    try:
        with open(EXPLORER_CHAIN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        chain = data.get("chain", []) if isinstance(data, dict) else []
        return chain if isinstance(chain, list) else []
    except Exception:
        return []


def _save_cached_chain(chain: list):
    with open(EXPLORER_CHAIN_FILE, "w", encoding="utf-8") as f:
        json.dump({"chain": chain, "updated_at": time.time()}, f)


def _fetch_chain_summaries() -> list:
    with urlopen(f"{POOL_API_BASE}/api/chain", timeout=1.8) as resp:
        data = json.loads(resp.read().decode())
    blocks = data.get("blocks", [])
    return blocks if isinstance(blocks, list) else []


def _fetch_blocks_range(start: int, limit: int = 100) -> list:
    with urlopen(f"{POOL_API_BASE}/api/blocks?start={int(start)}&limit={int(limit)}", timeout=2.5) as resp:
        data = json.loads(resp.read().decode())
    blocks = data.get("blocks", []) if isinstance(data, dict) else []
    return blocks if isinstance(blocks, list) else []


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


def download_and_update_chain() -> dict:
    try:
        remote = _fetch_chain_summaries()
        local = _load_cached_chain()

        if len(local) > len(remote):
            local = local[: len(remote)]

        mismatch = None
        for idx in range(len(local)):
            local_hash = str((local[idx] or {}).get("hash", ""))
            remote_hash = str((remote[idx] or {}).get("hash", ""))
            if local_hash and remote_hash and local_hash != remote_hash:
                mismatch = idx
                break
        if mismatch is not None:
            local = local[:mismatch]

        start = len(local)
        while start < len(remote):
            batch = _fetch_blocks_range(start=start, limit=100)
            if not batch:
                break
            local.extend(batch)
            start = len(local)

        _save_cached_chain(local)
        try:
            send_sync(len(local))
        except Exception:
            pass

        return {"ok": True, "chain_height": len(local), "downloaded": len(local), "remaining": max(0, len(remote) - len(local)), "blocks": local}
    except Exception as exc:
        chain = _load_cached_chain()
        return {"ok": False, "error": str(exc), "chain_height": len(chain), "downloaded": len(chain), "remaining": 0, "blocks": chain}


def fetch_block(index: int):
    chain = _load_cached_chain()
    if 0 <= index < len(chain):
        return {"ok": True, "block": chain[index]}
    return {"ok": False, "error": "block not found"}


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
    .block { min-width:260px; background:#111827; border:1px solid #1f2937; border-radius:10px; padding:12px; }
    .hash { font-family: monospace; font-size:12px; word-break:break-all; }
    .link { color:#93c5fd; text-decoration:none; }
    .panel { background:#111827; border-radius:10px; padding:12px; margin-top:12px; }
    pre { white-space:pre-wrap; word-break:break-word; background:#0b1220; border-radius:8px; padding:10px; }
  </style>
</head>
<body>
<div class="container">
  <h1>MPA Blockchain Map</h1>
  <div class="muted">Explorer auto download/update every 10 seconds.</div>
  <div class="row">
    {% for b in blocks %}
    <div class="block">
      <div><strong>Block #{{ b.index }}</strong></div>
      <div>Txs: {{ b.tx_count if b.tx_count is defined else (b.transactions|length) }} | Nonce: {{ b.nonce }}</div>
      <div>Miner: {{ b.miner }} | Addr: {{ b.miner_address }}</div>
      <div>Date: {{ b.date }} {{ "%02d"|format(b.hour|int) }}:{{ "%02d"|format(b.minute|int) }}:{{ "%02d"|format(b.second|int) }}</div>
      <div>Difficulty: {{ b.difficulty }}</div>
      <div class="hash">Hash: {{ b.hash }}</div>
      <div class="hash">Prev: {{ b.prev_hash }}</div>
      <a class="link" href="/?block={{ b.index }}">Open block</a>
    </div>
    {% endfor %}
  </div>

  <div class="panel">
    <strong>Chain height:</strong> {{ chain_height }}<br/>
    <strong>Downloaded:</strong> {{ downloaded }} · <strong>Remaining:</strong> {{ remaining }}<br/>
    {% if selected_block is not none %}
      <h3>Block details #{{ selected_block.index }}</h3>
      <pre>{{ selected_block | tojson(indent=2) }}</pre>
    {% endif %}
    {% if error %}<div style="color:#fca5a5">{{ error }}</div>{% endif %}
  </div>
</div>
<script>setTimeout(()=>window.location.reload(),10000);</script>
</body>
</html>
"""


@app.get("/")
def home():
    chain = download_and_update_chain()
    blocks = chain.get("blocks", [])
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
        downloaded=chain.get("downloaded", 0),
        remaining=chain.get("remaining", 0),
        selected_block=selected_block,
        error=error,
    )


@app.get("/api/chain")
def api_chain():
    return jsonify(download_and_update_chain())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
