import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import central_web_gui

HOST = "127.0.0.1"
REFRESH_MS = 2000

SERVICES = [
    ("p2p", "P2P Node", 5000),
    ("explorer", "Blockchain Explorer", 8050),
    ("wallet", "Wallet", 8070),
    ("pool", "Pool GUI", 8080),
]


class DesktopControlApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MPA Desktop Control Center")
        self.root.geometry("980x700")

        self._status_labels: dict[str, tk.StringVar] = {}
        self._miner_count = tk.IntVar(value=1)

        self._build_ui()
        self._refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        root_frame = ttk.Frame(self.root, padding=14)
        root_frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(root_frame, text="MPA Desktop Control Center", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")

        top_actions = ttk.Frame(root_frame, padding=(0, 10, 0, 10))
        top_actions.pack(fill=tk.X)

        ttk.Label(top_actions, text="Miners:").pack(side=tk.LEFT)
        miner_spin = ttk.Spinbox(top_actions, from_=1, to=16, width=5, textvariable=self._miner_count)
        miner_spin.pack(side=tk.LEFT, padx=(8, 16))

        ttk.Button(top_actions, text="Start All", command=self._start_all).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_actions, text="Stop All", command=self._stop_all).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_actions, text="Refresh", command=self._refresh_status).pack(side=tk.LEFT, padx=4)

        services_frame = ttk.LabelFrame(root_frame, text="Services", padding=12)
        services_frame.pack(fill=tk.X)

        for idx, (key, name, port) in enumerate(SERVICES):
            row = ttk.Frame(services_frame)
            row.grid(row=idx, column=0, sticky="ew", pady=4)

            ttk.Label(row, text=f"{name} ({port})", width=28).pack(side=tk.LEFT)
            status_var = tk.StringVar(value="Checking...")
            self._status_labels[key] = status_var
            ttk.Label(row, textvariable=status_var, width=16).pack(side=tk.LEFT)
            ttk.Button(row, text="Start", command=lambda k=key: self._start_service(k)).pack(side=tk.LEFT, padx=4)
            ttk.Button(row, text="Open", command=lambda p=port: self._open_url(p)).pack(side=tk.LEFT, padx=4)

        miners_frame = ttk.LabelFrame(root_frame, text="Miners", padding=12)
        miners_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Button(miners_frame, text="Start Configured Miners", command=self._start_miners).pack(anchor="w", pady=(0, 8))

        self.miners_list = tk.Text(miners_frame, height=12)
        self.miners_list.pack(fill=tk.BOTH, expand=True)

    def _set_status(self, key: str, online: bool):
        state = "Online ✅" if online else "Offline ❌"
        self._status_labels[key].set(state)

    def _refresh_status(self):
        for key, _, port in SERVICES:
            online = central_web_gui.is_service_online(port)
            self._set_status(key, online)

        self.miners_list.delete("1.0", tk.END)
        online_ports = [p for p in range(8090, 8106) if central_web_gui.is_service_online(p)]
        if online_ports:
            self.miners_list.insert(tk.END, "Online miner ports:\n")
            for p in online_ports:
                self.miners_list.insert(tk.END, f"- {p}\n")
        else:
            self.miners_list.insert(tk.END, "No online miners found.\n")

        self.root.after(REFRESH_MS, self._refresh_status)

    def _safe_thread(self, fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    def _start_service(self, key: str):
        self._safe_thread(lambda: central_web_gui.start_service(key))

    def _start_all(self):
        count = max(1, min(16, int(self._miner_count.get() or 1)))

        def _job():
            central_web_gui.start_all(count)

        self._safe_thread(_job)

    def _stop_all(self):
        self._safe_thread(central_web_gui.stop_all)

    def _start_miners(self):
        count = max(1, min(16, int(self._miner_count.get() or 1)))
        self._safe_thread(lambda: central_web_gui.start_miners(count))

    def _open_url(self, port: int):
        webbrowser.open(f"http://{HOST}:{port}")

    def _on_close(self):
        if messagebox.askyesno("Exit", "Stop all services before closing?"):
            try:
                central_web_gui.stop_all()
                time.sleep(0.2)
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = DesktopControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
