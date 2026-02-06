import os
import sys
import socket
import json
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.mpa_blockchain import Blockchain

HOST = "0.0.0.0"
PORT = 3333
bc = Blockchain()
miners = {}
balances = {}


def handle_client(conn, addr):
    miner = addr[0] + ":" + str(addr[1])
    miners[miner] = {"shares": 0, "difficulty": 1}
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            msg = json.loads(data.decode())
            if msg.get("method") == "submit":
                miners[miner]["shares"] += 1
                balances[miner] = balances.get(miner, 0) + 0.01
                conn.send(json.dumps({"result": "accepted"}).encode())
        except Exception:
            break
    conn.close()


def run_pool_server(host=HOST, port=PORT):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
    except OSError as exc:
        print(f"Pool server not started: {host}:{port} is already in use ({exc}).")
        server.close()
        return False

    server.listen(100)
    print(f"Pool listening on {port}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    run_pool_server()
