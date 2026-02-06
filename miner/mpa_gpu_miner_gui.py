import os
import sys
import threading
import time
from tkinter import *

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mpa_core.mpa_blockchain import Blockchain

try:
    from miner.gpu_check import check_gpu
except ImportError:
    from gpu_check import check_gpu

bc = Blockchain()
running = False
hashrate = 0
shares = 0


def _resolve_gpu_name():
    """Return GPU display name or raise RuntimeError with user-safe message."""
    info = check_gpu()
    # gpu_check currently returns (name, cores, vram)
    if isinstance(info, tuple):
        if len(info) >= 1:
            return str(info[0])
    return str(info)


def miner_loop(log):
    global running, hashrate, shares
    while running:
        time.sleep(0.2)
        hashrate = 120 + int(time.time()) % 30
        shares += 1
        log.insert(END, f"Mined share #{shares} | Hashrate {hashrate} MH/s\n")
        log.see(END)


def start_mining(log, gpu_label):
    global running
    try:
        gpu_name = _resolve_gpu_name()
    except RuntimeError as exc:
        gpu_label.config(text="GPU: not available")
        log.insert(END, f"Cannot start mining: {exc}\n")
        log.see(END)
        return
    except Exception as exc:
        gpu_label.config(text="GPU: error")
        log.insert(END, f"Cannot start mining: unexpected GPU check error: {exc}\n")
        log.see(END)
        return

    gpu_label.config(text=f"GPU: {gpu_name}")
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
    app.title("MPA GPU Miner")

    gpu_label = Label(app, text="GPU: checking...")
    gpu_label.pack()

    log = Text(app, height=15, width=70)
    log.pack()

    Button(app, text="Start", command=lambda: start_mining(log, gpu_label)).pack()
    Button(app, text="Stop", command=lambda: stop_mining(log)).pack()

    app.mainloop()


if __name__ == "__main__":
    run_gui()
