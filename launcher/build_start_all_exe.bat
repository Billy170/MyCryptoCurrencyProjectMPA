@echo off
REM Build a Windows .exe launcher (run this on Windows)
python -m pip install pyinstaller
pyinstaller --onefile --name MPA_Start_All launcher\start_all.py
echo EXE created in dist\MPA_Start_All.exe
