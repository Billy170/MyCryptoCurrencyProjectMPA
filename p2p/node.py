import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, request
from mpa_core.live_chain import get_live_chain, write_chain

app = Flask(__name__)
peers = set()


@app.route("/blocks", methods=["GET"])
def get_blocks():
    return jsonify(get_live_chain())


@app.route("/blocks", methods=["POST"])
def receive_block():
    block = request.get_json(silent=True) or {}
    if not isinstance(block, dict):
        return jsonify({"ok": False, "error": "invalid block payload"}), 400

    chain = get_live_chain()
    last_index = int(chain[-1].get("index", len(chain) - 1)) if chain else -1
    incoming_index = int(block.get("index", -1))

    if incoming_index <= last_index:
        return jsonify({"ok": True, "status": "ignored", "reason": "stale block"})

    chain.append(block)
    write_chain(chain)
    return jsonify({"ok": True, "status": "accepted", "height": len(chain)})


@app.route("/peers", methods=["POST"])
def add_peer():
    body = request.get_json(silent=True) or {}
    peer = str(body.get("peer", "")).strip()
    if not peer:
        return jsonify({"ok": False, "error": "peer is required"}), 400
    peers.add(peer)
    return jsonify({"ok": True, "peers": sorted(peers)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
