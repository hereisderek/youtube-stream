@echo off
setlocal
chcp 65001 >nul

:: --- [ Python 环境检查与安装 ] ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 在此系统中找不到 Python。
    set /p INSTALL_PY="是否要使用 winget 自动安装最新的 Python 3? ^(y/n^): " 
    if /i "%INSTALL_PY%"=="y" (
        echo [INFO] 正在尝试通过 winget 安装 Python...
        winget install -e --id Python.Python.3
        if %errorlevel% neq 0 (
            echo [ERROR] 自动安装失败。请手动安装 Python 3 并将其添加到 PATH 环境变量。
            pause
            exit /b 1
        )
        echo [SUCCESS] Python 安装成功。请重新运行此脚本。
        pause
        exit /b 0
    ) else (
        echo [ERROR] 请安装 Python 3 环境后再运行脚本。
        pause
        exit /b 1
    )
)

set VENV_DIR=.venv

echo "[INFO] 正在执行一键下播..."
"%VENV_DIR%\Scripts\python.exe" stop_stream.py

echo.
pause