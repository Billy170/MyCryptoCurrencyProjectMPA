import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tkinter import *
from core.mpa_crypto import create_wallet, sign_transaction

sk, vk = create_wallet()

def make_tx():
    tx = {"sender":sender.get(),"receiver":receiver.get(),"amount":float(amount.get()),"nonce":nonce.get(),"coin":"MPA"}
    sig = sign_transaction(sk, tx)
    output.delete("1.0",END)
    output.insert(END,f"TX: {tx}\nSignature: {sig.hex()}")

app = Tk(); app.title("MPA Wallet")
Label(app,text="Sender").pack(); sender=Entry(app); sender.pack()
Label(app,text="Receiver").pack(); receiver=Entry(app); receiver.pack()
Label(app,text="Amount").pack(); amount=Entry(app); amount.pack()
Label(app,text="Nonce").pack(); nonce=Entry(app); nonce.pack()
Button(app,text="Sign TX",command=make_tx).pack()
output=Text(app,height=10); output.pack()
app.mainloop()
