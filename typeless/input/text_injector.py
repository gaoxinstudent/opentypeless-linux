"""文本注入模块

将润色后的文本注入到当前焦点应用的输入光标处。
- X11: pyperclip 复制 + xdotool Ctrl+V
- Wayland: wtype 逐字输入（兜底）
"""

import os
import subprocess
import time
import pyperclip


def _is_wayland() -> bool:
    """检测是否运行在 Wayland 下"""
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def inject_text(text: str) -> bool:
    """将文本注入到当前焦点窗口

    策略：剪贴板 + Ctrl+V 粘贴（最可靠的跨应用方式）

    Args:
        text: 要输入的文本

    Returns:
        True 成功，False 失败
    """
    if not text:
        return False

    if _is_wayland():
        return _inject_wayland(text)
    else:
        return _inject_x11(text)


def _inject_x11(text: str) -> bool:
    """X11 下通过剪贴板 + xdotool 粘贴"""
    try:
        # 1. 复制到剪贴板
        pyperclip.copy(text)
        time.sleep(0.05)  # 短暂等待剪贴板生效

        # 2. 模拟 Ctrl+V
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            timeout=2,
            check=False,
        )
        return True
    except Exception as e:
        print(f"[TextInjector] X11 注入失败: {e}")
        # 后备：xdotool type 逐字输入
        return _inject_x11_type(text)


def _inject_x11_type(text: str) -> bool:
    """X11 后备方案：逐字输入（较慢但兼容性好）"""
    try:
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "5", text],
            timeout=10,
            check=False,
        )
        return True
    except Exception as e:
        print(f"[TextInjector] type 注入也失败: {e}")
        return False


def _inject_wayland(text: str) -> bool:
    """Wayland 下通过 wtype 输入"""
    try:
        result = subprocess.run(
            ["wtype", "-"],
            input=text,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # wtype 未安装，尝试 ydotool
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            subprocess.run(["ydotool", "key", "29:1,47:1,47:0,29:0"], timeout=2)
            return True
        except FileNotFoundError:
            print("[TextInjector] Wayland 下没有 wtype 或 ydotool")
            return False
