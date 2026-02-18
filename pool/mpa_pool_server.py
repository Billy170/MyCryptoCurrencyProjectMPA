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

STATE_DIR = os.path.join(PROJECT_ROOT, ".mpa_state")
os.makedirs(STATE_DIR, exist_ok=True)
CHAIN_STATE_FILE = os.path.join(STATE_DIR, "network_chain_state.json")

bc = Blockchain()
miners = {}
wallet_balances = {}
state_lock = threading.Lock()
network_sync = {"latest_block": 0, "latest_hash": "", "approved": True, "acks": {"pool": {"pool"}}, "roles_seen": {"pool"}}

api_app = Flask(__name__)


def _save_chain_state():
    payload = {
        "chain": bc.chain,
        "sync": {
            "latest_block": int(network_sync.get("latest_block", 0)),
            "latest_hash": network_sync.get("latest_hash", ""),
            "approved": bool(network_sync.get("approved", True)),
            "acks": {k: sorted(v) for k, v in network_sync.get("acks", {}).items()},
            "roles_seen": sorted(network_sync.get("roles_seen", {"pool"})),
        },
    }
    try:
        with open(CHAIN_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def _load_chain_state():
    try:
        with open(CHAIN_STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return

    saved_chain = payload.get("chain")
    if isinstance(saved_chain, list) and saved_chain:
        bc.chain = saved_chain
        bc.pending_transactions = []

    sync = payload.get("sync") if isinstance(payload, dict) else {}
    if isinstance(sync, dict):
        network_sync["latest_block"] = int(sync.get("latest_block", len(bc.chain) - 1 if bc.chain else 0) or 0)
        network_sync["latest_hash"] = str(sync.get("latest_hash", bc.chain[-1].get("hash", "") if bc.chain else ""))
        network_sync["approved"] = bool(sync.get("approved", True))
        acks = sync.get("acks", {})
        network_sync["acks"] = {str(k): set(v) for k, v in acks.items() if isinstance(v, list)}
        roles_seen = sync.get("roles_seen", ["pool"])
        network_sync["roles_seen"] = set(roles_seen) if isinstance(roles_seen, list) else {"pool"}

    network_sync["roles_seen"].add("pool")
    network_sync["acks"].setdefault("pool", set()).add("pool")


def _sync_status_payload() -> dict:
    return {
        "latest_block": int(network_sync.get("latest_block", 0)),
        "latest_hash": network_sync.get("latest_hash", ""),
        "approved": bool(network_sync.get("approved", True)),
        "acks": {k: sorted(v) for k, v in network_sync.get("acks", {}).items()},
        "roles_seen": sorted(network_sync.get("roles_seen", {"pool"})),
    }


def _mark_new_block(block: dict):
    network_sync["latest_block"] = int(block.get("index", len(bc.chain) - 1))
    network_sync["latest_hash"] = str(block.get("hash", ""))
    network_sync["approved"] = False
    network_sync["acks"] = {"pool": {"pool"}}
    network_sync["roles_seen"].add("pool")


def _maybe_approve_latest_block():
    required_roles = set(network_sync.get("roles_seen", {"pool"}))
    required_roles.add("pool")
    approved = all(network_sync.get("acks", {}).get(role) for role in required_roles)
    network_sync["approved"] = bool(approved)


def _apply_sync_ack(role: str, node_id: str, last_block: int):
    role = role or "unknown"
    node_id = node_id or f"{role}-node"
    network_sync["roles_seen"].add(role)
    latest = int(network_sync.get("latest_block", 0))
    if int(last_block) in {latest, latest + 1}:
        network_sync.setdefault("acks", {}).setdefault(role, set()).add(node_id)
    _maybe_approve_latest_block()


def _append_chain_tx(tx: dict, miner_label: str = "POOL", miner_address: str = "POOL"):
    """Append a transaction to blockchain and mine immediately (demo chain)."""
    bc.pending_transactions.append(tx)
    block = bc.mine(miner_label, miner_address=miner_address)
    _mark_new_block(block)
    _save_chain_state()


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
        for miner_id, info in miners_copy.items():
            miner_wallet = str(info.get("wallet", ""))
            info["wallet_balance"] = float(wallet_copy.get(miner_wallet, 0.0))

    return jsonify(
        {
            "miners": miners_copy,
            "balances": wallet_copy,
            "total_shares": sum(v.get("shares", 0) for v in miners_copy.values()),
            "total_hashrate": sum(int(v.get("hashrate", 0)) for v in miners_copy.values()),
            "total_balance": sum(wallet_copy.values()),
            "chain_height": len(bc.chain),
            "status": "ok",
            "sync": _sync_status_payload(),
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
                "miner_address": b.get("miner_address", ""),
                "date": b.get("date", ""),
                "hour": b.get("hour", 0),
                "minute": b.get("minute", 0),
                "second": b.get("second", 0),
            }
            for b in bc.chain
        ]
    return jsonify({"chain_height": len(blocks), "blocks": blocks, "sync": _sync_status_payload()})


@api_app.get("/api/block/<int:index>")
def block_api(index: int):
    with state_lock:
        if index < 0 or index >= len(bc.chain):
            return jsonify({"ok": False, "error": "block not found"}), 404
        return jsonify({"ok": True, "block": bc.chain[index]})




@api_app.get("/api/blocks")
def blocks_range_api():
    start = int(request.args.get("start", 0) or 0)
    limit = int(request.args.get("limit", 25) or 25)
    start = max(0, start)
    limit = max(1, min(500, limit))
    with state_lock:
        end = min(len(bc.chain), start + limit)
        items = bc.chain[start:end]
        total = len(bc.chain)
    return jsonify({"ok": True, "start": start, "end": end, "total": total, "blocks": items})

@api_app.post("/api/sync")
def sync_api():
    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "unknown")).strip().lower()
    node_id = str(data.get("node_id", f"{role}-node")).strip()
    last_block = int(data.get("last_block", 0) or 0)
    with state_lock:
        _apply_sync_ack(role, node_id, last_block)
        _save_chain_state()
        payload = _sync_status_payload()
    return jsonify({"ok": True, "sync": payload})


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
        _append_chain_tx(tx, miner_label="SYSTEM", miner_address="SYSTEM")
        _sync_balances_from_chain()

    return jsonify({"ok": True, "wallet": wallet, "email": email})




