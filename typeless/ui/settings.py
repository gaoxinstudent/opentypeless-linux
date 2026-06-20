"""设置管理

两种方式打开设置：
1. 用系统默认编辑器直接打开配置文件（最稳健）
2. tkinter GUI 对话框（可选，当 tkinter 线程可用时）
"""

import subprocess
import os
from typeless.config import _config_path


def open_config_in_editor():
    """用系统默认编辑器打开配置文件（100% 可靠）"""
    config_path = str(_config_path())

    # 确保目录存在
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # 如果配置文件不存在，创建一个带注释的模板
    if not os.path.exists(config_path):
        _create_template_config(config_path)

    # 尝试多种编辑器
    editors = [
        ["gedit", config_path],
        ["gnome-text-editor", config_path],
        ["kate", config_path],
        ["mousepad", config_path],
        ["nano", config_path],
        ["xdg-open", config_path],
    ]

    for editor_cmd in editors:
        try:
            subprocess.Popen(
                editor_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            continue
    return False


def _create_template_config(path: str):
    """创建带注释的模板配置文件"""
    template = """{
    // ============================================================
    // Typeless 配置文件
    // 编辑完成后保存即可，新设置将在下次录音时生效。
    // ============================================================

    // DeepSeek API Key (在 https://platform.deepseek.com 获取)
    "deepseek_api_key": "",

    // DeepSeek API 地址 (默认不需要改)
    "deepseek_base_url": "https://api.deepseek.com",

    // DeepSeek 模型: deepseek-v4-flash(快速) | deepseek-chat(标准)
    "deepseek_model": "deepseek-v4-flash",

    // 热键 (按住说话): <ctrl_r> <ctrl_l> <alt> <shift> <f1>-<f12>
    "hotkey": "<ctrl_r>",

    // 润色模式: general(通用) | chat(聊天) | email(邮件) | list(清单)
    "polish_mode": "general",

    // 是否自动去除填充词 (嗯、啊、那个…)
    "remove_fillers": true,

    // 是否自动结构化 (列表、步骤等)
    "auto_structure": true,

    // 音频输入设备 (null = 系统默认)
    "audio_device": null
}
"""
    # 去掉 JSON 不支持的注释行
    import json
    clean_lines = []
    for line in template.split('\n'):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*'):
            continue
        clean_lines.append(line)

    clean_json = '\n'.join(clean_lines)
    # 验证是合法 JSON
    try:
        parsed = json.loads(clean_json)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        # 不应该发生，兜底
        pass


def open_settings_dialog(app=None):
    """打开设置（优先 GUI，不可用时回退到编辑器）"""
    # 尝试 tkinter GUI
    try:
        _open_tkinter_dialog(app)
        return
    except Exception:
        pass

    # 回退：用编辑器打开配置文件
    open_config_in_editor()


def _open_tkinter_dialog(app):
    """tkinter GUI 设置对话框"""
    import tkinter as tk
    from tkinter import ttk, messagebox
    from typeless.config import load_config, save_config

    HOTKEY_OPTIONS = [
        ("右 Ctrl", "<ctrl_r>"),
        ("左 Ctrl", "<ctrl_l>"),
        ("Ctrl", "<ctrl>"),
        ("右 Alt", "<alt_r>"),
        ("Alt", "<alt>"),
        ("Shift", "<shift>"),
    ]

    POLISH_MODES = [
        ("通用", "general"),
        ("聊天消息", "chat"),
        ("邮件", "email"),
        ("清单列表", "list"),
    ]

    config = load_config()

    root = tk.Tk()
    root.title("Typeless 设置")
    root.resizable(False, False)

    main = ttk.Frame(root, padding=10)
    main.pack(fill="both", expand=True)

    # ── API Key ──
    api_frame = ttk.LabelFrame(main, text="DeepSeek API", padding=10)
    api_frame.pack(fill="x", padx=0, pady=4)

    ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
    api_entry = ttk.Entry(api_frame, width=42, show="•")
    api_entry.insert(0, config.get("deepseek_api_key", ""))
    api_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(api_frame, text="Base URL:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
    url_entry = ttk.Entry(api_frame, width=42)
    url_entry.insert(0, config.get("deepseek_base_url", "https://api.deepseek.com"))
    url_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=3)

    # ── 热键 ──
    hk_frame = ttk.LabelFrame(main, text="热键设置", padding=10)
    hk_frame.pack(fill="x", padx=0, pady=4)

    ttk.Label(hk_frame, text="触发键:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
    hk_var = tk.StringVar()
    hk_combo = ttk.Combobox(hk_frame, textvariable=hk_var,
                            values=[l for l, _ in HOTKEY_OPTIONS],
                            state="readonly", width=18)
    hk_val = config.get("hotkey", "<ctrl_r>")
    hk_label = next((l for l, v in HOTKEY_OPTIONS if v == hk_val), "右 Ctrl")
    hk_var.set(hk_label)
    hk_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(hk_frame, text="💡 按住热键说话，松开后自动处理",
              foreground="#888").grid(row=1, column=0, columnspan=2, pady=(0, 4))

    # ── 润色 ──
    pol_frame = ttk.LabelFrame(main, text="文本润色", padding=10)
    pol_frame.pack(fill="x", padx=0, pady=4)

    ttk.Label(pol_frame, text="模式:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
    pol_var = tk.StringVar()
    pol_combo = ttk.Combobox(pol_frame, textvariable=pol_var,
                             values=[l for l, _ in POLISH_MODES],
                             state="readonly", width=18)
    pol_val = config.get("polish_mode", "general")
    pol_label = next((l for l, v in POLISH_MODES if v == pol_val), "通用")
    pol_var.set(pol_label)
    pol_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

    rm_var = tk.BooleanVar(value=config.get("remove_fillers", True))
    ttk.Checkbutton(pol_frame, text="去除口语填充词（嗯、啊、那个…）",
                    variable=rm_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=2)

    struct_var = tk.BooleanVar(value=config.get("auto_structure", True))
    ttk.Checkbutton(pol_frame, text="自动格式化为列表/步骤",
                    variable=struct_var).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=2)

    # ── 按钮 ──
    btn_frame = ttk.Frame(main)
    btn_frame.pack(fill="x", pady=(12, 0))

    def on_save():
        config["deepseek_api_key"] = api_entry.get().strip()
        config["deepseek_base_url"] = url_entry.get().strip()
        hkl = hk_var.get()
        config["hotkey"] = next((v for l, v in HOTKEY_OPTIONS if l == hkl), "<ctrl_r>")
        pl = pol_var.get()
        config["polish_mode"] = next((v for l, v in POLISH_MODES if l == pl), "general")
        config["remove_fillers"] = rm_var.get()
        config["auto_structure"] = struct_var.get()
        save_config(config)
        if app:
            app.config = config
            app.polish._api_key = config["deepseek_api_key"]
        messagebox.showinfo("Typeless", "配置已保存 ✓")
        root.destroy()

    ttk.Button(btn_frame, text="保存", command=on_save).pack(side="right", padx=4)
    ttk.Button(btn_frame, text="取消", command=root.destroy).pack(side="right", padx=4)

    root.lift()
    root.focus_force()
    root.mainloop()


# 作为独立脚本运行时，直接打开 GUI 设置窗口
if __name__ == "__main__":
    _open_tkinter_dialog(app=None)
