import threading
import time
import webbrowser

import central_web_gui

HOST = "127.0.0.1"
PORT = 8060
APP_URL = f"http://{HOST}:{PORT}"


def _run_web_server():
    central_web_gui.app.run(host="0.0.0.0", port=PORT, use_reloader=False)


def _wait_until_ready(timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if central_web_gui.is_service_online(PORT, host=HOST):
            return True
        time.sleep(0.15)
    return False


def main():
    server_thread = threading.Thread(target=_run_web_server, daemon=True)
    server_thread.start()

    if not _wait_until_ready():
        raise RuntimeError(f"Failed to start central web gui on {APP_URL}")

    try:
        import webview
    except Exception:
        webbrowser.open(APP_URL)
        print("pywebview not found. Opened Central GUI in your default browser.")
        print("Install pywebview to run as a native desktop window: pip install pywebview")
        server_thread.join()
        return

    window = webview.create_window("MPA Desktop Control Center", APP_URL, width=1400, height=950)
    webview.start(gui="edgechromium", debug=False)

    try:
        central_web_gui.stop_all()
    except Exception:
        pass


if __name__ == "__main__":
    main()
