import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from core.mpa_blockchain import Blockchain

app = FastAPI()
bc = Blockchain()


@app.get("/blocks")
def blocks():
    return bc.chain


@app.get("/balance/{address}")
def balance(address: str):
    bal = 0
    for b in bc.chain:
        for tx in b["transactions"]:
            if tx["receiver"] == address:
                bal += tx["amount"]
            if tx["sender"] == address:
                bal -= tx["amount"]
    return {"address": address, "balance": bal, "coin": "MPA"}
