# -*- coding: utf-8 -*-
"""エントリポイント。argparse でモードを分岐する。

``python -m ai_usage_tray`` またはルートの薄いランチャ ``ai_usage_tray.py`` から呼ばれる。"""

import sys
import argparse

from .config import load_config, config_exists
from .collect import collect, summarize_text
from .gui import run_settings_gui
from .probe import run_probe
from .tray import run_tray


def main():
    ap = argparse.ArgumentParser(description="AI Usage Tray")
    ap.add_argument("--once", action="store_true", help="1回だけ取得してテキスト表示")
    ap.add_argument("--probe", action="store_true", help="各データソースの検出状況・正規化結果を表示")
    ap.add_argument("--probe-raw", action="store_true",
                    help="--probe に加えて外部 CLI の生出力も表示(redact 済みだが共有前に要確認)")
    ap.add_argument("--settings", action="store_true", help="設定ダイアログを表示")
    args = ap.parse_args()

    # Windows の cp932 コンソールだと中点(·)等の出力で UnicodeEncodeError になるため、
    # 標準出力/標準エラーを UTF-8(置換)に固定する(--once/--probe のテキスト表示用)。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    cfg = load_config()

    if args.settings:
        # 保存=0 / 取消=1 を exit code に変換(tray.py のサブプロセス経路が rc==0 で判定)。
        sys.exit(0 if run_settings_gui(cfg) else 1)
    if args.probe or args.probe_raw:
        run_probe(cfg, show_raw=args.probe_raw)
        return
    if args.once:
        print(summarize_text(collect(cfg)))
        return

    # 初回起動(config.json 不在)は、トレイ常駐の前に設定ダイアログで初期セットアップを促す。
    # run_settings_gui は cfg を直接書き換える(保存前に更新する)ため、保存有無に
    # かかわらずディスクから読み直してから常駐する。保存済みならその値、未保存
    # (キャンセル/× や保存失敗)なら config.json が無いまま既定設定が返るので、
    # 「取消時は既定設定のまま常駐し、次回起動で再度プロンプト」の仕様を満たす。
    if not config_exists():
        run_settings_gui(cfg)
        cfg = load_config()
    run_tray(cfg)


if __name__ == "__main__":
    main()
