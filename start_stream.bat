@echo off
setlocal
chcp 65001 >nul

:: ==========================================
:: [可选配置] 自定义 OBS 完整路径
:: 如果不为空，将覆盖系统默认路径。路径中不要带引号。
:: 例如: set CUSTOM_OBS_PATH=D:\OBS Studio\bin\64bit\obs64.exe
:: ==========================================
set CUSTOM_OBS_PATH=

:: --- [ Python 环境检查与安装 ] ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 在此系统中找不到 Python。
    set /p INSTALL_PY="是否要使用 winget 自动安装最新的 Python 3? ^(y/n^): " 
    if /i "%INSTALL_PY%"=="y" (
        echo "[INFO] 正在尝试通过 winget 安装 Python..."
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

:: allow optional venv directory via 2nd argument or CUSTOM_VENV_DIR env var
set "STREAM_TYPE=%~1"
if "%STREAM_TYPE%"=="" set "STREAM_TYPE=dota2"

set "VENV_DIR=%~2"
if "%VENV_DIR%"=="" (
    if defined CUSTOM_VENV_DIR (
        set VENV_DIR=%CUSTOM_VENV_DIR%
    ) else (
        set VENV_DIR=.venv
    )
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo "[INFO] 正在创建虚拟环境 (%VENV_DIR%)..."
    python -m venv "%VENV_DIR%"
)

echo "[INFO] 检查并更新依赖..."
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt >nul 2>&1

:: 构建 OBS 路径参数
set OBS_ARG=
if not "%CUSTOM_OBS_PATH%"=="" (
    set OBS_ARG=--obs-path "%CUSTOM_OBS_PATH%"
)

echo "[INFO] 正在启动 [%STREAM_TYPE%] 直播流..."
"%VENV_DIR%\Scripts\python.exe" stream-youtube-gaming.py --type %STREAM_TYPE% %OBS_ARG%

echo.
pause