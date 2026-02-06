import json
import os
import sys
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


def _api_post(path: str, payload: dict):
    req = Request(
        f"{POOL_API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=2) as resp:
        return json.loads(resp.read().decode()), resp.getcode()


def get_wallet_balance(address: str) -> float:
    try:
        with urlopen(f"{POOL_API}/api/wallet/{address}", timeout=1.2) as resp:
            data = json.loads(resp.read().decode())
        return float(data.get("balance", 0.0))
    except Exception:
        return 0.0


def get_chain_height() -> int:
    try:
        with urlopen(f"{POOL_API}/api/chain", timeout=1.2) as resp:
            data = json.loads(resp.read().decode())
        return int(data.get("chain_height", 0))
    except Exception:
        return 0


def build_tx(sender_value: str, receiver_value: str, amount_raw: str, nonce_value: str):
    sender_value = sender_value.strip()
    receiver_value = receiver_value.strip()
    nonce_value = nonce_value.strip()
    amount_raw = amount_raw.strip()

    if not sender_value or not receiver_value or not nonce_value or not amount_raw:
        raise ValueError("sender, receiver, amount και nonce είναι υποχρεωτικά")

    try:
        amount_value = float(amount_raw)
    except ValueError as exc:
        raise ValueError(f"μη έγκυρο amount '{amount_raw}'. Βάλε αριθμό") from exc

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
    button { margin-top:12px; background:#2563eb; color:white; border:0; padding:10px 14px; border-radius:8px; cursor:pointer; }
    pre { white-space: pre-wrap; word-break: break-word; background:#0b1220; border-radius:8px; padding:12px; }
    .err { color:#fca5a5; }
    .ok { color:#34d399; }
    a { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Wallet Web GUI</h1>
    <p><a href="/api/pubkey">Public key API</a> · <a href="/api/wallet">Wallet API</a> · <a href="/logout">Logout</a></p>

    <div class="panel">
      <div><strong>Email:</strong> {{ email }}</div>
      <div><strong>Wallet address:</strong> {{ wallet_address }}</div>
      <div class="ok"><strong>Balance:</strong> {{ '%.4f'|format(balance) }} MPA</div>
      <div><strong>Blocks mined on network:</strong> {{ chain_height }}</div>
      <div style="font-size:12px;color:#93a4bf;">Auto-refresh every 2 seconds</div>
    </div>

    <div class="panel">
      <form method="post" action="/sign">
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
    setTimeout(() => window.location.reload(), 2000);
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
        "chain_height": get_chain_height(),
        "sender": wallet,
        "receiver": "",
        "amount": "",
        "nonce": "",
        "error": "",
        "tx_text": "",
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
        return render_auth("email και password είναι υποχρεωτικά", email)
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
        return render_auth("email και password είναι υποχρεωτικά", email)
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
        )
    except ValueError as exc:
        return render_wallet(
            sender=sender,
            receiver=receiver,
            amount=amount,
            nonce=nonce,
            error=f"Error: {exc}",
        )


@app.get("/api/pubkey")
def pubkey_api():
    return jsonify({"public_key": vk.to_string().hex(), "wallet_address": _session_wallet()})


@app.get("/api/wallet")
def wallet_api():
    wallet = _session_wallet()
    return jsonify({"wallet": wallet, "balance": get_wallet_balance(wallet), "coin": "MPA"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8070)
