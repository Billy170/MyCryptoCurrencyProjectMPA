import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, render_template_string, request
from mpa_core.mpa_crypto import create_wallet, sign_transaction

app = Flask(__name__)
sk, vk = create_wallet()


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


TPL = """
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
    a { color:#93c5fd; }
  </style>
</head>
<body>
  <div class="container">
    <h1>MPA Wallet Web GUI</h1>
    <p><a href="/api/pubkey">Public key API</a></p>
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
</body>
</html>
"""


def render_form(**kwargs):
    defaults = {
        "sender": "",
        "receiver": "",
        "amount": "",
        "nonce": "",
        "error": "",
        "tx_text": "",
    }
    defaults.update(kwargs)
    return render_template_string(TPL, **defaults)


@app.get("/")
def home():
    return render_form()


@app.post("/sign")
def sign():
    sender = request.form.get("sender", "")
    receiver = request.form.get("receiver", "")
    amount = request.form.get("amount", "")
    nonce = request.form.get("nonce", "")

    try:
        tx = build_tx(sender, receiver, amount, nonce)
        sig = sign_transaction(sk, tx).hex()
        return render_form(
            sender=sender,
            receiver=receiver,
            amount=amount,
            nonce=nonce,
            tx_text=f"TX: {tx}\nSignature: {sig}",
        )
    except ValueError as exc:
        return render_form(
            sender=sender,
            receiver=receiver,
            amount=amount,
            nonce=nonce,
            error=f"Error: {exc}",
        )


@app.get("/api/pubkey")
def pubkey_api():
    return jsonify({"public_key": vk.to_string().hex()})


if __name__ == "__main__":
    app.run(port=8070)
