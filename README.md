# 🪙 MPA Coin — Complete Local Crypto Stack

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img alt="Flask" src="https://img.shields.io/badge/Flask-Web%20UI-000000?logo=flask&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-RPC-009688?logo=fastapi&logoColor=white" />
  <img alt="Status" src="https://img.shields.io/badge/Mode-Local%20First-2ea44f" />
</p>

<p align="center">
  <img alt="MPA architecture" src="https://img.shields.io/badge/Architecture-Pool%20%7C%20Wallet%20%7C%20Miner%20%7C%20Explorer%20%7C%20P2P-4f46e5" />
</p>

**MPA Coin** is a local-first demo crypto stack that includes:
- 🔗 blockchain core,
- 🌐 P2P node,
- 🏊 pool server + pool GUI,
- 👛 wallet web GUI,
- ⛏️ miner web GUI,
- 🧭 explorer / blockchain map,
- 🧩 central control center to start/stop all services.

---

## ✨ Features

- 🖥️ **Central Web GUI** (`:8060`) for fast orchestration of all services.
- 🪟 **Windows Desktop App** (`launcher/central_desktop_app.py`) to run the same control center in a native window (non-browser tab).
- 👛 **Wallet Web GUI** (`:8070`) with register/login, Quick Send, and blockchain sync.
- 🏊 **Pool Server** (TCP `:3333`, API `:3334`) for wallet, miner, and chain APIs.
- 🧭 **Blockchain Map Explorer** (`:8050`) with auto update / chain download.
- ⛏️ **Miner Web GUIs** (`:8090+`) that submit shares to the pool.
- 🔁 **Incremental sync** for wallet/explorer (downloads only missing blocks).

---

## 🧱 Architecture (Quick View)

```text
                ┌──────────────────────────────┐
                │  Central GUI (launcher) :8060│
                └──────────────┬───────────────┘
                               │
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
┌─────▼─────┐           ┌──────▼──────┐          ┌─────▼─────┐
│ Wallet GUI│           │ Pool Server │          │ Explorer  │
│   :8070   │◄─────────►│ TCP:3333    │◄────────►│   :8050   │
└───────────┘  API:3334 │ API:3334    │          └───────────┘
      ▲                 └──────┬──────┘                ▲
      │                        │                       │
      │                 ┌──────▼──────┐                │
      │                 │ Miner GUIs  │                │
      │                 │  :8090+     │────────────────┘
      │                 └─────────────┘
      │
┌─────▼─────┐
│ P2P Node  │
│   :5000   │
└───────────┘
```

---

## 📦 Modules

- `launcher/central_web_gui.py` → Control center (start/stop/monitor).
- `pool/mpa_pool_server.py` → Core pool + wallet/miner/chain APIs.
- `wallet/wallet_web_gui.py` → Wallet UX + quick send + chain sync.
- `miner/miner_web_gui.py` → Miner submit loop / controls.
- `explorer/blockchain_map_gui.py` → Explorer map + cached chain updates.
- `p2p/node.py` → Lightweight peer/block endpoints.
- `mpa_core/` → Blockchain + crypto primitives.

---

## ✅ Requirements

- Python **3.10+**
- pip
- Linux/macOS shell (or equivalent environment)

---

## 🚀 Installation

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

> `-e .` helps project imports resolve correctly in development mode.

---

## ▶️ Run

### Option A (recommended): Central Control Center

```bash
python launcher/central_web_gui.py
```

Then open:
- `http://127.0.0.1:8060`

### Option B: Windows desktop app (non-web tab)

```bash
python launcher/central_desktop_app.py
```

- On Windows 10/11 this opens the Control Center in a native desktop window using `pywebview`.
- If `pywebview` is not installed, it falls back to your default browser and prints install guidance.

### Option C: One-click launcher

```bash
python launcher/mpa_launcher.py
```

---

## 🌐 Ports

| Service | Port |
|---|---:|
| Central GUI | `8060` |
| Explorer | `8050` |
| Wallet GUI | `8070` |
| Pool GUI | `8080` |
| Pool TCP | `3333` |
| Pool API | `3334` |
| P2P Node | `5000` |
| Miner GUI base | `8090` |

---

## 👛 Wallet Quick Send

Quick Send is available in the Wallet UI:
1. Receiver wallet address
2. Amount (MPA)

The wallet calls the pool transfer endpoint and validates sender balance before transfer.

---

## 🧪 Quick Checks

```bash
python -m py_compile \
  launcher/central_web_gui.py \
  launcher/central_desktop_app.py \
  launcher/mpa_launcher.py \
  pool/mpa_pool_server.py \
  wallet/wallet_web_gui.py \
  explorer/blockchain_map_gui.py \
  p2p/node.py
```

---

## 🛠️ Troubleshooting

- **Port already in use** → stop old processes or change ports/env variables.
- **`ModuleNotFoundError`** → ensure you ran `pip install -e .` in the correct environment.
- **Miner issues** → verify pool is running (`3333`/`3334`).
- **Wallet sync issues** → verify `POOL_API` points to `http://127.0.0.1:3334`.

---

## 📌 Notes

- This project is demo/dev friendly and designed for local usage.
- A production setup requires additional hardening, auth policies, persistence strategy, and process supervision.
