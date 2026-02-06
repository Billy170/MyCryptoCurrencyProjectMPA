from tkinter import *
import threading, time
from core.mpa_blockchain import Blockchain
from gpu_check import check_gpu

bc = Blockchain()
MINER = "MPA_GPU_MINER"
running = False

def start_mining():
    global running
    try:
        name, cores, vram = check_gpu()
        lbl_gpu.config(text=f"GPU: {name} ({cores} cores, {vram} MB)")
    except Exception as e:
        lbl_gpu.config(text=str(e))
        return
    running = True
    threading.Thread(target=mine_loop, daemon=True).start()

def mine_loop():
    while running:
        bc.mine(MINER)
        lbl_mined.config(text=f"Mined: {len(bc.chain)*bc.current_reward()} MPA")
        time.sleep(1)

def stop_mining():
    global running
    running = False

root = Tk()
root.title("MPA GPU Miner")
root.geometry("350x250")
Label(root, text="MPA GPU Miner").pack(pady=10)
lbl_gpu = Label(root, text="GPU: checking...")
lbl_gpu.pack()
lbl_mined = Label(root, text="Mined: 0 MPA")
lbl_mined.pack()
Button(root, text="Start GPU Mining", command=start_mining).pack(pady=5)
Button(root, text="Stop", command=stop_mining).pack(pady=5)
root.mainloop()
