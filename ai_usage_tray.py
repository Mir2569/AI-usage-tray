#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Usage Tray  -  薄いランチャ。

本体は ``ai_usage_tray/`` パッケージに分割されている(Issue #55)。
このファイルは配布・起動スクリプト(run.bat / start_hidden.vbs / setup.bat /
build_exe.bat / AIUsageTray.spec)が参照するエントリを維持するための薄い入口で、
実体は ``ai_usage_tray.__main__.main`` に委譲する。``python -m ai_usage_tray`` でも起動可。

使い方:
    python ai_usage_tray.py            # トレイ常駐で起動
    python ai_usage_tray.py --once     # 1回だけ取得してテキスト表示(テスト用)
    python ai_usage_tray.py --probe    # 各データソースの生データを表示(設定の診断用)
    python ai_usage_tray.py --probe-raw# 上記に加えて外部 CLI の生出力(redact 済み)
    python ai_usage_tray.py --settings # 設定ダイアログを表示

設定は同じフォルダの config.json で上書き可能(無ければ既定値)。
"""

from ai_usage_tray.__main__ import main

if __name__ == "__main__":
    main()
