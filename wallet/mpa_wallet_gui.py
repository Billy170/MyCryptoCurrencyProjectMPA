import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tkinter import *
from mpa_core.mpa_crypto import create_wallet, sign_transaction

sk, vk = create_wallet()


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


def make_tx():
    output.delete("1.0", END)
    try:
        tx = build_tx(sender.get(), receiver.get(), amount.get(), nonce.get())
    except ValueError as exc:
        output.insert(END, f"Error: {exc}.\n")
        return

    sig = sign_transaction(sk, tx)
    output.insert(END, f"TX: {tx}\nSignature: {sig.hex()}")


def run_wallet_gui():
    global app, sender, receiver, amount, nonce, output
    app = Tk()
    app.title("MPA Wallet")
    Label(app, text="Sender").pack()
    sender = Entry(app)
    sender.pack()
    Label(app, text="Receiver").pack()
    receiver = Entry(app)
    receiver.pack()
    Label(app, text="Amount").pack()
    amount = Entry(app)
    amount.pack()
    Label(app, text="Nonce").pack()
    nonce = Entry(app)
    nonce.pack()
    Button(app, text="Sign TX", command=make_tx).pack()
    output = Text(app, height=10)
    output.pack()
    app.mainloop()


if __name__ == "__main__":
    run_wallet_gui()
