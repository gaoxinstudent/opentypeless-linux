"""音频录制模块

实现按住热键录音（push-to-talk）功能。
- 16kHz 采样率，单声道，16bit PCM
- 录音时在后台线程运行，不阻塞 UI
- 输出 numpy float32 数组（范围 -1.0 ~ 1.0）
- 支持麦克风设备检测
"""

import threading
import queue
import subprocess
from typing import Optional, List
import pyaudio
import numpy as np


# 音频参数
SAMPLE_RATE = 16000  # 16kHz（FunASR 标准采样率）
CHANNELS = 1          # 单声道
FORMAT = pyaudio.paInt16  # 16bit PCM
CHUNK_SIZE = 960      # 60ms 每块（16000 * 0.06 = 960）
SAMPLE_WIDTH = 2      # 16bit = 2 bytes


def list_microphones() -> List[dict]:
    """列出系统可用的麦克风设备"""
    devices = []
    try:
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                devices.append({
                    "index": i,
                    "name": info.get("name", "Unknown"),
                    "channels": info.get("maxInputChannels"),
                    "sample_rate": int(info.get("defaultSampleRate", 0)),
                })
        pa.terminate()
    except Exception:
        pass
    return devices


def check_microphone() -> bool:
    """快速检查是否有可用的麦克风"""
    try:
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                pa.terminate()
                return True
        pa.terminate()
        return False
    except Exception:
        return False


def _play_beep(freq: int = 800, duration_ms: int = 100, volume: float = 0.5):
    """播放提示音（尝试多种播放方式）"""
    duration_s = duration_ms / 1000.0
    # 生成 16kHz 16bit 单声道 WAV 数据
    sample_rate = 16000
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    # 带衰减包络（避免爆音）
    envelope = np.exp(-3 * t / duration_s)
    audio = (volume * np.sin(2 * np.pi * freq * t) * envelope).astype(np.float32)
    audio_int16 = (audio * 32767).astype(np.int16)

    # 构造最小 WAV 文件（PCM）
    import struct
    data_size = len(audio_int16) * 2
    wav_header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate,
        sample_rate * 2, 2, 16,
        b'data', data_size,
    )
    wav_data = wav_header + audio_int16.tobytes()

    # 尝试多种播放器
    for cmd in [
        ["aplay", "-q"],                           # ALSA
        ["paplay", "--short"],                     # PulseAudio
        ["play", "-q", "-t", "wav", "-"],          # sox
    ]:
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=wav_data, timeout=2)
            if proc.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue


class AudioRecorder:
    """Push-to-talk 音频录制器"""

    def __init__(self):
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._chunks: list[bytes] = []
        self._chunk_queue: queue.Queue = queue.Queue()
        self._mic_available: Optional[bool] = None

    def check_mic(self) -> bool:
        """检测麦克风是否可用（缓存结果）"""
        if self._mic_available is None:
            self._mic_available = check_microphone()
        return self._mic_available

    def list_mics(self) -> List[dict]:
        """列出可用麦克风"""
        return list_microphones()

    def _init_pyaudio(self) -> Optional[pyaudio.PyAudio]:
        if self._pyaudio is None:
            try:
                self._pyaudio = pyaudio.PyAudio()
            except Exception as e:
                print(f"[AudioRecorder] PyAudio 初始化失败: {e}")
                return None
        return self._pyaudio

    def start(self) -> bool:
        """开始录音（非阻塞），返回是否成功启动"""
        if self._recording:
            return False

        # 检测麦克风
        if not self.check_mic():
            print("[AudioRecorder] 未检测到麦克风")
            return False

        self._chunks = []
        self._recording = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

        # 录音开始提示音（高音）
        _play_beep(1200, 80, 0.3)

        return True

    def _record_loop(self) -> None:
        """后台录音循环"""
        pa = self._init_pyaudio()
        if pa is None:
            self._recording = False
            return

        try:
            self._stream = pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
            while self._recording:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._chunks.append(data)
                self._chunk_queue.put(data)
        except Exception as e:
            print(f"[AudioRecorder] 录音错误: {e}")
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

    def stop(self) -> np.ndarray:
        """停止录音，返回 float32 归一化音频数组"""
        self._recording = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        # 录音结束提示音（低音）
        _play_beep(600, 80, 0.3)

        if not self._chunks:
            return np.array([], dtype=np.float32)

        # 拼接 PCM 字节
        raw_bytes = b"".join(self._chunks)

        # 转换为 numpy float32
        audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        return audio_float32

    @property
    def is_recording(self) -> bool:
        return self._recording

    def close(self) -> None:
        """释放 PyAudio 资源"""
        self.stop()
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None
