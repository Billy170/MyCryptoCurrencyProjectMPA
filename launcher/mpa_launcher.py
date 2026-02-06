import subprocess
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))  # φάκελος launcher

services = [
    [sys.executable, os.path.join(ROOT,"..","p2p","node.py")],
    [sys.executable, os.path.join(ROOT,"..","pool","mpa_pool_server.py")],
    [sys.executable, os.path.join(ROOT,"..","pool","mpa_pool_gui.py")],
    [sys.executable, os.path.join(ROOT,"..","wallet","mpa_wallet_gui.py")],
    [sys.executable, os.path.join(ROOT,"..","miner","mpa_gpu_miner_gui.py")],
    [sys.executable, os.path.join(ROOT,"..","explorer","explorer_rpc.py")],
    [sys.executable, os.path.join(ROOT,"..","admin","admin_dashboard.py")],
]

procs = [subprocess.Popen(s) for s in services]
print("MPA running...")
input("Press ENTER to stop all services.")
for p in procs:
    p.terminate()
