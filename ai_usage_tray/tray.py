# -*- coding: utf-8 -*-
"""トレイ表示。テーマ検出・アイコン生成・常駐ループ。"""

import os
import sys
import time
import threading
import webbrowser

from .constants import ICON_COLOR_MODES, GITHUB_URL, AUTHOR_X_URL
from .state import cfg_lock, ui_lock
from .config import load_config
from .utils import run_cmd, fmt_reset
from .wsl import _wsl_default_help_text, _wsl_distro_blank_help_text
from .providers import PROVIDERS, PROVIDER_NAMES
from .collect import collect, min_remaining


def _windows_is_light_theme():
    """Windows のタスクバー(システム)テーマがライトなら True、ダークなら False。
    判定できなければ None。"""
    if os.name != "nt":
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        finally:
            winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return None


def make_icon_image(remaining, color_mode="classic"):
    from PIL import Image, ImageDraw
    light = _windows_is_light_theme()
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 残量で塗り色を決定(配色モードのパレットから引く。未知のモードは classic にフォールバック)
    palette = ICON_COLOR_MODES.get(color_mode, ICON_COLOR_MODES["classic"])
    if remaining is None:
        fill = (130, 130, 130, 255)
    elif remaining >= 50:
        fill = palette["high"]
    elif remaining >= 20:
        fill = palette["mid"]
    else:
        fill = palette["low"]

    # タスクバー背景に対して縁取りを反転(ライトなら暗い縁、ダークなら明るい縁)
    if light is True:
        outline = (45, 45, 45, 255)
    elif light is False:
        outline = (245, 245, 245, 255)
    else:
        outline = None

    if outline is not None:
        d.ellipse([3, 3, size - 3, size - 3], fill=fill, outline=outline, width=4)
    else:
        d.ellipse([4, 4, size - 4, size - 4], fill=fill)

    # 数字の色は塗り色の明るさで自動選択(黄色などは黒字、濃色は白字)
    txt = "?" if remaining is None else str(int(round(remaining)))
    lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
    text_color = (25, 25, 25, 255) if lum > 150 else (255, 255, 255, 255)

    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arialbd.ttf", 30 if len(txt) < 3 else 24)
    except Exception:
        font = None
    bbox = d.textbbox((0, 0), txt, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), txt,
           fill=text_color, font=font)
    return img


