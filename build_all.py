import os
import subprocess
import sys
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(ROOT,"launcher","mpa_launcher.py")

# ---- 1. Build CUDA miner ----
cuda_dir = os.path.join(ROOT,"miner","cuda")
if sys.platform.startswith("win"):
    subprocess.run(["nvcc","mpa_ethash.cu","main.cpp","-o","mpa_miner.exe"], cwd=cuda_dir)
else:
    subprocess.run(["nvcc","mpa_ethash.cu","main.cpp","-o","mpa_miner"], cwd=cuda_dir)

# ---- 2. Build Windows EXE ----
if sys.platform.startswith("win"):
    pyinstaller_cmd = [
        "pyinstaller",
        "--name","MPA_Launcher",
        "--onefile",
        "--add-data", f"{os.path.join(ROOT,'miner','cuda')};cuda",
        "--noconsole",
        LAUNCHER
    ]
    subprocess.run(pyinstaller_cmd)

# ---- 3. Build Linux AppImage ----
if sys.platform.startswith("linux"):
    appdir = os.path.join(ROOT,"MPA.AppDir")
    os.makedirs(os.path.join(appdir,"usr/bin"), exist_ok=True)
    # Copy all project files
    for folder in os.listdir(ROOT):
        if folder.startswith(".") or folder=="MPA.AppDir":
            continue
        shutil.copytree(os.path.join(ROOT,folder), os.path.join(appdir,"usr/bin",folder))
    # Create AppRun script
    apprun_path = os.path.join(appdir,"AppRun")
    with open(apprun_path,"w") as f:
        f.write(f"""#!/bin/bash
HERE="$(dirname "$(readlink -f "${{0}}")")"
export PATH="$HERE/usr/bin:$PATH"
python3 "$HERE/usr/bin/launcher/mpa_launcher.py"
""")
    os.chmod(apprun_path,0o755)
    # Build AppImage
    subprocess.run(["appimagetool-x86_64.AppImage", appdir])

print("Build complete!")