@api_app.post("/api/transfer_simple")
def transfer_simple_api():
    data = request.get_json(silent=True) or {}
    receiver = str(data.get("receiver", "")).strip()
    amount_raw = data.get("amount", 0)

    if not receiver:
        return jsonify({"ok": False, "error": "receiver is required"}), 400

    try:
        amount = float(amount_raw)
    except Exception:
        return jsonify({"ok": False, "error": "invalid amount"}), 400

    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be > 0"}), 400

    with state_lock:
        tx = {
            "type": "transfer",
            "sender": "SYSTEM",
            "receiver": receiver,
            "amount": amount,
            "timestamp": time.time(),
            "coin": "MPA",
        }
        _append_chain_tx(tx, miner_label="SYSTEM", miner_address="SYSTEM")
        _sync_balances_from_chain()

    return jsonify({"ok": True, "tx": tx})


@api_app.post("/api/transfer_wallet")
def transfer_wallet_api():
    data = request.get_json(silent=True) or {}
    sender = str(data.get("sender", "")).strip()
    receiver = str(data.get("receiver", "")).strip()
    amount_raw = data.get("amount", 0)

    if not sender or not receiver:
        return jsonify({"ok": False, "error": "sender and receiver are required"}), 400

    try:
        amount = float(amount_raw)
    except Exception:
        return jsonify({"ok": False, "error": "invalid amount"}), 400

    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be > 0"}), 400

    with state_lock:
        _sync_balances_from_chain()
        sender_balance = float(wallet_balances.get(sender, 0.0))
        if sender_balance < amount:
            return jsonify({"ok": False, "error": "insufficient balance", "balance": sender_balance}), 400

        tx = {
            "type": "transfer",
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "timestamp": time.time(),
            "coin": "MPA",
        }
        _append_chain_tx(tx, miner_label=sender, miner_address=sender)
        _sync_balances_from_chain()

    return jsonify({
        "ok": True,
        "tx": tx,
        "sender_balance": float(wallet_balances.get(sender, 0.0)),
        "receiver_balance": float(wallet_balances.get(receiver, 0.0)),
    })

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


def _apply_submit(miner_id: str, wallet: str, hashrate: int = 0, algo: str = "", pow_hash: str = "", cpu_load: float = 0.0, cpu_temp: str = "N/A"):
    with state_lock:
        is_new_miner = miner_id not in miners
        if is_new_miner:
            miners[miner_id] = {"shares": 0, "difficulty": 1.0, "wallet": wallet, "hashrate": 0, "registered": False, "algo": algo or "MPAALG", "last_pow": "", "cpu_load": 0.0, "cpu_temp": "N/A"}
            _append_chain_tx(
                {
                    "type": "miner_register",
                    "miner_id": miner_id,
                    "wallet": wallet,
                    "timestamp": time.time(),
                    "coin": "MPA",
                },
                miner_label=miner_id,
                miner_address=wallet,
            )
            miners[miner_id]["registered"] = True

        registered_miners = sum(1 for m in miners.values() if m.get("registered"))
        network_difficulty = round(1 + (registered_miners * 0.536), 3)
        # Keep chain mining responsive for real-time pool/miner communication in this demo.
        bc.difficulty = 1

        for m in miners.values():
            m["difficulty"] = network_difficulty

        miners[miner_id]["shares"] += 1
        miners[miner_id]["wallet"] = wallet
        miners[miner_id]["hashrate"] = int(hashrate)
        miners[miner_id]["algo"] = str(algo or miners[miner_id].get("algo", "MPAALG"))
        if pow_hash:
            miners[miner_id]["last_pow"] = str(pow_hash)[:32]
        miners[miner_id]["cpu_load"] = float(cpu_load or 0.0)
        miners[miner_id]["cpu_temp"] = str(cpu_temp or "N/A")[:16]

        _append_chain_tx(
            {
                "type": "mining_reward",
                "sender": "SYSTEM",
                "receiver": wallet,
                "amount": 25.0,
                "miner_id": miner_id,
                "timestamp": time.time(),
                "coin": "MPA",
            },
            miner_label=miner_id,
            miner_address=wallet,
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
                algo = str(msg.get("algo") or "MPAALG")
                pow_hash = str(msg.get("pow_hash") or "")
                cpu_load = float(msg.get("cpu_load", 0.0) or 0.0)
                cpu_temp = str(msg.get("cpu_temp") or "N/A")
                _apply_submit(miner_id, wallet, hashrate, algo=algo, pow_hash=pow_hash, cpu_load=cpu_load, cpu_temp=cpu_temp)
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


_load_chain_state()
if bc.chain:
    network_sync["latest_block"] = int(bc.chain[-1].get("index", len(bc.chain)-1))
    network_sync["latest_hash"] = str(bc.chain[-1].get("hash", ""))
_maybe_approve_latest_block()
_save_chain_state()

if __name__ == "__main__":
    run_pool_server()
