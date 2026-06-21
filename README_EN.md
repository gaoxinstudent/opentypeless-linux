# OpenTypeless-Linux

> 🎙️ Hold a hotkey, speak, and polished text appears right at your cursor — Linux finally has its Typeless.

## Features

- 🎤 **Local ASR** — Alibaba DAMO FunASR (Paraformer) on GPU, industrial-grade Chinese recognition, 100% offline
- ✨ **AI Full Refinement** — 7-step polish: punctuation segmentation → typo fix → synonym optimization → filler removal → self-correction → logic restructuring → formatting
- 🌐 **Bilingual** — Auto-detects Chinese/English, fixes homophone errors (在/再, their/there), custom filler word lists
- 📋 **Long Speech Structuring** — Auto-extracts key points into numbered outlines (一/二/三 or 1/2/3)
- 🧠 **Style Memory** — Saves history as few-shot examples, output style converges to your preference
- 🔥 **Global Hotkey** — Hold Right Ctrl, speak, release, done — works in any app
- 🖥️ **System Tray** — Runs quietly in background with status indicator
- 🔒 **Privacy First** — Voice recognition happens entirely on your GPU, audio never leaves your machine

## Quick Start

```bash
git clone https://github.com/gaoxinstudent/opentypeless-linux.git
cd opentypeless-linux
bash scripts/install_deps.sh
export DEEPSEEK_API_KEY="sk-your-api-key"
python3 -m typeless.main
```

**Requirements:** Ubuntu 22.04+ · NVIDIA GPU 4GB+ · Python 3.10+ · DeepSeek API Key

## How It Works

```
[Hold Hotkey] → [Record 16kHz] → [FunASR GPU ASR] → [DeepSeek Polish] → [Ctrl+V into app]
```

- Chinese: adds punctuation (。，、；：？！), fixes homophones (在/再, 的/得), optimizes synonyms, removes 20+ fillers, restructures logic
- English: adds punctuation, fixes homophones (their/there), optimizes word choice, removes disfluencies, restructures flow
- Auto-detects enumerations and reformats as markdown lists
- Long speech → auto-extracts key points as numbered outline
- Style memory persists across sessions for consistent output

## Tech Stack

| Module | Tech |
|--------|------|
| Speech Recognition | FunASR (Paraformer), RTF ~0.025, VRAM 0.8GB |
| Text Polish | DeepSeek V4 Flash | 7-step: punctuation → typos → synonyms → fillers → corrections → logic → format |
| Audio Capture | PyAudio, 16kHz mono 16-bit PCM |
| Hotkey | pynput (X11 global keyboard listener) |
| Text Injection | xdotool (clipboard + Ctrl+V) |
| System Tray | pystray + Pillow |
| Settings UI | tkinter (standalone subprocess) |

## Configuration

`~/.config/typeless/config.json`:

```json
{
  "deepseek_api_key": "sk-xxx",
  "deepseek_model": "deepseek-v4-flash",
  "hotkey": "<ctrl_r>",
  "polish_mode": "general",
  "remove_fillers": true,
  "auto_structure": true,
  "memory_size": 5
}
```

## vs Typeless

| | Typeless | OpenTypeless-Linux |
|---|---|---|
| Platform | macOS/Windows | **Linux** |
| Speech Recognition | Cloud API | **Local GPU (FunASR)** |
| Audio Privacy | Uploaded to server | **Never leaves your machine** |
| Text Polish | Proprietary model | **DeepSeek (bring your own key)** |
| License | Closed source | **MIT Open Source** |

## License

MIT
