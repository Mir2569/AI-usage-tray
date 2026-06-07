# -*- coding: utf-8 -*-
"""各 provider の取得結果の集約・最小残量算出・テキスト整形。"""

import copy
from datetime import datetime

from .state import cfg_lock
from .redact import mask_path, redact_text
from .utils import fmt_reset
from .providers import PROVIDERS


def collect(cfg):
    # 設定保存スレッドが cfg を差し替える瞬間に読んでも壊れないよう、ロック下で
    # スナップショットを取ってから各 provider を実行する(ネットワーク中はロックを保持しない)。
    with cfg_lock:
        cfg = copy.deepcopy(cfg)
    cfg["_wsl_cycle_cache"] = {}
    results = []
    for key, fn in PROVIDERS:
        if not cfg["enabled"].get(key, True):
            continue
        try:
            results.append(fn(cfg))
        except Exception as e:
            detail = mask_path(redact_text(str(e)))
            results.append({"name": key, "ok": False, "error": f"内部エラー: {detail}",
                            "windows": [], "note": ""})
    return results


def min_remaining(results):
    vals = []
    for r in results:
        for w in r["windows"]:
            if w["remaining_pct"] is not None:
                vals.append(w["remaining_pct"])
    return min(vals) if vals else None


def summarize_text(results):
    lines = []
    for r in results:
        if not r["ok"]:
            lines.append(f"● {r['name']}: ⚠ {r['error']}")
            continue
        lines.append(f"● {r['name']}")
        for w in r["windows"]:
            if w["remaining_pct"] is not None:
                pct = f"残 {w['remaining_pct']:.0f}%"
            elif w["detail"]:
                pct = w["detail"]
            else:
                pct = "残量 不明"
            extra = f"  {w['detail']}" if (w["detail"] and w["remaining_pct"] is not None) else ""
            lines.append(f"   {w['label']}: {pct} · {fmt_reset(w['reset_at'])}{extra}")
        if r["note"]:
            lines.append(f"   ※ {r['note']}")
    lines.append("")
    lines.append(f"更新: {datetime.now().strftime('%H:%M:%S')}")
    return "\n".join(lines)
