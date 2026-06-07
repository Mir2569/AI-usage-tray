# -*- coding: utf-8 -*-
"""設定の既定値・読み込み・パス解決(凍結対応)。"""

import os
import sys
import json

# PyInstaller などで exe 化(凍結)された場合は exe のあるフォルダを基準にする。
# 非凍結時はパッケージの親ディレクトリ(= リポジトリ/配布ルート)を基準にする。
# 注意: __file__ はこのファイル(ai_usage_tray/config.py)を指すため、dirname を 2 回
# たどってパッケージの親 = config.json の置き場所(薄いランチャと同階層)に合わせる。
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

DEFAULT_CONFIG = {
    "refresh_seconds": 300,            # 自動更新間隔(秒)
    "codex_max_days": 10,              # Codex セッションログの走査日数
    "enabled": {"claude": True, "codex": True, "antigravity": True},
    # トレイアイコンの配色モード。"classic"(緑→黄→赤) / "colorblind"(青→黄→赤)
    "icon_color_mode": "classic",
    # Antigravity のオートコンプリート専用モデルも表示するか(既定は非表示)
    "antigravity_show_autocomplete": False,
    # antigravity-usage が未検出のとき npx 経由で取得するか(既定は無効=opt-in)。
    # 有効にすると常駐アプリがバックグラウンドで npm からパッケージを取得・実行する。
    "antigravity_npx_fallback": False,
    # npx フォールバック時に使う antigravity-usage の固定バージョン。
    # 空文字にすると無印(最新)になるが、サプライチェーンの観点から非推奨。
    "antigravity_usage_version": "0.2.9",
    # WSL 側のデータソースを provider ごとに使う設定。distro 空欄なら既定 distro。
    # enabled を有効化した provider だけ、WSL 内の credentials / sessions / CLI を参照する。
    "wsl": {
        "distro": "",
        "enabled": {"claude": False, "codex": False, "antigravity": False},
    },
    # コマンドの明示パス(自動検出に失敗する場合のみ設定)
    "paths": {"antigravity_usage": ""},
}


def _deep_merge_and_validate(default_cfg, user_cfg, path=""):
    for k, v in user_cfg.items():
        current_path = f"{path}.{k}" if path else k
        if k not in default_cfg:
            # デフォルトに存在しないキーはそのまま受け入れる
            default_cfg[k] = v
            continue

        default_val = default_cfg[k]

        # 双方とも辞書型の場合は再帰マージ
        if isinstance(default_val, dict) and isinstance(v, dict):
            _deep_merge_and_validate(default_val, v, current_path)
        # 型が不一致の場合（bool は int のサブクラスなので type で厳密チェック、ただし int/float の相互変換は許容。boolは除外）
        elif type(default_val) is not type(v) and not (isinstance(default_val, (int, float)) and isinstance(v, (int, float)) and not isinstance(default_val, bool) and not isinstance(v, bool)):
            print(f"[config] 警告: キー '{current_path}' の型が不一致です（期待: {type(default_val).__name__}, 入力: {type(v).__name__}）。デフォルト値を使用します。", file=sys.stderr)
        else:
            default_cfg[k] = v


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user = json.load(f)
        if isinstance(user, dict):
            _deep_merge_and_validate(cfg, user)
        else:
            print("[config] 警告: 設定ファイルのルート要素が辞書型ではありません。デフォルト設定を使用します。", file=sys.stderr)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[config] 読み込みエラー: {e}", file=sys.stderr)
    return cfg
