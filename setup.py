"""Typeless-Linux: 智能语音输入工具

类似 Typeless 的 Linux 桌面端实现:
按住热键 → 说话 → 语音识别 → AI润色 → 自动粘贴
"""

from setuptools import setup, find_packages

setup(
    name="typeless-linux",
    version="0.1.0",
    description="智能语音输入工具 - Linux 版 Typeless 替代",
    author="gx",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "funasr>=1.0.0",
        "websocket-client>=1.6.0",
        "openai>=1.0.0",
        "pyaudio>=0.2.11",
        "pynput>=1.7.0",
        "pystray>=0.19.0",
        "Pillow>=10.0.0",
        "pyperclip>=1.8.0",
    ],
    # 设置界面使用 Python 内置 tkinter，无需额外依赖
    entry_points={
        "console_scripts": [
            "typeless=typeless.main:main",
        ],
    },
)
