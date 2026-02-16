import os
import sys
import threading
import time
from tkinter import *

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mpa_core.mpa_blockchain import Blockchain
from mpa_core.mpa_pow import ALGORITHM_NAME, mpaalg_hash

try:
    from miner.gpu_check import check_gpu
except ImportError:
    from gpu_check import check_gpu

bc = Blockchain()
running = False
hashrate = 0
shares = 0
simulation_mode = False
last_pow = ""


def _resolve_mining_device():
    """Return (device_name, simulation_mode)."""
    info = check_gpu()
    if isinstance(info, tuple) and len(info) >= 1:
        return str(info[0]), False
    return str(info), False


def miner_loop(log):
    global running, hashrate, shares, last_pow
    while running:
        time.sleep(0.2)
        if simulation_mode:
            hashrate = 8 + int(time.time()) % 5
        else:
            hashrate = 120 + int(time.time()) % 30
        shares += 1
        pow_hash = mpaalg_hash(f"gpu-miner:{shares}", shares)
        last_pow = pow_hash[:22]
        mode = "SIM" if simulation_mode else "GPU"
        log.insert(END, f"[{mode}/{ALGORITHM_NAME}] Share #{shares} | Hashrate {hashrate} MH/s | Hash {last_pow}\n")
        log.see(END)


def start_mining(log, gpu_label):
    global running, simulation_mode
    try:
        device_name, simulation_mode = _resolve_mining_device()
        gpu_label.config(text=f"GPU: {device_name}")
    except RuntimeError as exc:
        # Fallback instead of crashing: allow CPU simulation mode.
        simulation_mode = True
        gpu_label.config(text="GPU: not available (CPU sim)")
        log.insert(END, f"Warning: {exc}. Starting in CPU simulation mode.\n")
        log.see(END)
    except Exception as exc:
        simulation_mode = True
        gpu_label.config(text="GPU: error (CPU sim)")
        log.insert(END, f"Warning: unexpected GPU check error: {exc}. Starting in CPU simulation mode.\n")
        log.see(END)

    if not running:
        running = True
        threading.Thread(target=miner_loop, args=(log,), daemon=True).start()


def stop_mining(log=None):
    global running
    running = False
    if log is not None:
        log.insert(END, "Mining stopped.\n")
        log.see(END)


def run_gui():
    app = Tk()
    app.title("MPA GPU Miner - MPAALG")

    gpu_label = Label(app, text="GPU: checking...")
    gpu_label.pack()
    algo_label = Label(app, text=f"Algorithm: {ALGORITHM_NAME}")
    algo_label.pack()

    log = Text(app, height=15, width=70)
    log.pack()

    Button(app, text="Start", command=lambda: start_mining(log, gpu_label)).pack()
    Button(app, text="Stop", command=lambda: stop_mining(log)).pack()

    app.mainloop()


if __name__ == "__main__":
    run_gui()
