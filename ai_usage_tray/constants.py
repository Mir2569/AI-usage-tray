# -*- coding: utf-8 -*-
"""アプリ全体で共有する定数。"""

import os

HOME = os.path.expanduser("~")

# 配布元・作者リンク(ヘルプメニューから開く)
GITHUB_URL = "https://github.com/Mir2569/ai-usage-tray"
AUTHOR_X_URL = "https://x.com/E_Mir_a"

# トレイアイコンの配色モード。残量しきい値(>=50 / >=20 / <20)ごとの塗り色を定義する。
# 文字色は塗り色の明度から自動選択(make_icon_image)。None(取得不可)の灰は別扱い。
ICON_COLOR_MODES = {
    # 緑→黄→赤(標準)
    "classic":    {"high": (46, 160, 67, 255),  "mid": (210, 153, 34, 255), "low": (218, 54, 51, 255)},
    # 青→黄→赤(色弱対応)。high を緑から青(#2563EB)に変更し、緑/赤の混同を避ける。
    "colorblind": {"high": (37, 99, 235, 255),  "mid": (210, 153, 34, 255), "low": (218, 54, 51, 255)},
}
