"""DeepSeek 文本润色模块

通过 DeepSeek API（OpenAI 兼容）对语音识别文本进行智能润色：
1. 自动检测语言（中文/英文），使用对应的润色策略
2. 去除口语填充词
3. 识别自我修正，保留最终意图
4. 自动格式化列表/步骤为结构化文本
5. 修正语法错误，保持原意
"""

import re
from typing import Optional
from openai import OpenAI
from typeless.config import get_api_key, load_memory, append_memory, load_config


# ── 中文润色 Prompt ──────────────────────────

POLISH_CN_PROMPT = """你是一个专业的文本润色助手。对用户的语音转文字内容进行以下处理：

1. **去除填充词**：删除口语填充词，如：嗯、啊、呃、那个、这个、然后、就是、就是说、反正、你知道、怎么说呢、是吧、对不对…

2. **识别自我修正**：当用户说了又改口时（如"我觉得应该去...不对，应该这样做"），只保留最终意图，丢弃被修正的部分。

3. **自动格式化**：
   - 识别列举（"第一...第二...""首先...其次..."）→ 转为编号列表
   - 识别步骤说明 → 转为有序列表
   - 识别无序要点 → 转为 bullet points

4. **修正语法**：修正口语化的语法错误，补全不完整的句子，但保持原意不变。

5. **自动标点**：添加合适的标点符号（逗号、句号、问号等）。

输出规则：
- 直接输出润色后的文本，不要加任何解释或前缀
- 如果是零散的词组/短句，保持简短风格
- 如果是连续的叙述，整理为流畅的段落
- 保持第一人称和原始语气
- 使用中文全角标点"""


# ── 英文润色 Prompt ──────────────────────────

POLISH_EN_PROMPT = """You are a professional text polisher. Process the voice-to-text input as follows:

1. **Remove filler words**: Delete spoken filler words like: um, uh, er, you know, like, I mean, so, basically, actually, well, anyway, sort of, kind of, right, okay so...

2. **Detect self-corrections**: When the speaker stumbles or rephrases mid-sentence (e.g. "I think we should... no wait, we need to..."), keep only the final intended meaning and discard the aborted attempts.

3. **Auto-formatting**:
   - Detect enumerated points ("first... second...", "number one...") → convert to numbered lists
   - Detect step-by-step instructions → convert to ordered lists
   - Detect unstructured bullet points → format as markdown bullet list

4. **Fix grammar**: Correct spoken grammar errors, complete incomplete sentences, but preserve the original meaning and tone.

5. **Auto-punctuation**: Add appropriate punctuation (commas, periods, question marks, etc.).

Output rules:
- Output ONLY the polished text, no explanations or prefixes
- For short phrases/bullets, keep concise style
- For continuous narration, organize into fluent paragraphs
- Preserve first-person perspective and original tone"""


# ── 模式后缀 ──────────────────────────────────

CN_MODE_SUFFIX = {
    "general": "",
    "chat": "\n注意：这是即时通讯场景，保持口语化、简短，适合聊天消息的风格。",
    "email": "\n注意：这是邮件场景，输出正式的书面语，添加合适的称呼和落款格式。",
    "list": "\n注意：将内容组织为清晰的清单/列表格式。",
}

EN_MODE_SUFFIX = {
    "general": "",
    "chat": "\nNote: This is for instant messaging. Keep it casual, short, and chat-friendly.",
    "email": "\nNote: This is for email. Use formal written language with appropriate salutation and closing.",
    "list": "\nNote: Organize the content into a clear list/bullet format.",
}


def detect_language(text: str) -> str:
    """检测文本主要语言（启发式）

    策略：
    - 包含任何 CJK 字符 → 中文（保守策略，避免误判中英混合句）
    - 纯 ASCII 字母文本 → 英文
    - 其他 → 默认中文
    """
    if not text:
        return "zh"

    cjk_pattern = re.compile(r'[一-鿿㐀-䶿]')
    latin_pattern = re.compile(r'[a-zA-Z]')

    cjk_count = len(cjk_pattern.findall(text))
    latin_count = len(latin_pattern.findall(text))

    # 有中文字符 → 中文（技术词汇混入英文也不影响）
    if cjk_count > 0:
        return "zh"

    # 纯拉丁字母 → 英文
    if latin_count > 0:
        return "en"

    # 无法判断 → 默认中文
    return "zh"


class DeepSeekPolish:
    """DeepSeek 文本润色器（自动检测中/英文）"""

    def __init__(self, api_key: str = "", base_url: str = "https://api.deepseek.com"):
        self._api_key = api_key or get_api_key()
        self._base_url = base_url
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

    def polish(self, text: str, mode: str = "general",
               model: str = "") -> str:
        """润色文本（自动检测语言）

        Args:
            text: 待润色的原始文本
            mode: 润色模式 - general/chat/email/list
            model: DeepSeek 模型名，空则从配置读取

        Returns:
            润色后的文本。API 调用失败时返回原始文本。
        """
        if not text or not text.strip():
            return text

        if not self._api_key:
            print("[DeepSeek] 未配置 API Key，跳过润色")
            return text

        # 从配置读取模型（未指定时）
        if not model:
            config = load_config()
            model = config.get("deepseek_model", "deepseek-v4-flash")

        # 检测语言并选择对应的 prompt
        lang = detect_language(text)

        if lang == "en":
            base_prompt = POLISH_EN_PROMPT
            mode_suffix = EN_MODE_SUFFIX.get(mode, "")
        else:
            base_prompt = POLISH_CN_PROMPT
            mode_suffix = CN_MODE_SUFFIX.get(mode, "")

        system_prompt = base_prompt + mode_suffix

        # 加载历史记忆作为 few-shot 示例
        few_shot = self._build_few_shot(lang)
        if few_shot:
            system_prompt += few_shot

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=2048,
                timeout=30.0,
            )
            polished = response.choices[0].message.content.strip()

            # 保存到记忆（供下次 few-shot 使用）
            self._save_to_memory(raw=text, polished=polished, lang=lang, mode=mode)

            return polished
        except Exception as e:
            print(f"[DeepSeek] API 调用失败: {e}")
            return text

    def _build_few_shot(self, lang: str) -> str:
        """从记忆加载同语言的 few-shot 示例"""
        memory = load_memory()
        # 过滤同语言
        relevant = [m for m in memory if m.get("lang") == lang]
        if not relevant:
            return ""

        # 最近 N 条（最多 3 条，避免 prompt 过长）
        examples = relevant[-3:]
        parts = []
        for i, ex in enumerate(examples, 1):
            parts.append(
                f"\n示例{i}:\n"
                f"输入: {ex['raw']}\n"
                f"输出: {ex['polished']}"
            )

        prefix = "\n\n## 历史润色参考（请保持一致的风格）\n"
        return prefix + "\n".join(parts)

    def _save_to_memory(self, raw: str, polished: str,
                        lang: str, mode: str) -> None:
        """保存润色记录到记忆"""
        try:
            config = load_config()
            max_size = config.get("memory_size", 5)
            append_memory(raw, polished, lang, mode, max_size)
        except Exception:
            pass  # 记忆保存失败不影响主流程
