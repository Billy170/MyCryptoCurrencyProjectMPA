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
    with urlopen(req, timeout=6) as resp:
        return json.loads(resp.read().decode()), resp.getcode()


def _sync_network(role: str, node_id: str, last_block: int):
    payload = {"role": role, "node_id": node_id, "last_block": int(last_block)}
    req = Request(
        f"{POOL_API}/api/sync",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=4):
        pass


def get_wallet_balance(address: str) -> float:
    try:
        with urlopen(f"{POOL_API}/api/wallet/{address}", timeout=4.0) as resp:
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


def _load_local_chain(wallet_address: str) -> list:
    try:
        with open(_wallet_chain_file(wallet_address), "r", encoding="utf-8") as f:
            data = json.load(f)
        chain = data.get("chain", []) if isinstance(data, dict) else []
        return chain if isinstance(chain, list) else []
    except Exception:
        return []


def _save_local_chain(wallet_address: str, chain: list):
    with open(_wallet_chain_file(wallet_address), "w", encoding="utf-8") as f:
        json.dump({"wallet": wallet_address, "chain": chain, "synced_at": time.time()}, f)


def _fetch_remote_chain_summaries() -> list:
    with urlopen(f"{POOL_API}/api/chain", timeout=4.0) as resp:
        chain_data = json.loads(resp.read().decode())
    blocks = chain_data.get("blocks", [])
    return blocks if isinstance(blocks, list) else []


def _fetch_blocks_range(start: int, limit: int = 25) -> tuple[list, int]:
    with urlopen(f"{POOL_API}/api/blocks?start={int(start)}&limit={int(limit)}", timeout=5.0) as resp:
        payload = json.loads(resp.read().decode())
    blocks = payload.get("blocks", []) if isinstance(payload, dict) else []
    total = int(payload.get("total", 0) or 0) if isinstance(payload, dict) else 0
    return (blocks if isinstance(blocks, list) else []), total


def _update_wallet_meta(wallet_address: str, chain: list):
    wallet_blocks = _load_wallet_blocks()
    wallet_blocks[wallet_address] = {
        "height": len(chain),
        "updated_at": time.time(),
        "last_hash": chain[-1].get("hash", "") if chain else "",
    }
    _save_wallet_blocks(wallet_blocks)
    try:
        _sync_network("wallet", wallet_address, len(chain))
    except Exception:
        pass


