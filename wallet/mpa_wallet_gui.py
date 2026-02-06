from tkinter import *
from core.mpa_crypto import create_wallet, sign_transaction

sk, vk = create_wallet()

root = Tk()
root.title("MPA Wallet GUI")
root.geometry("400x200")

Label(root, text="MPA Wallet").pack(pady=10)
address_var = StringVar(value=str(vk.to_string().hex()))
Entry(root, textvariable=address_var, width=60).pack()

root.mainloop()
