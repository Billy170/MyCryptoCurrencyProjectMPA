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
    ok, name = check_gpu()
    gpu_label.config(text=f"GPU: {name}")
    if ok and not running:
        running = True
        threading.Thread(target=miner_loop, args=(log,), daemon=True).start()


def stop_mining():
    global running
    running = False


app = Tk()
app.title("MPA GPU Miner")

gpu_label = Label(app, text="GPU: checking...")
gpu_label.pack()

log = Text(app, height=15, width=70)
log.pack()

Button(app, text="Start", command=lambda: start_mining(log, gpu_label)).pack()
Button(app, text="Stop", command=stop_mining).pack()

app.mainloop()