def _prepare_chain(wallet_address: str):
    remote = _fetch_remote_chain_summaries()
    local = _load_local_chain(wallet_address)

    if len(local) > len(remote):
        local = local[: len(remote)]

    mismatch = None
    for idx in range(len(local)):
        local_hash = str((local[idx] or {}).get("hash", ""))
        remote_hash = str((remote[idx] or {}).get("hash", ""))
        if local_hash and remote_hash and local_hash != remote_hash:
            mismatch = idx
            break
    if mismatch is not None:
        local = local[:mismatch]

    return local, remote


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
    .overlay { position: fixed; inset:0; background: rgba(2,6,23,.92); z-index:9999; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:12px; }
    .spinner { width:58px; height:58px; border-radius:50%; border:5px solid #1e293b; border-top-color:#38bdf8; animation: spin 1s linear infinite; }
    .progress-wrap { width:300px; }
    .progress-text { display:flex; justify-content:space-between; font-size:12px; color:#93a4bf; margin-bottom:4px; }
    .progress-bg { width:100%; height:10px; border-radius:999px; overflow:hidden; background:#1e293b; }
    .progress-fill { height:100%; width:0%; background:#2563eb; transition: width .2s ease; }
    .muted { color:#93a4bf; font-size:12px; }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div id="syncOverlay" class="overlay" {% if not auto_sync %}style="display:none"{% endif %}>
    <div class="spinner"></div>
    <div><strong>Downloading blockchain...</strong></div>
    <div class="progress-wrap">
      <div class="progress-text">
        <span id="syncDownloaded">0</span>
        <span id="syncRemaining">remaining: 0</span>
      </div>
      <div class="progress-bg"><div id="syncProgress" class="progress-fill"></div></div>
    </div>
    <div id="syncMessage" class="muted">Preparing sync...</div>
  </div>

  <div class="container">
    <h1>MPA Wallet</h1>
    <div class="panel">
      <div><strong>Email:</strong> {{ email }}</div>
      <div><strong>Wallet:</strong> {{ wallet_address }}</div>
      <div class="ok"><strong>Balance:</strong> {{ '%.4f'|format(balance) }} MPA</div>
      <div><strong>Downloaded blocks:</strong> <span id="chainHeight">{{ chain_height }}</span></div>
      <div class="muted">On each open, wallet syncs only missing blocks.</div>
      <a href="/logout" style="color:#93c5fd;">Logout</a>
    </div>

    <div class="panel">
      <h3>Quick Send MPA</h3>
      <form method="post" action="/quick_send">
        <label>Receiver wallet</label>
        <input name="quick_receiver" value="{{ quick_receiver }}" placeholder="MPA-..." />
        <label>Amount (MPA)</label>
        <input name="quick_amount" value="{{ quick_amount }}" placeholder="0.01" />
        <button type="submit">Send</button>
      </form>
      {% if quick_error %}<div class="err" style="margin-top:8px;">{{ quick_error }}</div>{% endif %}
      {% if quick_ok %}<div class="ok" style="margin-top:8px;">{{ quick_ok }}</div>{% endif %}
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
    function updateProgress(downloaded, total) {
      const remaining = Math.max(0, total - downloaded);
      document.getElementById('syncDownloaded').textContent = `downloaded: ${downloaded}/${total}`;
      document.getElementById('syncRemaining').textContent = `remaining: ${remaining}`;
      const pct = total > 0 ? Math.min(100, Math.round((downloaded / total) * 100)) : 100;
      document.getElementById('syncProgress').style.width = `${pct}%`;
    }

    async function runWalletSync() {
      const overlay = document.getElementById('syncOverlay');
      const msg = document.getElementById('syncMessage');
      try {
        const planRes = await fetch('/api/wallet/sync_plan');
        const plan = await planRes.json();
        let total = plan.total_blocks || 0;
        let downloaded = plan.local_blocks || 0;
        updateProgress(downloaded, total);
        msg.textContent = `Need ${plan.missing_blocks || 0} missing blocks.`;

        let remaining = plan.remaining_blocks || 0;
        while (remaining > 0 || downloaded < total) {
          const stepRes = await fetch('/api/wallet/sync_step', { method: 'POST' });
          const step = await stepRes.json();
          total = step.total_blocks || total;
          downloaded = step.local_blocks || downloaded;
          updateProgress(downloaded, total);
          msg.textContent = step.message || 'Syncing blocks...';
          remaining = step.remaining_blocks || 0;
          if (!step.ok || remaining <= 0) break;
        }

        document.getElementById('chainHeight').textContent = downloaded;
      } catch (e) {
        msg.textContent = 'Sync warning: unable to contact pool API.';
      }
      setTimeout(() => { overlay.style.display = 'none'; }, 600);
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
        "quick_receiver": "",
        "quick_amount": "",
        "quick_error": "",
        "quick_ok": "",
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


@app.post("/quick_send")
def quick_send():
    wallet = _session_wallet()
    if not wallet:
        return redirect(url_for("home"))

    receiver = request.form.get("quick_receiver", "").strip()
    amount_raw = request.form.get("quick_amount", "").strip()
    if not receiver or not amount_raw:
        return render_wallet(quick_receiver=receiver, quick_amount=amount_raw, quick_error="receiver and amount are required", auto_sync=False)

    try:
        amount = float(amount_raw)
    except ValueError:
        return render_wallet(quick_receiver=receiver, quick_amount=amount_raw, quick_error="enter a valid amount", auto_sync=False)

    if amount <= 0:
        return render_wallet(quick_receiver=receiver, quick_amount=amount_raw, quick_error="amount must be > 0", auto_sync=False)

    try:
        data, _ = _api_post("/api/transfer_wallet", {"sender": wallet, "receiver": receiver, "amount": amount})
    except Exception as exc:
        return render_wallet(quick_receiver=receiver, quick_amount=amount_raw, quick_error=f"send error: {exc}", auto_sync=False)

    if not data.get("ok"):
        return render_wallet(quick_receiver=receiver, quick_amount=amount_raw, quick_error=data.get("error", "send failed"), auto_sync=False)

    return render_wallet(quick_ok=f"Sent {amount:.4f} MPA to {receiver}", auto_sync=False)


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


@app.get("/api/wallet/sync_plan")
def wallet_sync_plan_api():
    wallet = _session_wallet()
    if not wallet:
        return jsonify({"ok": False, "error": "not authenticated"}), 401
    try:
        local, remote = _prepare_chain(wallet)
        _save_local_chain(wallet, local)
        _update_wallet_meta(wallet, local)
        return jsonify({
            "ok": True,
            "local_blocks": len(local),
            "total_blocks": len(remote),
            "missing_blocks": max(0, len(remote) - len(local)),
            "remaining_blocks": max(0, len(remote) - len(local)),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.post("/api/wallet/sync_step")
def wallet_sync_step_api():
    wallet = _session_wallet()
    if not wallet:
        return jsonify({"ok": False, "error": "not authenticated"}), 401

    try:
        local, remote = _prepare_chain(wallet)
        total = len(remote)
        if len(local) >= total:
            _save_local_chain(wallet, local)
            _update_wallet_meta(wallet, local)
            return jsonify({
                "ok": True,
                "message": "Blockchain is already up to date.",
                "local_blocks": len(local),
                "total_blocks": total,
                "remaining_blocks": 0,
            })

        start = len(local)
        fetched, range_total = _fetch_blocks_range(start=start, limit=25)
        if not fetched:
            return jsonify({"ok": False, "error": f"failed to fetch missing blocks from {start}", "local_blocks": len(local), "total_blocks": total, "remaining_blocks": total - len(local)}), 502

        local.extend([b for b in fetched if isinstance(b, dict)])
        _save_local_chain(wallet, local)
        _update_wallet_meta(wallet, local)

        total = max(total, range_total)
        remaining = max(0, total - len(local))
        return jsonify({
            "ok": True,
            "message": f"Downloaded {len(fetched)} block(s).",
            "local_blocks": len(local),
            "total_blocks": total,
            "remaining_blocks": remaining,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.get("/api/pubkey")
def pubkey_api():
    return jsonify({"public_key": vk.to_string().hex(), "wallet_address": _session_wallet()})


@app.get("/api/wallet")
def wallet_api():
    wallet = _session_wallet()
    return jsonify({"wallet": wallet, "balance": get_wallet_balance(wallet), "coin": "MPA"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8070)
