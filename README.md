# MPA Coin — Complete Local Crypto Stack

Το **MPA Coin** είναι ένα πλήρες local-first demo crypto project με:
- blockchain core,
- P2P node,
- pool server + pool web GUI,
- wallet web GUI,
- miner web GUI (CPU mode),
- explorer,
- και **κεντρικό one-tab control center** για διαχείριση όλων των services.

---

## ✨ Βασικά χαρακτηριστικά

- **Central Web GUI** (port `8060`) για εκκίνηση/παύση υπηρεσιών και miners.
- **P2P Node** (port `5000`) ενσωματωμένο στη ροή εκκίνησης.
- **Pool Server** (TCP `3333`, API `3334`) με wallet registration/login και balance APIs.
- **Wallet Web GUI** (port `8070`) για login/register wallet και υπογραφή TX.
- **Pool Web GUI** (port `8080`) για παρακολούθηση pool κατάστασης.
- **Explorer** (port `8050`) για οπτική παρακολούθηση chain.
- **Miner Web GUI(s)** (default από `8090` και πάνω) με start/stop mining.
- **Quick Send MPA** από το central GUI με μόνο:
  - wallet address παραλήπτη
  - ποσό (MPA)

---

## 🧱 Αρχιτεκτονική (γρήγορη εικόνα)

- `launcher/central_web_gui.py` → ενοποιημένος πίνακας ελέγχου για όλα.
- `pool/mpa_pool_server.py` → βασικός pool server + API για wallets/chain/transfer.
- `wallet/wallet_web_gui.py` → wallet interface για χρήστη.
- `miner/miner_web_gui.py` → miner interface και mining loop.
- `p2p/node.py` → απλό P2P node endpoint για peers/blocks.
- `launcher/mpa_launcher.py` → one-click launcher από terminal.

---

## ✅ Προαπαιτούμενα

- Python **3.10+**
- Linux/macOS shell (για scripts/launcher)
- Ενεργό virtual environment (προτείνεται)

---

## 🚀 Εγκατάσταση

1. Clone το repository.
2. (Προαιρετικά) Δημιούργησε virtualenv.
3. Εγκατάστησε dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

> Το `-e .` (editable install) βοηθά να λύνουν σωστά τα imports του project.

---

## ▶️ Εκκίνηση εφαρμογής

### Επιλογή Α: Central Control Center (προτείνεται)

```bash
python launcher/central_web_gui.py
```

Μετά άνοιξε:
- `http://127.0.0.1:8060`

Από εκεί μπορείς:
- **Start / Refresh All**
- **Stop All**
- να ορίσεις πόσα miners θες,
- να κάνεις **Start/Stop κάθε miner** ξεχωριστά,
- να κάνεις **Quick Send MPA** με receiver + amount.

### Επιλογή Β: One-click launcher από terminal

```bash
python launcher/mpa_launcher.py
```

---

## 🌐 Default ports

- Central GUI: `8060`
- Explorer: `8050`
- Wallet GUI: `8070`
- Pool GUI: `8080`
- Pool TCP: `3333`
- Pool API: `3334`
- P2P node: `5000`
- Miner GUI base: `8090` (και `8091`, `8092`, ...)

---

## 💸 Quick Send MPA (νέο flow)

Στο κεντρικό GUI υπάρχει φόρμα **Quick Send MPA** που απαιτεί μόνο:
1. `Wallet address` (receiver)
2. `Amount`

Εσωτερικά χρησιμοποιείται API call προς pool (`/api/transfer_simple`) και ενημερώνεται άμεσα το balance του receiver.

---

## 🧪 Γρήγορος έλεγχος (smoke test)

```bash
python -m py_compile launcher/central_web_gui.py launcher/mpa_launcher.py pool/mpa_pool_server.py p2p/node.py
```

Αν δεν επιστρέψει error, τα βασικά modules είναι syntactically valid.

---

## 🧰 Troubleshooting

- **Port already in use**: κλείσε παλιές διεργασίες ή άλλαξε port env vars.
- **`ModuleNotFoundError`**: βεβαιώσου ότι έτρεξες `pip install -e .` στο σωστό env.
- **Miner δεν ξεκινά**: έλεγξε αν ο pool server τρέχει (`3333`/`3334`).
- **Central GUI start/stop issues**: προτίμησε να το τρέχεις με πραγματικό Python executable (όχι broken shim).

---

## 🗂️ Σύντομη δομή φακέλων

- `launcher/` → launchers + central GUI
- `pool/` → pool server + pool GUI
- `wallet/` → wallet GUIs
- `miner/` → miner GUIs
- `p2p/` → P2P node
- `explorer/` → explorer / visualization
- `mpa_core/` → blockchain / crypto core logic

---

## 📌 Σημειώσεις

- Το project είναι demo/dev friendly και τρέχει τοπικά.
- Για production setup χρειάζονται επιπλέον hardening, auth, persistence strategy και process supervision.
