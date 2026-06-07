# -*- coding: utf-8 -*-
"""正規化された結果の型(辞書ベース)。

  window = {label, used_pct, remaining_pct, reset_at, detail}
  result = {name, ok, error, windows:[window...], note}
"""


def make_window(label, used_pct=None, remaining_pct=None, reset_at=None, detail=""):
    if remaining_pct is None and used_pct is not None:
        remaining_pct = max(0.0, 100.0 - used_pct)
    if used_pct is None and remaining_pct is not None:
        used_pct = max(0.0, 100.0 - remaining_pct)
    return {
        "label": label,
        "used_pct": used_pct,
        "remaining_pct": remaining_pct,
        "reset_at": reset_at,
        "detail": detail,
    }
