import os
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def main():
    subprocess.Popen([PY, os.path.join(ROOT, "central_web_gui.py")])
    time.sleep(1.0)
    try:
        webbrowser.open("http://127.0.0.1:8060/open/all")
    except Exception:
        pass
    print("MPA started. Open: http://127.0.0.1:8060/open/all")


if __name__ == "__main__":
    main()
