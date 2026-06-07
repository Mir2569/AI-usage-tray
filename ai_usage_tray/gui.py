# -*- coding: utf-8 -*-
"""設定ダイアログ(tkinter)。別プロセスで起動され、保存時に config.json を書く。"""

import sys
import json

from .config import CONFIG_PATH


def run_settings_gui(cfg):
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        print("tkinter が利用できません。Python の標準インストールを確認してください。", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    root.title("AI Usage Tray 設定")
    root.geometry("460x620")
    root.resizable(False, False)

    default_font = ("Yu Gothic UI", 10)
    root.option_add("*Font", default_font)

    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # 1. 有効にするプロバイダ
    prov_lf = ttk.LabelFrame(main_frame, text="有効にするプロバイダ", padding="10")
    prov_lf.pack(fill=tk.X, pady=(0, 10))

    var_claude = tk.BooleanVar(value=cfg["enabled"].get("claude", True))
    var_codex = tk.BooleanVar(value=cfg["enabled"].get("codex", True))
    var_antigravity = tk.BooleanVar(value=cfg["enabled"].get("antigravity", True))

    ttk.Checkbutton(prov_lf, text="Claude Code (公式 OAuth API)", variable=var_claude).pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(prov_lf, text="Codex (ローカルセッションログ)", variable=var_codex).pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(prov_lf, text="Antigravity (antigravity-usage)", variable=var_antigravity).pack(anchor=tk.W, pady=2)

    # 2. 自動更新間隔
    interval_lf = ttk.LabelFrame(main_frame, text="更新間隔", padding="10")
    interval_lf.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(interval_lf, text="自動更新間隔 (秒):").pack(side=tk.LEFT)
    var_interval = tk.StringVar(value=str(cfg.get("refresh_seconds", 300)))
    ent_interval = ttk.Entry(interval_lf, textvariable=var_interval, width=8)
    ent_interval.pack(side=tk.LEFT, padx=5)
    ttk.Label(interval_lf, text="(最小30秒以上)").pack(side=tk.LEFT)

    # 3. WSL データソース
    wsl_lf = ttk.LabelFrame(main_frame, text="WSL データソース", padding="10")
    wsl_lf.pack(fill=tk.X, pady=(0, 10))

    wsl_cfg = cfg.get("wsl", {}) if isinstance(cfg.get("wsl", {}), dict) else {}
    wsl_enabled = wsl_cfg.get("enabled", {}) if isinstance(wsl_cfg.get("enabled", {}), dict) else {}
    var_wsl_distro = tk.StringVar(value=str(wsl_cfg.get("distro", "") or ""))
    var_wsl_claude = tk.BooleanVar(value=bool(wsl_enabled.get("claude", False)))
    var_wsl_codex = tk.BooleanVar(value=bool(wsl_enabled.get("codex", False)))
    var_wsl_antigravity = tk.BooleanVar(value=bool(wsl_enabled.get("antigravity", False)))

    distro_row = ttk.Frame(wsl_lf)
    distro_row.pack(fill=tk.X, pady=(0, 5))
    ttk.Label(distro_row, text="Distro:").pack(side=tk.LEFT)
    ttk.Entry(distro_row, textvariable=var_wsl_distro, width=24).pack(side=tk.LEFT, padx=5)
    ttk.Label(distro_row, text="(空欄=既定)").pack(side=tk.LEFT)
    ttk.Checkbutton(wsl_lf, text="Claude Code を WSL 側から取得", variable=var_wsl_claude).pack(anchor=tk.W, pady=1)
    ttk.Checkbutton(wsl_lf, text="Codex を WSL 側から取得", variable=var_wsl_codex).pack(anchor=tk.W, pady=1)
    ttk.Checkbutton(wsl_lf, text="Antigravity を WSL 側から取得", variable=var_wsl_antigravity).pack(anchor=tk.W, pady=1)
    ttk.Label(wsl_lf, text="※ WSL 側の認証情報・セッションログ・CLI を参照します。", font=("Yu Gothic UI", 9), foreground="gray").pack(anchor=tk.W)

    # 4. Antigravity の設定
    anti_lf = ttk.LabelFrame(main_frame, text="Antigravity 設定", padding="10")
    anti_lf.pack(fill=tk.X, pady=(0, 10))

    var_auto = tk.BooleanVar(value=cfg.get("antigravity_show_autocomplete", False))
    ttk.Checkbutton(anti_lf, text="オートコンプリート専用モデルも表示する", variable=var_auto).pack(anchor=tk.W, pady=(0, 5))
    ttk.Label(anti_lf, text="※ モデルは共通枠ごとに自動でまとめて表示されます。", font=("Yu Gothic UI", 9), foreground="gray").pack(anchor=tk.W)

    # 5. アイコン表示(配色モード)
    icon_lf = ttk.LabelFrame(main_frame, text="アイコン表示", padding="10")
    icon_lf.pack(fill=tk.X, pady=(0, 10))

    # 表示ラベル ↔ config 値 の対応。色弱の人向けに緑を青へ置き換えるモードを選べる。
    color_mode_labels = {"classic": "緑→黄→赤（標準）", "colorblind": "青→黄→赤（色弱対応）"}
    color_label_to_mode = {v: k for k, v in color_mode_labels.items()}
    current_mode = cfg.get("icon_color_mode", "classic")
    if current_mode not in color_mode_labels:
        current_mode = "classic"

    ttk.Label(icon_lf, text="配色モード:").pack(side=tk.LEFT)
    var_color_mode = tk.StringVar(value=color_mode_labels[current_mode])
    cmb_color = ttk.Combobox(icon_lf, textvariable=var_color_mode, state="readonly",
                             values=list(color_mode_labels.values()), width=20)
    cmb_color.pack(side=tk.LEFT, padx=5)

    # 保存/キャンセル
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

    def on_save():
        try:
            val = int(var_interval.get())
            if val < 30:
                raise ValueError()
        except ValueError:
            messagebox.showerror("エラー", "更新間隔には 30 以上の数値を入力してください。")
            return

        cfg["enabled"]["claude"] = var_claude.get()
        cfg["enabled"]["codex"] = var_codex.get()
        cfg["enabled"]["antigravity"] = var_antigravity.get()
        cfg["refresh_seconds"] = val
        cfg["antigravity_show_autocomplete"] = var_auto.get()
        cfg["icon_color_mode"] = color_label_to_mode.get(var_color_mode.get(), "classic")
        cfg["wsl"] = {
            "distro": var_wsl_distro.get().strip(),
            "enabled": {
                "claude": var_wsl_claude.get(),
                "codex": var_wsl_codex.get(),
                "antigravity": var_wsl_antigravity.get(),
            },
        }

        # 旧バージョンの設定に残っているモデルフィルタは不要になったため掃除する
        cfg.pop("antigravity_models", None)

        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存に失敗しました:\n{e}")

    def on_cancel():
        root.destroy()
        sys.exit(1)

    ttk.Button(btn_frame, text="保存", command=on_save).pack(side=tk.RIGHT, padx=5)
    ttk.Button(btn_frame, text="キャンセル", command=on_cancel).pack(side=tk.RIGHT)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()
