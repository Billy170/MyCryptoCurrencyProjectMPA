MPA Altcoin Project
- GPU-only Ethash-style PoW
- Wallet GUI, Miner GUI
- Stratum Pool with PPLNS
- VarDiff, Auto-payouts, DB persistence
- P2P nodes
- Explorer + RPC
- Admin dashboard
- One-click launcher: python launcher/mpa_launcher.py

## Install (Python 3.12 / pip 25.x)

Base install (works without miner GPU stack):

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional (GPU miner dependencies):

```bash
python -m pip install -r requirements-gpu.txt
```

Notes:
- `requirements.txt` includes only core dependencies so app services can run on Python 3.12 without CUDA/PyTorch wheel issues.
- `requirements-gpu.txt` contains miner-specific packages and Python-version markers for better pip resolver compatibility.
- Launcher now uses the current interpreter (`sys.executable`), so running it from a Python 3.12 venv uses that same venv for all subprocesses.
