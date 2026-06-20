"""FunASR 语音识别客户端

直接嵌入 Paraformer 模型，无需独立服务进程。
模型: speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch
  - 内置 VAD（语音端点检测）
  - 内置标点恢复
  - GPU 实时推理（RTF ~0.2）
"""

import threading
import numpy as np
from typing import Optional


# 与 recorder.py 保持一致的采样率
SAMPLE_RATE = 16000

# 模型标识
MODEL_NAME = "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"


class FunASRClient:
    """FunASR 语音识别客户端（嵌入模式）"""

    def __init__(self, device: str = "cuda:0"):
        self._model = None
        self._device = device
        self._lock = threading.Lock()
        self._ready = False

    def load_model(self) -> bool:
        """加载模型（阻塞，首次启动时调用）"""
        if self._ready:
            return True

        try:
            from funasr import AutoModel

            print("[FunASR] 正在加载语音识别模型...")
            self._model = AutoModel(
                model=MODEL_NAME,
                device=self._device,
                disable_update=True,
            )
            self._ready = True
            print("[FunASR] 模型加载完成")
            return True
        except Exception as e:
            print(f"[FunASR] 模型加载失败: {e}")
            return False

    def recognize(self, audio: np.ndarray) -> str:
        """识别语音，返回文本

        Args:
            audio: float32 数组，16kHz 单声道，范围 [-1.0, 1.0]

        Returns:
            识别出的文本（含标点）。空音频返回空字符串。
        """
        if not self._ready:
            raise RuntimeError("模型未加载，请先调用 load_model()")

        # 音频过短（< 0.3 秒）视为无效
        if len(audio) < SAMPLE_RATE * 0.3:
            return ""

        with self._lock:
            try:
                result = self._model.generate(input=audio)
                if result and len(result) > 0:
                    text = result[0].get("text", "").strip()
                    # FunASR 输出以空格分隔中文字词，需要去除
                    text = text.replace(" ", "")
                    return text
                return ""
            except Exception as e:
                print(f"[FunASR] 识别错误: {e}")
                return ""

    @property
    def is_ready(self) -> bool:
        return self._ready