def run_tray(cfg):
    try:
        import pystray
        from pystray import MenuItem as Item, Menu
    except Exception:
        print("pystray / Pillow が必要です:  pip install pystray Pillow", file=sys.stderr)
        sys.exit(1)

    state = {"results": [], "lock": threading.Lock(),
             "remaining": None, "theme": _windows_is_light_theme(),
             "fetching": False, "pending": False}

    def _color_mode():
        # 設定差し替え中の空 dict を読まないようロック下で配色モードを取得する。
        with cfg_lock:
            return cfg.get("icon_color_mode", "classic")

    def show_settings(icon):
        def run_launcher():
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--settings"]
            else:
                # 起動に使われたエントリ(薄いランチャ ai_usage_tray.py か -m の __main__)を
                # そのまま再実行する。__file__ はパッケージ内モジュールを指してしまうため使わない。
                cmd = [sys.executable, sys.argv[0], "--settings"]

            # 設定ダイアログはユーザーがいつ閉じるか分からないため待ち時間に上限を設けない。
            # 上限があると、長く開いたまま保存してもタイムアウト済みで親プロセスの cfg が
            # 更新されず、表示が古いままになる (timeout=None で無期限に待つ)。
            rc, out, err = run_cmd(cmd, timeout=None)
            if rc == 0:
                new_cfg = load_config()
                # 取得スレッドが読み取り中の空 dict を見ないよう、clear+update を原子化する。
                with cfg_lock:
                    cfg.clear()
                    cfg.update(new_cfg)
                do_refresh(icon)

        threading.Thread(target=run_launcher, daemon=True).start()

    def _build_help_menu(Item, Menu):
        # 現在の配色モードに合わせて凡例(色と残量の対応)・使い方の要約・外部リンクを作る。
        with cfg_lock:
            mode = cfg.get("icon_color_mode", "classic")
            interval = int(cfg.get("refresh_seconds", 300))
        high_name = "青" if mode == "colorblind" else "緑"
        return Menu(
            Item("― 色と残量の見方 ―", None, enabled=False),
            Item(f"  50%以上 : {high_name}", None, enabled=False),
            Item("  20〜49% : 黄", None, enabled=False),
            Item("  20%未満 : 赤", None, enabled=False),
            Item("  取得不可 : 灰", None, enabled=False),
            Menu.SEPARATOR,
            Item("― 使い方 ―", None, enabled=False),
            Item(f"  自動更新: {interval}秒ごと", None, enabled=False),
            Item("  数字は一番余裕のない枠の残り%", None, enabled=False),
            Item("  配色は「設定...」で切替", None, enabled=False),
            Item(_wsl_default_help_text(), None, enabled=False),
            Item(_wsl_distro_blank_help_text(), None, enabled=False),
            Item("  不調時は --probe で診断", None, enabled=False),
            Menu.SEPARATOR,
            Item("GitHub を開く", lambda icon, item: webbrowser.open(GITHUB_URL)),
            Item("X (作者) を開く", lambda icon, item: webbrowser.open(AUTHOR_X_URL)),
        )

    def build_menu():
        items = []
        items.append(Item("AI Usage Tray", None, enabled=False))
        items.append(Menu.SEPARATOR)
        # cfg 差し替え中の空 dict を読まないよう、enabled をロック下でスナップショットする。
        with cfg_lock:
            enabled = dict(cfg.get("enabled", {}))
        with state["lock"]:
            results = list(state["results"])
            fetching = state["fetching"]
        if fetching:
            # 取得中は起動時と同様に「取得中」を出す。既存の結果行は残し、
            # 直前データを見たまま更新を待てるようにする。
            pending = [PROVIDER_NAMES.get(key, key) for key, _ in PROVIDERS
                       if enabled.get(key, True)]
            label = f"🔄 取得中... ({', '.join(pending)})" if pending else "🔄 取得中..."
            items.append(Item(label, None, enabled=False))
            items.append(Menu.SEPARATOR)
        elif not results:
            pending = [PROVIDER_NAMES.get(key, key) for key, _ in PROVIDERS
                       if enabled.get(key, True)]
            label = f"取得中... ({', '.join(pending)})" if pending else "取得中..."
            items.append(Item(label, None, enabled=False))
        for r in results:
            header = r["name"] if r["ok"] else f"{r['name']} ⚠"
            items.append(Item(header, None, enabled=False))
            if not r["ok"]:
                items.append(Item("   " + (r["error"] or "エラー")[:60], None, enabled=False))
            else:
                for w in r["windows"]:
                    if w["remaining_pct"] is not None:
                        head = f"残 {w['remaining_pct']:.0f}%"
                    elif w["detail"]:
                        head = w["detail"]
                    else:
                        head = "残量不明"
                    extra = f" ({w['detail']})" if (w["detail"] and w["remaining_pct"] is not None) else ""
                    items.append(Item(f"   {w['label']}: {head} · {fmt_reset(w['reset_at'])}{extra}",
                                      None, enabled=False))
                if r["note"]:
                    items.append(Item("   " + r["note"][:120], None, enabled=False))
            items.append(Menu.SEPARATOR)
        items.append(Item("ヘルプ", _build_help_menu(Item, Menu)))
        items.append(Item("設定...", lambda icon, item: show_settings(icon)))
        items.append(Item("今すぐ更新", lambda icon, item: threading.Thread(
            target=do_refresh, args=(icon,), daemon=True).start()))
        items.append(Item("終了", lambda icon, item: icon.stop()))
        return Menu(*items)

    def _apply_ui(icon):
        # 現在の state を元にアイコン/ツールチップ/メニューを再描画する。
        # UI スレッド外から呼んでよい(ui_lock で直列化)。
        if icon is None:
            return
        with state["lock"]:
            rem = state["remaining"]
            results = list(state["results"])
        with ui_lock:
            icon.icon = make_icon_image(rem, _color_mode())
            icon.title = build_tooltip(results)
            icon.menu = build_menu()
            icon.update_menu()

    def do_refresh(icon=None):
        # 取得処理は重い(API通信/サブプロセス)。必ず UI スレッド外で実行すること。
        # 単一フライト + pending: 取得中に来た更新要求は取りこぼさず、完了後にもう一度
        # 取得する。これにより設定保存直後の再取得が「実行中の(古い設定での)取得」に
        # 飲み込まれて反映されない問題を防ぐ。
        with state["lock"]:
            if state["fetching"]:
                state["pending"] = True   # 取得中の要求は完了後に消化
                return False              # 競合で繰り延べた(呼び出し側に通知)
            state["fetching"] = True
            state["pending"] = False
        _apply_ui(icon)            # 「取得中」を即時表示
        try:
            while True:
                results = collect(cfg)
                rem = min_remaining(results)
                with state["lock"]:
                    state["results"] = results
                    state["remaining"] = rem
                    state["theme"] = _windows_is_light_theme()
                    # 停止判定とフラグ解除を同一ロック内で原子的に行い、取りこぼしを防ぐ。
                    if state["pending"]:
                        state["pending"] = False
                        again = True
                    else:
                        state["fetching"] = False
                        again = False
                _apply_ui(icon)    # 結果(取得継続中なら中間結果)を反映
                if not again:
                    break
        except BaseException:
            with state["lock"]:
                state["fetching"] = False
                state["pending"] = False
            _apply_ui(icon)
            raise
        return True                 # 実際に取得を実行した

    def build_tooltip(results):
        with state["lock"]:
            fetching = state["fetching"]
        parts = []
        for r in results:
            if not r["ok"]:
                parts.append(f"{r['name']}: ⚠")
                continue
            rems = [w["remaining_pct"] for w in r["windows"] if w["remaining_pct"] is not None]
            if rems:
                parts.append(f"{r['name']}: {min(rems):.0f}%")
            else:
                parts.append(f"{r['name']}: OK")
        # 各プロバイダを改行で区切り、ホバー時に縦並びで見やすく表示する。
        head = "AI Usage（取得中...）" if fetching else "AI Usage"
        tip = head + "\n" + "\n".join(parts)
        # Windows 通知領域のツールチップは 127 文字までしか表示されない。超過分を安全に切り詰める。
        if len(tip) > 127:
            tip = tip[:124] + "..."
        return tip

    icon = pystray.Icon("ai_usage", make_icon_image(None, _color_mode()), "AI Usage 取得中...", menu=build_menu())

    def worker():
        while True:
            try:
                # do_refresh が False を返すのは手動更新/設定保存の取得と競合して
                # この回を繰り延べたとき。固定間隔で再試行すると、取得が長い環境
                # (Claude の version 取得や Antigravity CLI は最大 15〜60 秒待つ) では
                # fetching 中に何度も pending を立て直し、取得が止まらず API/CLI を
                # 連続実行するループになり得る。実行中の取得が完了するのを待ってから
                # 一度だけ取得し直し、定期更新を確実に1回行う。
                if do_refresh(icon) is False:
                    for _ in range(120):       # 完了待ちの安全上限(秒)
                        time.sleep(1)
                        with state["lock"]:
                            if not state["fetching"]:
                                break
                    do_refresh(icon)
            except Exception as e:
                print(f"[worker] {e}", file=sys.stderr)
            time.sleep(max(30, int(cfg.get("refresh_seconds", 300))))

    def theme_watcher():
        # システムテーマ(ライト/ダーク)を短い間隔で監視し、変化したら
        # 最後に描画した残量でアイコンを即時に作り直す(データ取得は待たない)。
        while True:
            time.sleep(3)
            try:
                theme = _windows_is_light_theme()
                with state["lock"]:
                    changed = theme != state["theme"]
                    rem = state["remaining"]
                    if changed:
                        state["theme"] = theme
                if changed:
                    with ui_lock:
                        icon.icon = make_icon_image(rem, _color_mode())
            except Exception as e:
                print(f"[theme_watcher] {e}", file=sys.stderr)

    threading.Thread(target=worker, daemon=True).start()
    if os.name == "nt":
        threading.Thread(target=theme_watcher, daemon=True).start()
    icon.run()
