"""DeepSeek 文本润色模块

通过 DeepSeek API（OpenAI 兼容）对语音识别文本进行智能润色：
1. 自动检测语言（中文/英文），使用对应的润色策略
2. 去除口语填充词（内置 + 用户自定义）
3. 识别自我修正，保留最终意图
4. 自动格式化列表/步骤为结构化文本
5. 长语音自动提炼要点并编号
6. 对话记忆（few-shot）保持风格一致
"""

import re
from typing import Optional
from openai import OpenAI
from typeless.config import get_api_key, load_memory, append_memory, load_config


# ── 中文润色 Prompt 模板 ──────────────────────

_CN_FILLERS_BUILTIN = [
    "嗯", "啊", "呃", "哦", "那个", "这个",
    "然后", "就是", "就是说", "反正", "你知道",
    "怎么说呢", "是吧", "对不对", "那个啥", "这样子",
]

CN_PROMPT_TEMPLATE = """你是一个专业的文本润色助手。对用户的语音转文字内容进行以下处理：

1. **去除填充词**：删除口语填充词，包括但不限于：
   {filler_list}
   {custom_filler_note}

2. **识别自我修正**：当用户说了又改口时（如"我觉得应该去...不对，应该这样做"），只保留最终意图，丢弃被修正的部分。

3. **自动格式化**：
   - 识别列举（"第一...第二...""首先...其次..."）→ 转为编号列表
   - 识别步骤说明 → 转为有序列表
   - 识别无序要点 → 转为 bullet points
{long_structure_rule}
4. **修正语法**：修正口语化的语法错误，补全不完整的句子，但保持原意不变。

5. **自动标点**：添加合适的标点符号（逗号、句号、问号等）。

输出规则：
- 直接输出润色后的文本，不要加任何解释或前缀
- 如果是零散的词组/短句，保持简短风格
- 如果是连续的叙述，整理为流畅的段落
- 保持第一人称和原始语气
- 使用中文全角标点"""


# ── 英文润色 Prompt 模板 ──────────────────────

_EN_FILLERS_BUILTIN = [
    "um", "uh", "er", "you know", "like", "I mean",
    "so", "basically", "actually", "well", "anyway",
    "sort of", "kind of", "right", "okay so", "I guess",
]

EN_PROMPT_TEMPLATE = """You are a professional text polisher. Process the voice-to-text input as follows:

1. **Remove filler words**: Delete spoken filler words including but not limited to:
   {filler_list}
   {custom_filler_note}

2. **Detect self-corrections**: When the speaker stumbles or rephrases mid-sentence (e.g. "I think we should... no wait, we need to..."), keep only the final intended meaning and discard the aborted attempts.

3. **Auto-formatting**:
   - Detect enumerated points ("first... second...", "number one...") → convert to numbered lists
   - Detect step-by-step instructions → convert to ordered lists
   - Detect unstructured bullet points → format as markdown bullet list
{long_structure_rule}
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

# 长语音结构化规则
CN_LONG_STRUCTURE_RULE = """   - **长语音要点提炼**：如果输入内容较长且包含多个观点或事项，请提取核心要点，用「一、... 二、... 三、...」的格式输出。每个要点保持简洁，提炼关键信息。"""

EN_LONG_STRUCTURE_RULE = """   - **Long speech structuring**: If the input is lengthy and contains multiple points or topics, extract the key points and output them as a numbered outline (1. ... 2. ... 3. ...). Keep each point concise and focused."""


# ── 语言检测 ──────────────────────────────────

def detect_language(text: str) -> str:
    """检测文本主要语言

    策略：
    - 包含任何 CJK 字符 → 中文
    - 纯 ASCII 字母文本 → 英文
    - 其他 → 默认中文
    """
    if not text:
        return "zh"

    cjk_pattern = re.compile(r'[一-鿿㐀-䶿]')
    latin_pattern = re.compile(r'[a-zA-Z]')

    cjk_count = len(cjk_pattern.findall(text))
    latin_count = len(latin_pattern.findall(text))

    if cjk_count > 0:
        return "zh"
    if latin_count > 0:
        return "en"
    return "zh"


# ── Prompt 构建 ────────────────────────────────

def _build_cn_prompt(config: dict) -> str:
    """动态构建中文润色 prompt"""
    all_fillers = list(dict.fromkeys(_CN_FILLERS_BUILTIN))  # 保持顺序去重
    custom = config.get("custom_fillers_zh", [])
    for w in custom:
        if w not in all_fillers:
            all_fillers.append(w)

    filler_list = "、".join(all_fillers)

    if custom:
        custom_filler_note = f"   额外屏蔽（用户指定）：{'、'.join(custom)}"
    else:
        custom_filler_note = ""

    # 长语音结构化
    long_rule = ""
    if config.get("auto_structure_long", True):
        long_rule = CN_LONG_STRUCTURE_RULE + "\n"

    prompt = CN_PROMPT_TEMPLATE.format(
        filler_list=filler_list,
        custom_filler_note=custom_filler_note,
        long_structure_rule=long_rule,
    )
    return prompt


def _build_en_prompt(config: dict) -> str:
    """动态构建英文润色 prompt"""
    all_fillers = list(dict.fromkeys(_EN_FILLERS_BUILTIN))
    custom = config.get("custom_fillers_en", [])
    for w in custom:
        if w not in all_fillers:
            all_fillers.append(w)

    filler_list = ", ".join(all_fillers)

    if custom:
        custom_filler_note = f"   Additionally remove (user-specified): {', '.join(custom)}"
    else:
        custom_filler_note = ""

    long_rule = ""
    if config.get("auto_structure_long", True):
        long_rule = EN_LONG_STRUCTURE_RULE + "\n"

    prompt = EN_PROMPT_TEMPLATE.format(
        filler_list=filler_list,
        custom_filler_note=custom_filler_note,
        long_structure_rule=long_rule,
    )
    return prompt


# ── 润色器 ─────────────────────────────────────

class DeepSeekPolish:
    """DeepSeek 文本润色器（自动检测中/英文、支持自定义屏蔽词）"""

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

        config = load_config()
        if not model:
            model = config.get("deepseek_model", "deepseek-v4-flash")

        # 检测语言并动态构建 prompt
        lang = detect_language(text)

        if lang == "en":
            base_prompt = _build_en_prompt(config)
            mode_suffix = EN_MODE_SUFFIX.get(mode, "")
        else:
            base_prompt = _build_cn_prompt(config)
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

            self._save_to_memory(raw=text, polished=polished, lang=lang, mode=mode)
            return polished
        except Exception as e:
            print(f"[DeepSeek] API 调用失败: {e}")
            return text

    def _build_few_shot(self, lang: str) -> str:
        """从记忆加载同语言的 few-shot 示例"""
        memory = load_memory()
        relevant = [m for m in memory if m.get("lang") == lang]
        if not relevant:
            return ""

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
            pass
