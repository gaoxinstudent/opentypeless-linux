# Typeless-Linux

> 🎙️ 智能语音输入工具 — Linux 桌面端的 Typeless 替代实现

**按住热键说话，AI 自动润色，文字直接出现在你的光标位置。**

## 特性

- 🎤 **语音识别**：基于阿里达摩院 FunASR (Paraformer) 模型，中文识别精度领先，本地 GPU 推理
- ✨ **AI 润色**：通过 DeepSeek API 自动去除口语填充词、识别自我修正、结构化格式化
- 🌐 **中英双语**：自动检测语音语言，中文去「嗯啊那个」，英文去「um/like/you know」
- 🧠 **风格记忆**：保存历史润色记录作为 few-shot 示例，输出风格越来越一致
- 🔥 **全局热键**：按住右 Ctrl 说话，松手即完成识别→润色→粘贴
- 🖥️ **系统托盘**：后台静默运行，托盘图标显示状态（灰/红/黄）
- 🔊 **音频反馈**：录音开始/结束有提示音 + 桌面通知
- 🔒 **隐私安全**：语音识别全在本地 GPU 完成，语音数据不出本机
- 📝 **跨应用支持**：在任意应用（VSCode、浏览器、终端、聊天工具）中使用

## 环境要求

- Ubuntu 22.04+ (X11)
- NVIDIA GPU (4GB+ 显存) 或 CPU 模式
- Python 3.10+
- DeepSeek API Key ([获取地址](https://platform.deepseek.com))

## 快速开始

### 1. 安装依赖

```bash
bash scripts/install_deps.sh
```

### 2. 配置 API Key

```bash
# 方式一：环境变量（推荐，不会写入磁盘）
export DEEPSEEK_API_KEY="sk-your-api-key"

# 方式二：在设置界面中配置（自动保存到 ~/.config/typeless/config.json）
```

### 3. 启动

```bash
python3 -m typeless.main
```

首次运行会自动下载语音识别模型（约 860MB），请耐心等待。

### 4. 使用

1. 光标放到任何输入框
2. **按住右 Ctrl**，开始说话
3. **松开右 Ctrl**，等待 1-3 秒
4. 润色后的文字自动出现在光标位置 ✨

## 项目结构

```
typeless-linux/
├── typeless/
│   ├── main.py                 # 主入口，整合完整流水线
│   ├── config.py               # 配置管理 + 对话记忆
│   ├── audio/
│   │   └── recorder.py         # PyAudio 录音 + 麦克风检测 + 提示音
│   ├── asr/
│   │   └── funasr_client.py    # FunASR Paraformer 语音识别
│   ├── polish/
│   │   └── deepseek_polish.py  # DeepSeek 文本润色 (中英双语 + few-shot)
│   ├── input/
│   │   └── text_injector.py    # xdotool 文本注入 (剪贴板 + Ctrl+V)
│   └── ui/
│       ├── tray.py             # pystray 系统托盘
│       └── settings.py         # tkinter 设置界面 (支持独立进程)
├── scripts/
│   ├── install_deps.sh         # 依赖安装脚本
│   └── start_funasr_server.sh  # FunASR WebSocket 服务 (备用)
├── requirements.txt
├── setup.py
└── README.md
```

## 架构

```
[按住热键] → [PyAudio 16kHz 录音] → [FunASR GPU 识别]
                                            ↓
[Ctrl+V 注入] ← [xdotool 粘贴] ← [DeepSeek 润色]
                                            ↓
                              [自动检测中/英文]
                              [加载历史 few-shot]
                              [保存到记忆]
```

- 录音在后台线程执行，不阻塞热键监听
- ASR 推理在 ThreadPoolExecutor 中串行执行
- 润色 API 调用包含 30s 超时，失败时降级为原始文本
- 设置界面作为独立子进程运行，与主进程隔离
- 配置文件 + 记忆文件存储在 `~/.config/typeless/`

## 配置说明

配置文件位置：`~/.config/typeless/config.json`

```json
{
  "deepseek_api_key": "sk-xxx",
  "deepseek_base_url": "https://api.deepseek.com",
  "deepseek_model": "deepseek-v4-flash",
  "hotkey": "<ctrl_r>",
  "polish_mode": "general",
  "remove_fillers": true,
  "auto_structure": true,
  "memory_size": 5
}
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `deepseek_model` | `deepseek-v4-flash` | 模型：flash(快速)/chat(标准)/reasoner(推理) |
| `hotkey` | `<ctrl_r>` | 全局热键 |
| `polish_mode` | `general` | 润色风格：general/chat/email/list |
| `remove_fillers` | `true` | 是否去填充词 |
| `auto_structure` | `true` | 是否自动格式化列表 |
| `memory_size` | `5` | 历史记忆条数（few-shot 示例） |

### 润色模式

| 模式 | 说明 |
|------|------|
| `general` | 通用模式，平衡口语化和正式度 |
| `chat` | 聊天模式，保持简短口语化 |
| `email` | 邮件模式，输出正式书面语 |
| `list` | 清单模式，将内容转为结构化列表 |

## 技术栈

| 模块 | 技术 | 说明 |
|------|------|------|
| 语音识别 | FunASR (Paraformer) | 阿里达摩院开源，RTF ~0.025，显存 0.8GB |
| 文本润色 | DeepSeek V4 Flash | OpenAI 兼容接口，自动缓存 system prompt |
| 语言检测 | 启发式规则 | CJK 字符存在 → 中文；纯拉丁 → 英文 |
| 对话记忆 | JSON 持久化 | few-shot 示例注入 system prompt |
| 音频捕获 | PyAudio | 16kHz 单声道 16bit PCM |
| 全局热键 | pynput | X11 键盘监听 |
| 文本注入 | xdotool | 剪贴板 + Ctrl+V（Ctrl+Shift+V 兜底） |
| 系统托盘 | pystray + Pillow | 三色状态图标（灰待机/红录音/黄处理） |
| 设置界面 | tkinter | Python 内置，独立进程运行 |
| 桌面通知 | notify-send | GNOME/KDE 原生通知 |

## 修改日志

### v0.1.0 (2026-06-21) — 初始版本

**核心流水线**
- 实现完整 Push-to-Talk 流水线：录音 → ASR → 润色 → 粘贴
- FunASR Paraformer-large 模型集成，GPU 实时推理 (RTF ~0.025)
- DeepSeek API 文本润色，支持 system prompt 自动缓存

**语言支持**
- 中英双语自动检测（CJK 启发式规则）
- 中文润色：去除「嗯/啊/那个/然后」等 20+ 填充词
- 英文润色：去除「um/uh/like/you know」等填充词
- 自动识别自我修正，保留最终意图
- 口语列表 → 结构化 markdown 格式

**对话记忆**
- 历史润色记录持久化到 `~/.config/typeless/memory.json`
- 同语言最近 N 条作为 few-shot 示例注入 prompt
- 风格逐渐与用户偏好对齐

**系统托盘**
- pystray 系统托盘，三种状态图标（灰/红/黄）
- 右键菜单：状态显示、设置、重载模型、退出
- 桌面通知提醒各阶段状态

**设置界面**
- tkinter 设置对话框（独立子进程，与主进程隔离）
- 支持编辑 API Key、Base URL、模型、热键、润色模式
- 回退方案：用系统编辑器打开配置文件

**音频**
- PyAudio 16kHz 单声道录音
- 启动时自动检测麦克风可用性
- 录音开始/结束提示音（高音 1200Hz / 低音 600Hz）
- 多播放器兼容（aplay / paplay / sox）

**文本注入**
- X11: 剪贴板 + xdotool Ctrl+V
- 兜底: xdotool type 逐字输入
- Wayland 兼容预留（wtype）

**Bug 修复**
- 修复 `pa.get_device_info()` → `get_device_info_by_index()` API 错误
- 修复 PyQt6 线程冲突 → 改用 tkinter + 独立进程
- 修复 tkinter 根窗口复用导致第二次打开失败
- 修复 NumPy 2.x 与 scipy 兼容性 → 降级 NumPy
- 修复 numba/coverage 模块冲突 → 升级 coverage

## 故障排查

### 模型加载失败
- 确保磁盘空间 > 2GB
- 手动下载模型：`python3 -c "from modelscope import snapshot_download; snapshot_download('iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch')"`

### 检测不到麦克风
- 检查 USB/蓝牙连接
- 运行 `pactl list sources short` 确认 PulseAudio 能看到设备
- 检查默认输入设备：`pactl info | grep "Default Source"`

### 文本无法注入
- 确认 xdotool 已安装：`sudo apt install xdotool`
- 在 X11 下运行（`echo $XDG_SESSION_TYPE` 应输出 `x11`）

### DeepSeek API 报错
- 检查 API Key 是否正确
- 确认网络能访问 `api.deepseek.com`
- 查看日志：启动终端中的 `[DeepSeek]` 前缀错误信息

### 设置界面不弹出
- 确认已安装 `python3-tk`：`sudo apt install python3-tk`
- 设置界面作为独立子进程运行，检查终端是否有错误输出

## License

MIT
