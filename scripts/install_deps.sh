#!/bin/bash
# Typeless-Linux 依赖安装脚本

set -e

echo "=== Typeless-Linux 依赖安装 ==="

# 系统依赖
echo "[1/3] 安装系统包..."
sudo apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    xdotool \
    libx11-dev \
    python3-tk \
    2>/dev/null || true

# Python 依赖
echo "[2/3] 安装 Python 依赖..."
cd "$(dirname "$0")/.."
pip install --user -r requirements.txt

# 验证
echo "[3/3] 验证安装..."
python3 -c "
import torch
print(f'  PyTorch {torch.__version__} - CUDA: {torch.cuda.is_available()}')
"
python3 -c "
from funasr import AutoModel
print('  FunASR 就绪')
"
python3 -c "
import pyaudio
print('  PyAudio 就绪')
"
python3 -c "
import pynput
print('  pynput 就绪')
"

echo ""
echo "=== 安装完成 ==="
echo "首次运行 typeless 时会自动下载语音识别模型（约 860MB）。"
echo "启动命令: python3 -m typeless.main"
