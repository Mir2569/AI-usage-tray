# -*- coding: utf-8 -*-
"""複数モジュールから参照される共有ロック・キャッシュ。

専用モジュールに集約することで provider / collect / tray / probe 間の
循環 import を避ける。"""

import threading

# 共有設定 cfg への並行アクセス(設定保存スレッドの差し替え vs 取得スレッドの読み取り)を
# 直列化するためのロック。差し替え中の一時的な空 dict を読んで KeyError になるのを防ぐ。
cfg_lock = threading.Lock()

# Claude API レスポンスの 90 秒キャッシュとその排他ロック(provider と probe で共用)。
claude_lock = threading.Lock()
_claude_cache = {"ts": 0.0, "data": None, "source": None}

# トレイ UI(アイコン/メニュー更新)を直列化するロック。
ui_lock = threading.Lock()
