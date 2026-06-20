"""系统托盘模块

提供系统托盘图标和右键菜单。
图标状态：idle（黑色）、recording（红色）、processing（黄色）
"""

import os
import threading
from PIL import Image, ImageDraw
import pystray


# 图标尺寸
ICON_SIZE = 64


def _create_icon_image(status: str = "idle") -> Image.Image:
    """生成状态图标

    status: "idle" | "recording" | "processing"
    """
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆形底色
    colors = {
        "idle": (100, 100, 100),       # 灰色 - 待机
        "recording": (220, 50, 50),     # 红色 - 录音中
        "processing": (220, 180, 30),   # 黄色 - 处理中
    }
    color = colors.get(status, (100, 100, 100))

    # 外圈
    draw.ellipse([4, 4, ICON_SIZE - 4, ICON_SIZE - 4], fill=color)
    # 内圈（亮色）
    highlight = tuple(min(c + 40, 255) for c in color)
    draw.ellipse([12, 12, ICON_SIZE - 12, ICON_SIZE - 12], fill=highlight)
    # 麦克风符号（简化：圆点）
    draw.ellipse([22, 22, ICON_SIZE - 22, ICON_SIZE - 22], fill=(255, 255, 255))

    return img


class TrayIcon:
    """系统托盘图标管理"""

    def __init__(self, app):
        self._app = app
        self._status = "idle"
        self._icon = pystray.Icon(
            "typeless",
            _create_icon_image("idle"),
            "Typeless - 智能语音输入",
            menu=self._build_menu(),
        )

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem("🎙️ 状态: 就绪", self._on_status, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ 设置", self._on_settings),
            pystray.MenuItem("🔄 重新加载模型", self._on_reload_model),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ 退出", self._on_exit),
        )

    def update_status(self, status: str):
        """更新托盘状态"""
        self._status = status
        self._icon.icon = _create_icon_image(status)

    def run(self):
        """运行托盘（阻塞）"""
        self._icon.run()

    def stop(self):
        self._icon.stop()

    # ── 菜单回调 ──────────────────────────────────

    def _on_status(self, icon, item):
        pass  # 仅展示状态，不可点击

    def _on_settings(self, icon, item):
        """打开设置 — 优先 GUI，回退到编辑器"""
        self._open_settings()

    def _open_settings(self):
        # 方案1: 启动独立进程运行 tkinter GUI
        try:
            import subprocess, sys, os
            script = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "ui", "settings.py",
            )
            subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

        # 方案2: 用编辑器打开配置文件
        try:
            from typeless.ui.settings import open_config_in_editor
            open_config_in_editor()
        except Exception:
            pass

    def _on_reload_model(self, icon, item):
        """重新加载 ASR 模型"""
        def reload():
            self._app.asr._ready = False
            self._app.asr.load_model()
        threading.Thread(target=reload, daemon=True).start()

    def _on_exit(self, icon, item):
        """退出应用"""
        self._app.shutdown()
        self.stop()


def create_tray(app) -> TrayIcon:
    return TrayIcon(app)
