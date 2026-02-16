@echo off
setlocal

if "%PYTHON%"=="" set PYTHON=python

%PYTHON% -m pip install --upgrade pyinstaller
%PYTHON% -m PyInstaller --noconfirm --onefile --windowed --name MPA-Desktop-Control-Center "%~dp0central_desktop_app.py"

echo.
echo Build complete. EXE path:
echo dist\MPA-Desktop-Control-Center.exe

endlocal
