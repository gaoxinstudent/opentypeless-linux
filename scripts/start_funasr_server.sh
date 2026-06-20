#!/bin/bash
# 启动 FunASR WebSocket 服务（备用方式）
# Typeless-Linux 默认使用内嵌模式，此脚本用于独立部署 FunASR 服务

MODEL="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
PORT="${1:-10095}"

echo "启动 FunASR WebSocket 服务: ws://0.0.0.0:${PORT}"
python3 -m funasr.runtime.python.websocket.funasr_wss_server \
    --model "${MODEL}" \
    --port "${PORT}" \
    --device "cuda:0"
