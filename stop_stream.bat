@echo off
setlocal
chcp 65001 >nul
set VENV_DIR=.venv

echo [INFO] 正在执行一键下播...
"%VENV_DIR%\Scripts\python.exe" stop_stream.py

echo.
pause