import json
import os
from typing import Any
from urllib.request import urlopen

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_ROOT, ".mpa_state", "network_chain_state.json")
POOL_API_BASE = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334")


def _genesis_block() -> dict[str, Any]:
    return {
        "index": 0,
        "prev_hash": "0" * 64,
        "hash": "0" * 64,
        "transactions": [],
        "timestamp": 0.0,
        "nonce": 0,
        "difficulty": 0,
        "miner": "GENESIS",
    }


def _read_state_file() -> list[dict[str, Any]]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return []

    chain = payload.get("chain") if isinstance(payload, dict) else None
    if not isinstance(chain, list) or not chain:
        return []
    return chain


def get_live_chain() -> list[dict[str, Any]]:
    """Return latest full chain from shared state; fallback to pool summaries when needed."""
    chain = _read_state_file()
    if chain:
        return chain

    try:
        with urlopen(f"{POOL_API_BASE}/api/chain", timeout=1.5) as resp:
            payload = json.loads(resp.read().decode())
            blocks = payload.get("blocks", [])
            if isinstance(blocks, list) and blocks:
                return blocks
    except Exception:
        pass

    return [_genesis_block()]


def write_chain(chain: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    payload = {"chain": chain, "sync": {"latest_block": max(0, len(chain) - 1)}}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)
