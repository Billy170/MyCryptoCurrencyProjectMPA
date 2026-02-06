from fastapi import FastAPI
from core.mpa_blockchain import Blockchain

bc=Blockchain();app=FastAPI()
@app.get("/blocks")
def blocks(): return [b for b in bc.chain]
@app.get("/balance/{addr}")
def balance(addr): return bc.get_balance(addr)
