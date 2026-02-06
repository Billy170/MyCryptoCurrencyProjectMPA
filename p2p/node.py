from flask import Flask, request, jsonify
from core.mpa_blockchain import Blockchain

app = Flask(__name__)
bc = Blockchain()
peers = set()

@app.route("/blocks", methods=["GET"])
def get_blocks():
    return jsonify([b for b in bc.chain])

@app.route("/blocks", methods=["POST"])
def receive_block():
    block = request.json
    bc.chain.append(block)
    return "OK"

@app.route("/peers", methods=["POST"])
def add_peer():
    peers.add(request.json["peer"])
    return "OK"

if __name__ == "__main__":
    app.run(port=5000)
