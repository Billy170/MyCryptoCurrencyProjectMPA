import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from mpa_core.live_chain import get_live_chain

app = FastAPI()


@app.get("/blocks")
def blocks():
    return get_live_chain()


@app.get("/balance/{address}")
def balance(address: str):
    bal = 0.0
    for b in get_live_chain():
        for tx in b.get("transactions", []):
            if tx.get("receiver") == address:
                bal += float(tx.get("amount", 0))
            if tx.get("sender") == address:
                bal -= float(tx.get("amount", 0))
    return {"address": address, "balance": bal, "coin": "MPA"}
