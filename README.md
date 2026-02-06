MPA Altcoin Project
- GPU-only Ethash-style PoW
- Wallet GUI, Miner GUI
- Stratum Pool with PPLNS
- VarDiff, Auto-payouts, DB persistence
- P2P nodes
- Explorer + RPC
- Admin dashboard
- One-click launcher: python launcher/mpa_launcher.py


## Environment setup
1. Upgrade pip to the requested version:
   - `python -m pip install --upgrade pip==26.0.1`
2. Install project dependencies:
   - `python -m pip install -e .`

Using editable install (`-e .`) ensures imports like `from mpa_core import Blockchain` resolve from this project instead of PyCharm trying to install an unrelated package from PyPI.
