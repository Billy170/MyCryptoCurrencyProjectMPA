import json
import os
import socket
import sys
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify
from mpa_core.mpa_blockchain import Blockchain

HOST = "0.0.0.0"
PORT = 3333
API_HOST = "127.0.0.1"
API_PORT = 3334

bc = Blockchain()
miners = {}
wallet_balances = {}
state_lock = threading.Lock()

api_app = Flask(__name__)


@api_app.get("/api/pool")
def pool_stats_api():
    with state_lock:
        miners_copy = {k: dict(v) for k, v in miners.items()}
        wallet_copy = dict(wallet_balances)

    return jsonify(
        {
            "miners": miners_copy,
            "balances": wallet_copy,
            "total_shares": sum(v.get("shares", 0) for v in miners_copy.values()),
            "total_balance": sum(wallet_copy.values()),
            "status": "ok",
        }
    )


@api_app.get("/api/wallet/<wallet>")
def wallet_balance_api(wallet: str):
    with state_lock:
        balance = float(wallet_balances.get(wallet, 0.0))
    return jsonify({"wallet": wallet, "balance": balance, "coin": "MPA"})


def run_pool_api(host=API_HOST, port=API_PORT):
    api_app.run(host=host, port=port, debug=False, use_reloader=False)


def _apply_submit(miner_id: str, wallet: str):
    with state_lock:
        if miner_id not in miners:
            miners[miner_id] = {"shares": 0, "difficulty": 1, "wallet": wallet}
        miners[miner_id]["shares"] += 1
        miners[miner_id]["wallet"] = wallet
        wallet_balances[wallet] = wallet_balances.get(wallet, 0.0) + 0.01


def handle_client(conn, addr):
    default_miner_id = f"{addr[0]}:{addr[1]}"
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            msg = json.loads(data.decode())
            if msg.get("method") == "submit":
                miner_id = str(msg.get("miner_id") or default_miner_id)
                wallet = str(msg.get("wallet") or "UNKNOWN_WALLET")
                _apply_submit(miner_id, wallet)
                conn.send(json.dumps({"result": "accepted", "wallet": wallet}).encode())
            else:
                conn.send(json.dumps({"result": "ignored"}).encode())
        except Exception:
            break
    conn.close()


def run_pool_server(host=HOST, port=PORT):
    threading.Thread(target=run_pool_api, daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
    except OSError as exc:
        print(f"Pool server not started: {host}:{port} is already in use ({exc}).")
        server.close()
        return False

    server.listen(100)
    print(f"Pool listening on {port} (API on http://{API_HOST}:{API_PORT}/api/pool)")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    run_pool_server()
