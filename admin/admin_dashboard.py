import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask

from mpa_core.mpa_blockchain import Blockchain
from pool.mpa_pool_server import miners, wallet_balances

app = Flask(__name__)
bc = Blockchain()


def total_hashrate() -> int:
    """Estimate total hashrate from active miners state."""
    # Pool server tracks shares/difficulty only for now; expose a conservative
    # synthetic metric for dashboard compatibility.
    return sum(m.get("shares", 0) for m in miners.values())


def total_shares() -> int:
    return sum(m.get("shares", 0) for m in miners.values())


@app.route("/admin")
def admin():
    return {
        "blocks": len(bc.chain),
        "difficulty": bc.difficulty,
        "miners": list(miners),
        "balances": wallet_balances,
        "hashrate": total_hashrate(),
        "shares": total_shares(),
    }


if __name__ == "__main__":
    app.run(port=9000)
