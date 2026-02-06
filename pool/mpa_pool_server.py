import hashlib
import json
import os
import socket
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, request
from mpa_core.mpa_blockchain import Blockchain

HOST = "0.0.0.0"
PORT = 3333
API_HOST = "0.0.0.0"
API_PORT = 3334

bc = Blockchain()
miners = {}
wallet_balances = {}
state_lock = threading.Lock()

api_app = Flask(__name__)


def _append_chain_tx(tx: dict):
    """Append a transaction to blockchain and mine immediately (demo chain)."""
    bc.pending_transactions.append(tx)
    bc.mine("POOL")


def _wallet_records():
    records = []
    for block in bc.chain:
        for tx in block.get("transactions", []):
            if tx.get("type") == "wallet_register":
                records.append(tx)
    return records


def _find_wallet_by_email(email: str):
    email = email.lower().strip()
    for tx in reversed(_wallet_records()):
        if tx.get("email", "").lower() == email:
            return tx
    return None


def _recompute_balances_from_chain():
    balances = {}
    for block in bc.chain:
        for tx in block.get("transactions", []):
            tx_type = tx.get("type")
            if tx_type == "mining_reward":
                wallet = tx.get("receiver")
                amount = float(tx.get("amount", 0))
                if wallet:
                    balances[wallet] = balances.get(wallet, 0.0) + amount
            elif tx_type == "transfer":
                sender = tx.get("sender")
                receiver = tx.get("receiver")
                amount = float(tx.get("amount", 0))
                if sender:
                    balances[sender] = balances.get(sender, 0.0) - amount
                if receiver:
                    balances[receiver] = balances.get(receiver, 0.0) + amount
    return balances


def _sync_balances_from_chain():
    wallet_balances.clear()
    wallet_balances.update(_recompute_balances_from_chain())


@api_app.get("/api/pool")
def pool_stats_api():
    with state_lock:
        miners_copy = {k: dict(v) for k, v in miners.items()}
        _sync_balances_from_chain()
        wallet_copy = dict(wallet_balances)

    return jsonify(
        {
            "miners": miners_copy,
            "balances": wallet_copy,
            "total_shares": sum(v.get("shares", 0) for v in miners_copy.values()),
            "total_hashrate": sum(int(v.get("hashrate", 0)) for v in miners_copy.values()),
            "total_balance": sum(wallet_copy.values()),
            "chain_height": len(bc.chain),
            "status": "ok",
        }
    )


@api_app.get("/api/wallet/<wallet>")
def wallet_balance_api(wallet: str):
    with state_lock:
        _sync_balances_from_chain()
        balance = float(wallet_balances.get(wallet, 0.0))
    return jsonify({"wallet": wallet, "balance": balance, "coin": "MPA"})


@api_app.get("/api/chain")
def chain_api():
    with state_lock:
        blocks = [
            {
                "index": b.get("index"),
                "hash": b.get("hash"),
                "prev_hash": b.get("prev_hash"),
                "timestamp": b.get("timestamp"),
                "tx_count": len(b.get("transactions", [])),
                "miner": b.get("miner"),
                "nonce": b.get("nonce"),
                "difficulty": b.get("difficulty"),
            }
            for b in bc.chain
        ]
    return jsonify({"chain_height": len(blocks), "blocks": blocks})


@api_app.get("/api/block/<int:index>")
def block_api(index: int):
    with state_lock:
        if index < 0 or index >= len(bc.chain):
            return jsonify({"ok": False, "error": "block not found"}), 404
        return jsonify({"ok": True, "block": bc.chain[index]})


@api_app.post("/api/register_wallet")
def register_wallet_api():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({"ok": False, "error": "email and password are required"}), 400

    with state_lock:
        if _find_wallet_by_email(email):
            return jsonify({"ok": False, "error": "email already registered"}), 409

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        wallet = "MPA-" + hashlib.sha256(f"{email}:{time.time()}".encode()).hexdigest()[:24]
        tx = {
            "type": "wallet_register",
            "email": email,
            "password_hash": password_hash,
            "wallet": wallet,
            "timestamp": time.time(),
            "coin": "MPA",
        }
        _append_chain_tx(tx)
        _sync_balances_from_chain()

    return jsonify({"ok": True, "wallet": wallet, "email": email})


@api_app.post("/api/login_wallet")
def login_wallet_api():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not email or not password:
        return jsonify({"ok": False, "error": "email and password are required"}), 400

    with state_lock:
        record = _find_wallet_by_email(email)
        if not record:
            return jsonify({"ok": False, "error": "unknown email"}), 404
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != record.get("password_hash"):
            return jsonify({"ok": False, "error": "invalid password"}), 401

        wallet = record["wallet"]
        _sync_balances_from_chain()
        balance = float(wallet_balances.get(wallet, 0.0))

    return jsonify({"ok": True, "wallet": wallet, "email": email, "balance": balance})


def run_pool_api(host=API_HOST, port=API_PORT):
    api_app.run(host=host, port=port, debug=False, use_reloader=False)


def _apply_submit(miner_id: str, wallet: str, hashrate: int = 0):
    with state_lock:
        if miner_id not in miners:
            miners[miner_id] = {"shares": 0, "difficulty": 1, "wallet": wallet, "hashrate": 0}
        miners[miner_id]["shares"] += 1
        miners[miner_id]["wallet"] = wallet
        miners[miner_id]["hashrate"] = int(hashrate)

        _append_chain_tx(
            {
                "type": "mining_reward",
                "sender": "SYSTEM",
                "receiver": wallet,
                "amount": 0.01,
                "miner_id": miner_id,
                "timestamp": time.time(),
                "coin": "MPA",
            }
        )
        _sync_balances_from_chain()


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
                hashrate = int(msg.get("hashrate", 0) or 0)
                _apply_submit(miner_id, wallet, hashrate)
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
