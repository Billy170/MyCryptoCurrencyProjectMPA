# MPA Coin — Complete Local Crypto Stack

**MPA Coin** is a local-first demo crypto project that includes:
- blockchain core logic,
- a P2P node,
- pool server + pool web GUI,
- wallet web GUI,
- miner web GUI (CPU mode),
- explorer,
- and a **central one-tab control center** to manage all services.

---

## ✨ Key Features

- **Central Web GUI** (port `8060`) to start/stop services and miners.
- **P2P Node** (port `5000`) integrated into the startup flow.
- **Pool Server** (TCP `3333`, API `3334`) with wallet registration/login and balance APIs.
- **Wallet Web GUI** (port `8070`) for wallet login/register and TX signing.
- **Pool Web GUI** (port `8080`) to monitor pool state.
- **Explorer** (port `8050`) for chain visualization.
- **Miner Web GUI(s)** (default from `8090` and up) with start/stop mining controls.
- **Quick Send MPA** from the central GUI with only:
  - receiver wallet address
  - amount (MPA)

---

## 🧱 Architecture (Quick View)

- `launcher/central_web_gui.py` → unified control panel for everything.
- `pool/mpa_pool_server.py` → core pool server + API for wallets/chain/transfer.
- `wallet/wallet_web_gui.py` → wallet interface for end users.
- `miner/miner_web_gui.py` → miner interface and mining loop.
- `p2p/node.py` → lightweight P2P node endpoint for peers/blocks.
- `launcher/mpa_launcher.py` → one-click launcher from terminal.

---

## ✅ Requirements

- Python **3.10+**
- Linux/macOS shell (for scripts/launcher)
- Active virtual environment (recommended)

---

## 🚀 Installation

1. Clone the repository.
2. (Optional) Create a virtual environment.
3. Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

> `-e .` (editable install) helps resolve project imports correctly during development.

---

## ▶️ Run the Application

### Option A: Central Control Center (recommended)

```bash
python launcher/central_web_gui.py
```

Then open:
- `http://127.0.0.1:8060`

From there you can:
- **Start / Refresh All**
- **Stop All**
- set how many miners you want,
- **Start/Stop each miner** individually,
- use **Quick Send MPA** with receiver + amount.

### Option B: One-click launcher from terminal

```bash
python launcher/mpa_launcher.py
```

---

## 🌐 Default Ports

- Central GUI: `8060`
- Explorer: `8050`
- Wallet GUI: `8070`
- Pool GUI: `8080`
- Pool TCP: `3333`
- Pool API: `3334`
- P2P node: `5000`
- Miner GUI base: `8090` (then `8091`, `8092`, ...)

---

## 💸 Quick Send MPA

In the central GUI, the **Quick Send MPA** form requires only:
1. `Wallet address` (receiver)
2. `Amount`

Internally it calls the pool API endpoint (`/api/transfer_simple`) and updates the receiver balance immediately.

---

## 🧪 Quick Smoke Check

```bash
python -m py_compile launcher/central_web_gui.py launcher/mpa_launcher.py pool/mpa_pool_server.py p2p/node.py
```

If no error is returned, the core modules are syntactically valid.

---

## 🧰 Troubleshooting

- **Port already in use**: stop old processes or change port environment variables.
- **`ModuleNotFoundError`**: make sure you ran `pip install -e .` in the correct environment.
- **Miner not starting**: verify the pool server is running (`3333`/`3334`).
- **Central GUI start/stop issues**: run with a real Python executable (not a broken shim).

---

## 🗂️ Project Structure (Short)

- `launcher/` → launchers + central GUI
- `pool/` → pool server + pool GUI
- `wallet/` → wallet GUIs
- `miner/` → miner GUIs
- `p2p/` → P2P node
- `explorer/` → explorer / visualization
- `mpa_core/` → blockchain / crypto core logic

---

## 📌 Notes

- The project is demo/dev friendly and runs locally.
- A production setup needs additional hardening, auth, persistence strategy, and process supervision.
