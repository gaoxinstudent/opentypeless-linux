"""Typeless-Linux 主入口

整体流程：
1. 检测麦克风 → 启动系统托盘 → 加载 ASR 模型
2. 注册全局热键监听
3. 按住热键 → 录音 → 松开热键 → ASR → 润色 → 粘贴
"""

import sys
import time
import threading
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from pynput import keyboard

from typeless.config import load_config, save_config
from typeless.audio.recorder import AudioRecorder, check_microphone
from typeless.asr.funasr_client import FunASRClient
from typeless.polish.deepseek_polish import DeepSeekPolish
from typeless.input.text_injector import inject_text

logger = logging.getLogger(__name__)


class TypelessApp:
    """Typeless 主应用"""

    def __init__(self):
        self.config = load_config()
        self.recorder = AudioRecorder()
        self.asr = FunASRClient()
        self.polish = DeepSeekPolish()
        self.executor = ThreadPoolExecutor(max_workers=1)

        # 热键状态
        self._hotkey_pressed = False
        self._listener: Optional[keyboard.Listener] = None
        self._hotkey = self._parse_hotkey(self.config.get("hotkey", "<ctrl_r>"))

        # 托盘引用（由 ui.tray 设置）
        self.tray_icon = None

    # ── 热键解析 ──────────────────────────────────

    @staticmethod
    def _parse_hotkey(hotkey_str: str):
        """将配置字符串转为 pynput Key 对象"""
        mapping = {
            "<ctrl_r>": keyboard.Key.ctrl_r,
            "<ctrl_l>": keyboard.Key.ctrl_l,
            "<ctrl>": keyboard.Key.ctrl,
            "<alt>": keyboard.Key.alt,
            "<alt_r>": keyboard.Key.alt_r,
            "<shift>": keyboard.Key.shift,
            "<shift_r>": keyboard.Key.shift_r,
            "<cmd>": keyboard.Key.cmd,
            "<f1>": keyboard.Key.f1,
            "<f2>": keyboard.Key.f2,
            "<f3>": keyboard.Key.f3,
            "<f4>": keyboard.Key.f4,
            "<f5>": keyboard.Key.f5,
            "<f6>": keyboard.Key.f6,
            "<f7>": keyboard.Key.f7,
            "<f8>": keyboard.Key.f8,
            "<f9>": keyboard.Key.f9,
            "<f10>": keyboard.Key.f10,
            "<f11>": keyboard.Key.f11,
            "<f12>": keyboard.Key.f12,
        }
        return mapping.get(hotkey_str, keyboard.Key.ctrl_r)

    # ── 热键处理 ──────────────────────────────────

    def _on_press(self, key):
        """热键按下"""
        if key == self._hotkey and not self._hotkey_pressed:
            self._hotkey_pressed = True
            self._start_recording()

    def _on_release(self, key):
        """热键释放"""
        if key == self._hotkey and self._hotkey_pressed:
            self._hotkey_pressed = False
            self._stop_and_process()

    # ── 录音控制 ──────────────────────────────────

    def _start_recording(self):
        """开始录音"""
        if not self.asr.is_ready:
            self._notify("⏳ ASR 模型尚未加载完成，请稍候...")
            return

        success = self.recorder.start()
        if success:
            self._notify("🎙️ 录音中...")
            self._update_tray_status("recording")
        else:
            self._notify("❌ 无法启动录音，请检查麦克风")
            self._hotkey_pressed = False

    def _stop_and_process(self):
        """停止录音并启动处理流水线"""
        audio = self.recorder.stop()
        self._update_tray_status("processing")

        if len(audio) == 0:
            self._notify("⚠️ 未捕获到音频")
            self._update_tray_status("idle")
            return

        duration = len(audio) / 16000
        self._notify(f"⏳ 识别中... ({duration:.1f}s)")

        # 在后台线程中处理（ASR + Polish + Inject）
        self.executor.submit(self._process_pipeline, audio)

    def _process_pipeline(self, audio):
        """处理流水线：ASR → 润色 → 注入"""
        try:
            # Phase 1: ASR
            raw_text = self.asr.recognize(audio)
            if not raw_text:
                logger.info("ASR 未识别到语音")
                self._notify("🔇 未识别到有效语音")
                self._update_tray_status("idle")
                return

            logger.info(f"ASR 原文: {raw_text}")

            # Phase 2: 润色
            if self.config.get("remove_fillers", True) or self.config.get("auto_structure", True):
                mode = self.config.get("polish_mode", "general")
                polished_text = self.polish.polish(raw_text, mode=mode)
            else:
                polished_text = raw_text

            logger.info(f"润色结果: {polished_text}")

            # Phase 3: 注入文本
            success = inject_text(polished_text)
            if success:
                self._notify("✅ 文本已注入")
            else:
                self._notify("❌ 文本注入失败")
                logger.warning("文本注入失败")

        except Exception as e:
            logger.error(f"处理流水线异常: {e}")
            self._notify(f"❌ 处理失败: {e}")
        finally:
            self._update_tray_status("idle")

    # ── 通知和状态 ────────────────────────────────

    def _notify(self, message: str):
        """发送系统桌面通知"""
        try:
            import subprocess
            subprocess.run(
                ["notify-send", "Typeless", message,
                 "--expire-time=2500", "--app-name=Typeless"],
                timeout=2,
                check=False,
            )
        except Exception:
            pass

    def _update_tray_status(self, status: str):
        """更新托盘状态图标"""
        if self.tray_icon:
            try:
                self.tray_icon.update_status(status)
            except Exception:
                pass

    # ── 健康检查 ──────────────────────────────────

    def check_microphone(self) -> bool:
        """检测麦克风可用性"""
        has_mic = check_microphone()
        if not has_mic:
            self._notify("❌ 未检测到麦克风设备！请在设置中检查音频输入。")
            logger.warning("未检测到麦克风")
        else:
            logger.info("麦克风检测通过")
        return has_mic

    # ── 启动 ──────────────────────────────────────

    def start_hotkey_listener(self):
        """启动全局热键监听"""
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info(f"热键监听已启动: {self.config.get('hotkey', '<ctrl_r>')}")

    def load_asr_model(self):
        """后台加载 ASR 模型"""
        self._notify("⏳ 正在加载语音识别模型...")
        if self.asr.load_model():
            self._notify("✅ 语音识别模型就绪，按住热键开始说话吧！")
        else:
            self._notify("❌ 模型加载失败，请检查配置后重启")

    def run(self):
        """主启动流程"""
        # 0. 启动前检查
        logger.info("Typeless 启动中...")

        # 1. 检查麦克风
        self.check_microphone()

        # 2. 启动热键监听
        self.start_hotkey_listener()

        # 3. 后台加载 ASR 模型
        threading.Thread(target=self.load_asr_model, daemon=True).start()

        # 4. 启动系统托盘（阻塞主线程）
        from typeless.ui.tray import create_tray
        self.tray_icon = create_tray(self)
        self.tray_icon.run()

    def shutdown(self):
        """清理资源"""
        logger.info("Typeless 正在退出...")
        self.recorder.close()
        self.executor.shutdown(wait=False)
        if self._listener:
            self._listener.stop()


def main():
    """程序入口"""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    app = TypelessApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
