import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import urlopen, Request

import central_web_gui

POOL_API = "http://127.0.0.1:3334"
REFRESH_MS = 2000

SERVICES = [
    ("pool", "Pool Server + GUI", 3333),
    ("p2p", "P2P Node", 5000),
    ("explorer", "Explorer", 8050),
    ("wallet", "Wallet", 8070),
]


class MPADesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MPA Desktop Control Center")
        self.root.geometry("1200x780")
        self.root.minsize(1050, 700)

        self.miner_count = tk.IntVar(value=2)
        self.wallet_email = tk.StringVar()
        self.wallet_password = tk.StringVar()
        self.wallet_address = tk.StringVar()
        self.wallet_balance = tk.StringVar(value="0.0 MPA")
        self.transfer_to = tk.StringVar()
        self.transfer_amount = tk.StringVar(value="1")
        self.system_airdrop_to = tk.StringVar()
        self.system_airdrop_amount = tk.StringVar(value="10")

        self.service_status_vars: dict[str, tk.StringVar] = {}
        self.stat_vars = {
            "chain_height": tk.StringVar(value="0"),
            "miners": tk.StringVar(value="0"),
            "hashrate": tk.StringVar(value="0"),
            "shares": tk.StringVar(value="0"),
            "total_balance": tk.StringVar(value="0"),
        }

        self._configure_style()
        self._build_ui()
        self._refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        style.configure("State.TLabel", font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(main)
        top.pack(fill=tk.X)
        ttk.Label(top, text="MPA Desktop Control Center", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="Refresh Now", command=self._refresh_all).pack(side=tk.RIGHT)

        quick = ttk.LabelFrame(main, text="Quick Actions", padding=10, style="Section.TLabelframe")
        quick.pack(fill=tk.X, pady=(10, 8))

        ttk.Label(quick, text="Miners:").pack(side=tk.LEFT)
        ttk.Spinbox(quick, from_=1, to=16, width=5, textvariable=self.miner_count).pack(side=tk.LEFT, padx=(8, 12))
        ttk.Button(quick, text="Start All", command=lambda: self._bg(self._start_all)).pack(side=tk.LEFT, padx=4)
        ttk.Button(quick, text="Stop All", command=lambda: self._bg(central_web_gui.stop_all)).pack(side=tk.LEFT, padx=4)
        ttk.Button(quick, text="Start Miners", command=lambda: self._bg(self._start_miners)).pack(side=tk.LEFT, padx=4)

        stats = ttk.LabelFrame(main, text="Network Snapshot", padding=10, style="Section.TLabelframe")
        stats.pack(fill=tk.X)
        for idx, (title, key) in enumerate([
            ("Chain Height", "chain_height"),
            ("Active Miners", "miners"),
            ("Total Hashrate", "hashrate"),
            ("Total Shares", "shares"),
            ("Total Balance", "total_balance"),
        ]):
            box = ttk.Frame(stats, padding=8)
            box.grid(row=0, column=idx, sticky="nsew")
            stats.columnconfigure(idx, weight=1)
            ttk.Label(box, text=title).pack()
            ttk.Label(box, textvariable=self.stat_vars[key], style="State.TLabel").pack()

        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.tab_services = ttk.Frame(notebook, padding=10)
        self.tab_wallet = ttk.Frame(notebook, padding=10)
        self.tab_chain = ttk.Frame(notebook, padding=10)
        self.tab_miners = ttk.Frame(notebook, padding=10)

        notebook.add(self.tab_services, text="Services")
        notebook.add(self.tab_wallet, text="Wallet")
        notebook.add(self.tab_chain, text="Blockchain")
        notebook.add(self.tab_miners, text="Miners")

        self._build_services_tab()
        self._build_wallet_tab()
        self._build_chain_tab()
        self._build_miners_tab()

    def _build_services_tab(self):
        header = ttk.Label(self.tab_services, text="Manage all services directly here (no browser needed).")
        header.pack(anchor="w", pady=(0, 10))

        for key, name, port in SERVICES:
            row = ttk.Frame(self.tab_services, padding=8)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=f"{name}  (port {port})", width=34).pack(side=tk.LEFT)
            state = tk.StringVar(value="Checking...")
            self.service_status_vars[key] = state
            ttk.Label(row, textvariable=state, width=15, style="State.TLabel").pack(side=tk.LEFT)
            ttk.Button(row, text="Start", command=lambda k=key: self._bg(lambda: central_web_gui.start_service(k))).pack(side=tk.LEFT, padx=4)

        ttk.Label(self.tab_services, text="Live application log").pack(anchor="w", pady=(12, 4))
        self.log_text = tk.Text(self.tab_services, height=16)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_wallet_tab(self):
        left = ttk.Frame(self.tab_wallet)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(self.tab_wallet)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        auth = ttk.LabelFrame(left, text="Wallet Login / Register", padding=10, style="Section.TLabelframe")
        auth.pack(fill=tk.X)
        ttk.Label(auth, text="Email").grid(row=0, column=0, sticky="w")
        ttk.Entry(auth, textvariable=self.wallet_email, width=35).grid(row=1, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(auth, text="Password").grid(row=2, column=0, sticky="w")
        ttk.Entry(auth, textvariable=self.wallet_password, width=35, show="*").grid(row=3, column=0, sticky="ew", pady=(2, 8))
        btns = ttk.Frame(auth)
        btns.grid(row=4, column=0, sticky="w")
        ttk.Button(btns, text="Login", command=lambda: self._bg(self._wallet_login)).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Register", command=lambda: self._bg(self._wallet_register)).pack(side=tk.LEFT, padx=4)

        current = ttk.LabelFrame(left, text="Current Wallet", padding=10, style="Section.TLabelframe")
        current.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(current, text="Address").pack(anchor="w")
        ttk.Entry(current, textvariable=self.wallet_address).pack(fill=tk.X, pady=(2, 8))
        ttk.Label(current, text="Balance").pack(anchor="w")
        ttk.Label(current, textvariable=self.wallet_balance, style="State.TLabel").pack(anchor="w")
        ttk.Button(current, text="Refresh Balance", command=lambda: self._bg(self._refresh_wallet_balance)).pack(anchor="w", pady=(8, 0))

        transfer = ttk.LabelFrame(right, text="Wallet Transfer", padding=10, style="Section.TLabelframe")
        transfer.pack(fill=tk.X)
        ttk.Label(transfer, text="Receiver Address").pack(anchor="w")
        ttk.Entry(transfer, textvariable=self.transfer_to).pack(fill=tk.X, pady=(2, 8))
        ttk.Label(transfer, text="Amount (MPA)").pack(anchor="w")
        ttk.Entry(transfer, textvariable=self.transfer_amount).pack(fill=tk.X, pady=(2, 8))
        ttk.Button(transfer, text="Send", command=lambda: self._bg(self._wallet_transfer)).pack(anchor="w")

        airdrop = ttk.LabelFrame(right, text="System Airdrop", padding=10, style="Section.TLabelframe")
        airdrop.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(airdrop, text="Receiver Address").pack(anchor="w")
        ttk.Entry(airdrop, textvariable=self.system_airdrop_to).pack(fill=tk.X, pady=(2, 8))
        ttk.Label(airdrop, text="Amount").pack(anchor="w")
        ttk.Entry(airdrop, textvariable=self.system_airdrop_amount).pack(fill=tk.X, pady=(2, 8))
        ttk.Button(airdrop, text="Airdrop", command=lambda: self._bg(self._system_airdrop)).pack(anchor="w")

    def _build_chain_tab(self):
        self.chain_table = ttk.Treeview(self.tab_chain, columns=("index", "miner", "tx", "hash"), show="headings", height=22)
        self.chain_table.heading("index", text="#")
        self.chain_table.heading("miner", text="Miner")
        self.chain_table.heading("tx", text="Transactions")
        self.chain_table.heading("hash", text="Hash")
        self.chain_table.column("index", width=60, anchor="center")
        self.chain_table.column("miner", width=180)
        self.chain_table.column("tx", width=100, anchor="center")
        self.chain_table.column("hash", width=700)
        self.chain_table.pack(fill=tk.BOTH, expand=True)

    def _build_miners_tab(self):
        actions = ttk.Frame(self.tab_miners)
        actions.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(actions, text="Start Configured Miners", command=lambda: self._bg(self._start_miners)).pack(side=tk.LEFT)

        self.miner_table = ttk.Treeview(self.tab_miners, columns=("id", "wallet", "shares", "difficulty", "hashrate"), show="headings", height=20)
        for col, title, width in [
            ("id", "Miner ID", 220),
            ("wallet", "Wallet", 260),
            ("shares", "Shares", 100),
            ("difficulty", "Difficulty", 100),
            ("hashrate", "Hashrate", 120),
        ]:
            self.miner_table.heading(col, text=title)
            self.miner_table.column(col, width=width)
        self.miner_table.pack(fill=tk.BOTH, expand=True)

    def _bg(self, fn):
        threading.Thread(target=self._wrap_action, args=(fn,), daemon=True).start()

    def _wrap_action(self, fn):
        try:
            fn()
        except Exception as exc:
            self._log(f"ERROR: {exc}")

    def _json_get(self, path: str):
        with urlopen(f"{POOL_API}{path}", timeout=2.0) as resp:
            return json.loads(resp.read().decode())

    def _json_post(self, path: str, payload: dict):
        req = Request(
            f"{POOL_API}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=3.0) as resp:
            return json.loads(resp.read().decode())

    def _start_all(self):
        count = max(1, min(16, int(self.miner_count.get() or 1)))
        central_web_gui.start_all(count)
        self._log(f"Started all services and {count} miner(s).")

    def _start_miners(self):
        count = max(1, min(16, int(self.miner_count.get() or 1)))
        central_web_gui.start_miners(count)
        self._log(f"Started {count} miner(s).")

    def _wallet_login(self):
        data = self._json_post("/api/login_wallet", {"email": self.wallet_email.get().strip(), "password": self.wallet_password.get()})
        if data.get("ok"):
            self.wallet_address.set(data.get("wallet", ""))
            self.wallet_balance.set(f"{float(data.get('balance', 0.0)):.6f} MPA")
            self._log(f"Wallet login success: {data.get('email')}")

    def _wallet_register(self):
        data = self._json_post("/api/register_wallet", {"email": self.wallet_email.get().strip(), "password": self.wallet_password.get()})
        if data.get("ok"):
            self.wallet_address.set(data.get("wallet", ""))
            self._log(f"Wallet registered: {data.get('wallet')}")
            self._refresh_wallet_balance()

    def _refresh_wallet_balance(self):
        wallet = self.wallet_address.get().strip()
        if not wallet:
            return
        data = self._json_get(f"/api/wallet/{wallet}")
        self.wallet_balance.set(f"{float(data.get('balance', 0.0)):.6f} MPA")

    def _wallet_transfer(self):
        sender = self.wallet_address.get().strip()
        receiver = self.transfer_to.get().strip()
        amount = float(self.transfer_amount.get().strip())
        payload = {"sender": sender, "receiver": receiver, "amount": amount}
        data = self._json_post("/api/transfer_wallet", payload)
        if data.get("ok"):
            self._log(f"Transfer sent: {amount} MPA -> {receiver}")
            self._refresh_wallet_balance()

    def _system_airdrop(self):
        receiver = self.system_airdrop_to.get().strip()
        amount = float(self.system_airdrop_amount.get().strip())
        data = self._json_post("/api/transfer_simple", {"receiver": receiver, "amount": amount})
        if data.get("ok"):
            self._log(f"Airdrop sent: {amount} MPA -> {receiver}")
            self._refresh_wallet_balance()

    def _refresh_all(self):
        self._refresh_services()
        self._refresh_pool_data()
        self.root.after(REFRESH_MS, self._refresh_all)

    def _refresh_services(self):
        for key, _, port in SERVICES:
            online = central_web_gui.is_service_online(port)
            self.service_status_vars[key].set("Online ✅" if online else "Offline ❌")

    def _refresh_pool_data(self):
        try:
            data = self._json_get("/api/pool")
        except URLError:
            self._log("Pool API offline (start pool service).")
            return
        except Exception as exc:
            self._log(f"Pool refresh error: {exc}")
            return

        self.stat_vars["chain_height"].set(str(data.get("chain_height", 0)))
        miners = data.get("miners", {})
        self.stat_vars["miners"].set(str(len(miners)))
        self.stat_vars["hashrate"].set(str(data.get("total_hashrate", 0)))
        self.stat_vars["shares"].set(str(data.get("total_shares", 0)))
        self.stat_vars["total_balance"].set(f"{float(data.get('total_balance', 0.0)):.4f}")

        self._refresh_miners_table(miners)
        self._refresh_chain_table()

    def _refresh_miners_table(self, miners: dict):
        self.miner_table.delete(*self.miner_table.get_children())
        for miner_id, info in sorted(miners.items()):
            self.miner_table.insert(
                "",
                tk.END,
                values=(
                    miner_id,
                    info.get("wallet", ""),
                    info.get("shares", 0),
                    info.get("difficulty", 0),
                    info.get("hashrate", 0),
                ),
            )

    def _refresh_chain_table(self):
        try:
            data = self._json_get("/api/chain")
        except Exception:
            return
        blocks = data.get("blocks", [])[-120:]
        self.chain_table.delete(*self.chain_table.get_children())
        for b in reversed(blocks):
            self.chain_table.insert(
                "",
                tk.END,
                values=(b.get("index"), b.get("miner", ""), b.get("tx_count", 0), b.get("hash", "")[:72]),
            )

    def _log(self, text: str):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _on_close(self):
        if messagebox.askyesno("Exit", "Do you want to stop all services before closing?"):
            try:
                central_web_gui.stop_all()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    MPADesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
