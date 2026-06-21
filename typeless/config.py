"""配置管理模块

管理 ~/.config/typeless/config.json 配置文件。
遵循 KISS 原则：单文件 JSON，简单读写。
"""

import os
import json
from pathlib import Path
from typing import Any, Optional


DEFAULT_CONFIG = {
    "deepseek_api_key": "",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-v4-flash",  # 快速模型，润色够用
    "hotkey": "<ctrl_r>",
    "polish_mode": "general",
    "remove_fillers": True,
    "auto_structure": True,
    "auto_structure_long": True,  # 长语音自动提炼要点并编号
    "audio_device": None,
    "memory_size": 5,
    # 自定义屏蔽词（会追加到内置列表）
    "custom_fillers_zh": [],  # 中文自定义填充词，如 ["就是说", "然后呢"]
    "custom_fillers_en": [],  # 英文自定义填充词，如 ["I mean", "sort of"]
}


def _config_dir() -> Path:
    """配置目录 ~/.config/typeless/"""
    return Path.home() / ".config" / "typeless"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> dict:
    """加载配置，若不存在则返回默认配置并自动创建"""
    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 合并默认值（保证新字段有默认值）
            config = {**DEFAULT_CONFIG, **saved}
            return config
        except (json.JSONDecodeError, IOError):
            pass
    # 自动创建默认配置
    config = dict(DEFAULT_CONFIG)
    # 从环境变量读取 API Key（优先级高于配置文件）
    env_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if env_key:
        config["deepseek_api_key"] = env_key
    save_config(config)
    return config


def save_config(config: dict) -> None:
    """保存配置到文件"""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_api_key() -> str:
    """获取 DeepSeek API Key（环境变量优先）"""
    env_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if env_key:
        return env_key
    config = load_config()
    return config.get("deepseek_api_key", "")


# ── 对话记忆（用于 few-shot 润色）────────────────

def _memory_path() -> Path:
    return _config_dir() / "memory.json"


def load_memory() -> list[dict]:
    """加载历史润色记忆

    返回最近 N 条 [{raw, polished, lang, mode, time}, ...]
    """
    path = _memory_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_memory(memory: list[dict]) -> None:
    """保存润色记忆"""
    path = _memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def append_memory(raw: str, polished: str, lang: str, mode: str,
                  max_size: int = 5) -> None:
    """追加一条润色记录，保持不超过 max_size 条"""
    memory = load_memory()
    memory.append({
        "raw": raw,
        "polished": polished,
        "lang": lang,
        "mode": mode,
        "time": __import__("datetime").datetime.now().isoformat(),
    })
    # 只保留最近 max_size 条
    if len(memory) > max_size:
        memory = memory[-max_size:]
    save_memory(memory)
