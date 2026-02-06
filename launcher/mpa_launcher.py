import subprocess
import os

ROOT = os.path.dirname(os.path.abspath(__file__))  # φάκελος launcher

services = [
    ["python", os.path.join(ROOT,"..","p2p","node.py")],
    ["python", os.path.join(ROOT,"..","pool","mpa_pool_server.py")],
    ["python", os.path.join(ROOT,"..","pool","mpa_pool_gui.py")],
    ["python", os.path.join(ROOT,"..","wallet","mpa_wallet_gui.py")],
    ["python", os.path.join(ROOT,"..","miner","mpa_gpu_miner_gui.py")],
    ["python", os.path.join(ROOT,"..","explorer","explorer_rpc.py")],
    ["python", os.path.join(ROOT,"..","admin","admin_dashboard.py")],
]

procs = [subprocess.Popen(s) for s in services]
print("MPA running...")
input("Press ENTER to stop all services.")
for p in procs:
    p.terminate()
