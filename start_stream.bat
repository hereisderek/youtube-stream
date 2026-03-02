@echo off
setlocal
chcp 65001 >nul

:: ==========================================
:: [可选配置] 自定义 OBS 完整路径
:: 如果不为空，将覆盖系统默认路径。路径中不要带引号。
:: 例如: set CUSTOM_OBS_PATH=D:\OBS Studio\bin\64bit\obs64.exe
:: ==========================================
set CUSTOM_OBS_PATH=

set VENV_DIR=.venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] 正在创建虚拟环境...
    python -m venv %VENV_DIR%
)

echo [INFO] 检查并更新依赖...
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt >nul 2>&1

set STREAM_TYPE=%1
if "%STREAM_TYPE%"=="" set STREAM_TYPE=dota2

:: 构建 OBS 路径参数
set OBS_ARG=
if not "%CUSTOM_OBS_PATH%"=="" (
    set OBS_ARG=--obs-path "%CUSTOM_OBS_PATH%"
)

echo [INFO] 正在启动 [%STREAM_TYPE%] 直播流...
"%VENV_DIR%\Scripts\python.exe" stream-youtube-gaming.py --type %STREAM_TYPE% %OBS_ARG%

echo.
pause