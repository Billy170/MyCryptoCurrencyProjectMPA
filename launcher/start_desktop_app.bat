@echo off
setlocal

if "%PYTHON%"=="" set PYTHON=python

%PYTHON% "%~dp0central_desktop_app.py"

endlocal
