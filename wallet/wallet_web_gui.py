import json
import os
import re
import sys
import time
from urllib.request import Request, urlopen

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for
from mpa_core.mpa_crypto import create_wallet, sign_transaction

app = Flask(__name__)
app.secret_key = os.environ.get("MPA_WALLET_SECRET", "dev-wallet-secret")
POOL_API = os.environ.get("MPA_POOL_API_URL", "http://127.0.0.1:3334")
sk, vk = create_wallet()

STATE_DIR = os.path.join(PROJECT_ROOT, ".mpa_state")
os.makedirs(STATE_DIR, exist_ok=True)
WALLET_STATE_FILE = os.path.join(STATE_DIR, "wallet_blocks.json")


def _api_post(path: str, payload: dict):
    req = Request(
        f"{POOL_API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=2) as resp:
        return json.loads(resp.read().decode()), resp.getcode()


def _sync_network(role: str, node_id: str, last_block: int):
    payload = {"role": role, "node_id": node_id, "last_block": int(last_block)}
    req = Request(
        f"{POOL_API}/api/sync",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=1.5):
        pass


def get_wallet_balance(address: str) -> float:
    try:
        with urlopen(f"{POOL_API}/api/wallet/{address}", timeout=1.2) as resp:
            data = json.loads(resp.read().decode())
        return float(data.get("balance", 0.0))
    except Exception:
        return 0.0


def _load_wallet_blocks() -> dict:
    try:
        with open(WALLET_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_wallet_blocks(data: dict):
    try:
        with open(WALLET_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _wallet_chain_file(wallet_address: str) -> str:
    safe_wallet = re.sub(r"[^a-zA-Z0-9_-]", "_", wallet_address or "unknown")
    return os.path.join(STATE_DIR, f"wallet_chain_{safe_wallet}.json")


def _download_blockchain_for_wallet(wallet_address: str) -> dict:
    if not wallet_address:
        return {"ok": False, "error": "wallet address missing", "downloaded": 0, "chain_height": 0}

    try:
        with urlopen(f"{POOL_API}/api/chain", timeout=2.0) as resp:
            chain_data = json.loads(resp.read().decode())
        blocks = chain_data.get("blocks", [])
        if not isinstance(blocks, list):
            blocks = []

        full_chain = []
        for block in blocks:
            idx = int(block.get("index", 0))
            with urlopen(f"{POOL_API}/api/block/{idx}", timeout=2.0) as resp:
                detail = json.loads(resp.read().decode())
            if detail.get("ok") and isinstance(detail.get("block"), dict):
                full_chain.append(detail["block"])

        if not full_chain:
            return {"ok": False, "error": "could not download blockchain", "downloaded": 0, "chain_height": 0}

        with open(_wallet_chain_file(wallet_address), "w", encoding="utf-8") as f:
            json.dump({"wallet": wallet_address, "chain": full_chain, "synced_at": time.time()}, f)

        wallet_blocks = _load_wallet_blocks()
        wallet_blocks[wallet_address] = {
            "height": len(full_chain),
            "updated_at": time.time(),
            "last_hash": full_chain[-1].get("hash", ""),
        }
        _save_wallet_blocks(wallet_blocks)

        try:
            _sync_network("wallet", wallet_address, len(full_chain))
        except Exception:
            pass

        return {"ok": True, "downloaded": len(full_chain), "chain_height": len(full_chain), "last_hash": full_chain[-1].get("hash", "")}
    except Exception as exc:
        fallback = _load_wallet_blocks().get(wallet_address, {})
        return {
            "ok": False,
            "error": str(exc),
            "downloaded": int(fallback.get("height", 0) or 0),
            "chain_height": int(fallback.get("height", 0) or 0),
            "offline": True,
        }


def get_chain_height(wallet_address: str) -> int:
    info = _load_wallet_blocks().get(wallet_address or "", {})
    if isinstance(info, dict):
        return int(info.get("height", 0) or 0)
    return int(info or 0)


def build_tx(sender_value: str, receiver_value: str, amount_raw: str, nonce_value: str):
    sender_value = sender_value.strip()
    receiver_value = receiver_value.strip()
    nonce_value = nonce_value.strip()
    amount_raw = amount_raw.strip()

    if not sender_value or not receiver_value or not nonce_value or not amount_raw:
        raise ValueError("sender, receiver, amount, and nonce are required")

    try:
        amount_value = float(amount_raw)
    except ValueError as exc:
        raise ValueError(f"invalid amount '{amount_raw}'. Enter a number") from exc

    return {
        "sender": sender_value,
        "receiver": receiver_value,
        "amount": amount_value,
        "nonce": nonce_value,
        "coin": "MPA",
    }


AUTH_TPL = """
<!doctype html>
<html>
<head><meta charset="utf-8" /><title>MPA Wallet Sign In</title>
<style>
body { font-family: Arial; background:#0f172a; color:#e2e8f0; margin:0; }
.container { max-width:700px; margin:0 auto; padding:20px; }
.panel { background:#111827; border-radius:12px; padding:16px; margin-bottom:12px; }
label { display:block; margin:8px 0 4px; color:#93c5fd; }
input { width:100%; padding:10px; border-radius:8px; border:1px solid #334155; background:#0b1220; color:#e2e8f0; }
button { margin-top:10px; background:#2563eb; color:white; border:0; padding:10px 14px; border-radius:8px; cursor:pointer; }
.err { color:#fca5a5; }
</style>
</head>
<body>
<div class="container">
  <h1>MPA Wallet</h1>
  {% if error %}<div class="panel err">{{ error }}</div>{% endif %}
  <div class="panel">
    <h3>Sign in</h3>
    <form method="post" action="/login">
      <label>Email</label><input name="email" value="{{ email }}" />
      <label>Password</label><input type="password" name="password" />
      <button type="submit">Sign in</button>
    </form>
  </div>
  <div class="panel">
    <h3>Create wallet</h3>
    <form method="post" action="/register">
      <label>Email</label><input name="email" value="{{ email }}" />
      <label>Password</label><input type="password" name="password" />
      <button type="submit">Register</button>
    </form>
  </div>
</div>
</body>
</html>
"""

WALLET_TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>MPA Wallet Web GUI</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; }
    .container { max-width: 760px; margin: 0 auto; padding: 20px; }
    .panel { background:#111827; border-radius:12px; padding:16px; margin-bottom:12px; }
    label { display:block; margin:8px 0 4px; color:#93c5fd; }
    input { width:100%; padding:10px; border-radius:8px; border:1px solid #334155; background:#0b1220; color:#e2e8f0; }
    button { margin-top:12px; background:#2563eb; color:#fff; border:0; border-radius:8px; padding:10px 14px; cursor:pointer; }
    pre { white-space:pre-wrap; word-break:break-word; background:#0b1220; padding:10px; border-radius:8px; }
    .err { color:#fca5a5; }
    .ok { color:#34d399; }
    .overlay {
      position: fixed; inset:0; background: rgba(2, 6, 23, 0.9); z-index:9999;
      display:flex; align-items:center; justify-content:center; flex-direction:column; gap:12px;
    }
    .spinner {
      width:58px; height:58px; border-radius:50%; border:5px solid #1e293b; border-top-color:#38bdf8;
      animation: spin 1s linear infinite;
    }
    .pulse-bar {
      width:260px; height:8px; background:#1e293b; border-radius:999px; overflow:hidden;
    }
    .pulse-bar::after {
      content:""; display:block; width:45%; height:100%; background:#2563eb;
      animation: pulse 1.4s ease-in-out infinite;
    }
    @keyframes spin { to { transform:rotate(360deg); } }
    @keyframes pulse {
      0% { transform:translateX(-120%); }
      100% { transform:translateX(260%); }
    }
    .muted { color:#93a4bf; font-size:12px; }
  </style>
</head>
<body>
  <div id="syncOverlay" class="overlay" {% if not auto_sync %}style="display:none"{% endif %}>
    <div class="spinner"></div>
    <div><strong>Downloading blockchain...</strong></div>
    <div class="pulse-bar"></div>
    <div id="syncMessage" class="muted">Syncing wallet with latest network blocks...</div>
  </div>

  <div class="container" id="walletArea">
    <h1>MPA Wallet</h1>
    <div class="panel">
      <div><strong>Email:</strong> {{ email }}</div>
      <div><strong>Wallet:</strong> {{ wallet_address }}</div>
      <div class="ok"><strong>Balance:</strong> {{ '%.4f'|format(balance) }} MPA</div>
      <div><strong>Downloaded blocks:</strong> <span id="chainHeight">{{ chain_height }}</span></div>
      <div class="muted">Blockchain sync runs on each wallet open before actions are enabled.</div>
      <a href="/logout" style="color:#93c5fd;">Logout</a>
    </div>

    <div class="panel">
      <form method="post" action="/sign" id="signForm">
        <label>Sender</label>
        <input name="sender" value="{{ sender }}" />
        <label>Receiver</label>
        <input name="receiver" value="{{ receiver }}" />
        <label>Amount</label>
        <input name="amount" value="{{ amount }}" />
        <label>Nonce</label>
        <input name="nonce" value="{{ nonce }}" />
        <button type="submit">Sign TX</button>
      </form>
    </div>

    <div class="panel">
      {% if error %}<div class="err">{{ error }}</div>{% endif %}
      {% if tx_text %}<pre>{{ tx_text }}</pre>{% endif %}
    </div>
  </div>

  <script>
    async function runWalletSync() {
      const overlay = document.getElementById('syncOverlay');
      const msg = document.getElementById('syncMessage');
      try {
        const response = await fetch('/api/wallet/sync', { method: 'POST' });
        const data = await response.json();
        if (data.ok) {
          msg.textContent = `Blockchain synced: ${data.chain_height} blocks downloaded.`;
          const ch = document.getElementById('chainHeight');
          if (ch) ch.textContent = data.chain_height;
        } else {
          msg.textContent = `Sync warning: ${data.error || 'network unavailable'}`;
        }
      } catch (e) {
        msg.textContent = 'Sync warning: unable to contact pool API.';
      }
      setTimeout(() => { overlay.style.display = 'none'; }, 700);
    }

    {% if auto_sync %}
    runWalletSync();
    {% endif %}
  </script>
</body>
</html>
"""


def _session_wallet():
    return session.get("wallet_address", "")


def _session_email():
    return session.get("email", "")


def render_auth(error: str = "", email: str = ""):
    return render_template_string(AUTH_TPL, error=error, email=email)


def render_wallet(**kwargs):
    wallet = _session_wallet()
    defaults = {
        "email": _session_email(),
        "wallet_address": wallet,
        "balance": get_wallet_balance(wallet),
        "chain_height": get_chain_height(wallet),
        "sender": wallet,
        "receiver": "",
        "amount": "",
        "nonce": "",
        "error": "",
        "tx_text": "",
        "auto_sync": bool(request.args.get("sync", "1") == "1"),
    }
    defaults.update(kwargs)
    return render_template_string(WALLET_TPL, **defaults)


@app.get("/")
def home():
    if not _session_wallet():
        return render_auth()
    return render_wallet()


@app.post("/register")
def register():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        return render_auth("email and password are required", email)
    try:
        data, _ = _api_post("/api/register_wallet", {"email": email, "password": password})
        if not data.get("ok"):
            return render_auth(data.get("error", "register failed"), email)
        session["email"] = data["email"]
        session["wallet_address"] = data["wallet"]
        return redirect(url_for("home"))
    except Exception as exc:
        return render_auth(f"register error: {exc}", email)


@app.post("/login")
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        return render_auth("email and password are required", email)
    try:
        data, _ = _api_post("/api/login_wallet", {"email": email, "password": password})
        if not data.get("ok"):
            return render_auth(data.get("error", "login failed"), email)
        session["email"] = data["email"]
        session["wallet_address"] = data["wallet"]
        return redirect(url_for("home"))
    except Exception as exc:
        return render_auth(f"login error: {exc}", email)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.post("/sign")
def sign():
    if not _session_wallet():
        return redirect(url_for("home"))

    sender = request.form.get("sender", "")
    receiver = request.form.get("receiver", "")
    amount = request.form.get("amount", "")
    nonce = request.form.get("nonce", "")

    try:
        tx = build_tx(sender, receiver, amount, nonce)
        sig = sign_transaction(sk, tx).hex()
        return render_wallet(
            sender=sender,
            receiver=receiver,
            amount=amount,
            nonce=nonce,
            tx_text=f"TX: {tx}\nSignature: {sig}",
            auto_sync=False,
        )
    except ValueError as exc:
        return render_wallet(
            sender=sender,
            receiver=receiver,
            amount=amount,
            nonce=nonce,
            error=f"Error: {exc}",
            auto_sync=False,
        )


@app.post("/api/wallet/sync")
def wallet_sync_api():
    wallet = _session_wallet()
    if not wallet:
        return jsonify({"ok": False, "error": "not authenticated"}), 401
    result = _download_blockchain_for_wallet(wallet)
    return jsonify(result)


@app.get("/api/pubkey")
def pubkey_api():
    return jsonify({"public_key": vk.to_string().hex(), "wallet_address": _session_wallet()})


@app.get("/api/wallet")
def wallet_api():
    wallet = _session_wallet()
    return jsonify({"wallet": wallet, "balance": get_wallet_balance(wallet), "coin": "MPA"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8070)
