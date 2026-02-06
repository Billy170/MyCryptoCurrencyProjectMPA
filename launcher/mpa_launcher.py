import os
import socket
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


SERVICES = [
    {"name": "central-web-gui", "cmd": [PYTHON, os.path.join(ROOT, "central_web_gui.py")], "port": 8060},
    {"name": "p2p-node", "cmd": [PYTHON, os.path.join(ROOT, "..", "p2p", "node.py")], "port": 5000},
    {"name": "pool-server", "cmd": [PYTHON, os.path.join(ROOT, "..", "pool", "mpa_pool_server.py")], "port": 3333},
    {"name": "pool-gui", "cmd": [PYTHON, os.path.join(ROOT, "..", "pool", "mpa_pool_gui.py")], "port": 8080},
    {"name": "wallet-web-gui", "cmd": [PYTHON, os.path.join(ROOT, "..", "wallet", "wallet_web_gui.py")], "port": 8070},
    {"name": "miner-web-gui", "cmd": [PYTHON, os.path.join(ROOT, "..", "miner", "miner_web_gui.py")], "port": 8090},
    {"name": "explorer-rpc", "cmd": [PYTHON, os.path.join(ROOT, "..", "explorer", "explorer_rpc.py")]},
    {"name": "admin-dashboard", "cmd": [PYTHON, os.path.join(ROOT, "..", "admin", "admin_dashboard.py")], "port": 9000},
]


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def launch_services():
    procs = []
    skipped = []
    for svc in SERVICES:
        port = svc.get("port")
        if port is not None and is_port_in_use(port):
            skipped.append(f"{svc['name']} (port {port} already in use)")
            continue
        procs.append(subprocess.Popen(svc["cmd"]))

    print("MPA running...")
    if skipped:
        print("Skipped:")
        for item in skipped:
            print(f" - {item}")

    try:
        input("Press ENTER to stop all services.")
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    launch_services()
