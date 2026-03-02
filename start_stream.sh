#!/usr/bin/env bash

# ==========================================
# [可选配置] 自定义 OBS 完整路径
# 如果不为空，将覆盖系统默认路径。
# 例如: CUSTOM_OBS_PATH="/opt/obs-studio/bin/obs"
# ==========================================
CUSTOM_OBS_PATH=""

VENV_DIR=".venv"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[INFO] 正在创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

echo "[INFO] 检查并更新依赖..."
"$VENV_DIR/bin/python" -m pip install -r requirements.txt >/dev/null 2>&1

STREAM_TYPE=${1:-dota2}

OBS_ARG=""
if [ -n "$CUSTOM_OBS_PATH" ]; then
    OBS_ARG="--obs-path \"$CUSTOM_OBS_PATH\""
fi

echo "[INFO] 正在启动 [$STREAM_TYPE] 直播流..."
eval "\"$VENV_DIR/bin/python\" stream-youtube-gaming.py --type \"$STREAM_TYPE\" $OBS_ARG"