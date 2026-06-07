# -*- coding: utf-8 -*-
"""Provider: Codex  (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl)。"""

import os
import json
import time
from datetime import datetime, timezone, timedelta

from ..constants import HOME
from ..utils import parse_dt, fmt_age, now_utc
from ..redact import mask_path, redact_text
from ..wsl import (
    _provider_uses_wsl,
    _wsl_running_status,
    _wsl_linux_command_exists,
    _wsl_label,
    run_wsl_cmd,
)
from .types import make_window


def _iter_rollout_files(sessions_dir):
    """sessions_dir 配下の rollout-*.jsonl を (path, mtime) で再帰列挙する。
    os.scandir を使い、stat を1回(Windows ではディレクトリ列挙時にキャッシュ済みで
    追加 syscall が不要)に抑えることで、大量ファイル時の走査負荷を下げる。"""
    stack = [sessions_dir]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif (entry.name.startswith("rollout-")
                              and entry.name.endswith(".jsonl")):
                            yield entry.path, entry.stat().st_mtime
                    except OSError:
                        continue
        except OSError:
            continue


def _rl_is_usable(rl):
    """rate_limits dict が primary または secondary に有効な枠データ(dict)を持つか判定する。
    Free の月次100%到達直後に出る終端イベントは primary/secondary が null になるため
    この判定で弾き、直前の有用なイベントを優先選択するために使う。"""
    return isinstance(rl.get("primary"), dict) or isinstance(rl.get("secondary"), dict)


def find_latest_codex_event(sessions_dir, max_days=10):
    """最新の rate_limits イベントと診断メタ情報を返す。

    2本追跡:
    - best_usable: primary か secondary が dict であるイベントのうち最新
    - best_any   : 全 rate_limits イベント中の最新（フォールバック）
    usable がある場合は best_usable を返し、終端 null イベントを掴まない。
    """
    meta = {
        "candidate_files": 0,
        "scanned_files": 0,
        "rate_limit_events": 0,
        "file_mtime": None,
        "line_number": None,
    }
    if not os.path.isdir(sessions_dir):
        return None, None, None, meta
    # セッションファイルは "セッション開始日" の YYYY/MM/DD 配下に置かれ、その後も
    # 追記され得る(開始が max_days より前でも、今日 rate_limits が更新されることがある)。
    # そのため日付ディレクトリでの絞り込みでは最新イベントを取りこぼすので、全ファイルを
    # mtime で評価する。ただし os.scandir で stat を1回に抑え(Windows ではディレクトリ
    # 列挙でキャッシュ済み)、glob + 二重 getmtime を避けて走査負荷を下げる。
    files = list(_iter_rollout_files(sessions_dir))  # [(path, mtime), ...]
    if not files:
        return None, None, None, meta
    files.sort(key=lambda t: t[1], reverse=True)
    cutoff = time.time() - max_days * 86400
    best_usable = None
    best_usable_key = None
    best_any = None
    best_any_key = None
    event_seq = 0
    for path, mtime in files:
        if mtime < cutoff:
            break
        meta["candidate_files"] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                meta["scanned_files"] += 1
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or "rate_limits" not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    payload = rec.get("payload", rec)
                    if not isinstance(payload, dict):
                        continue
                    rl = payload.get("rate_limits")
                    if not rl:
                        continue
                    ts = parse_dt(rec.get("timestamp"))
                    meta["rate_limit_events"] += 1
                    event_seq += 1
                    event_epoch = ts.timestamp() if ts else mtime
                    key = (event_epoch, mtime, event_seq)
                    entry = {
                        "rate_limits": rl,
                        "timestamp": ts,
                        "path": path,
                        "file_mtime": datetime.fromtimestamp(mtime, tz=timezone.utc),
                        "line_number": line_no,
                    }
                    # 全イベント中の最新（フォールバック）
                    if best_any_key is None or key > best_any_key:
                        best_any_key = key
                        best_any = entry
                    # primary/secondary に有効な枠データを持つイベントのうち最新
                    if _rl_is_usable(rl):
                        if best_usable_key is None or key > best_usable_key:
                            best_usable_key = key
                            best_usable = entry
        except Exception:
            continue
    # usable イベントを優先し、無ければ any にフォールバック
    best = best_usable if best_usable is not None else best_any
    if best is None:
        return None, None, None, meta
    meta["file_mtime"] = best["file_mtime"]
    meta["line_number"] = best["line_number"]
    return best["rate_limits"], best["timestamp"], best["path"], meta


def find_latest_codex_event_wsl(cfg, max_days=10):
    """WSL 側の ~/.codex/sessions から最新の rate_limits イベントを返す。"""
    meta = {
        "candidate_files": 0,
        "scanned_files": 0,
        "rate_limit_events": 0,
        "file_mtime": None,
        "line_number": None,
        "sessions_exists": False,
        "error": None,
    }
    code = r'''
import datetime
import json
import os
import sys
import time

max_days = int(sys.argv[1])
sessions = os.path.expanduser("~/.codex/sessions")
result = {
    "ok": False,
    "sessions_exists": os.path.isdir(sessions),
    "candidate_files": 0,
    "scanned_files": 0,
    "rate_limit_events": 0,
    "file_mtime": None,
    "line_number": None,
    "timestamp": None,
    "path": None,
    "rate_limits": None,
}
if not result["sessions_exists"]:
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)

def rl_is_usable(rl):
    """primary か secondary に有効な枠データ(dict)を持つか判定する。
    Free の終端 null イベント対策として usable なイベントを優先選択するために使う。"""
    return isinstance(rl.get("primary"), dict) or isinstance(rl.get("secondary"), dict)

files = []
for root, dirs, names in os.walk(sessions):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
    for name in names:
        if name.startswith("rollout-") and name.endswith(".jsonl"):
            path = os.path.join(root, name)
            try:
                files.append((path, os.stat(path).st_mtime))
            except OSError:
                pass
files.sort(key=lambda item: item[1], reverse=True)
cutoff = time.time() - max_days * 86400
best_usable = None
best_usable_key = None
best_any = None
best_any_key = None
event_seq = 0
for path, mtime in files:
    if mtime < cutoff:
        break
    result["candidate_files"] += 1
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            result["scanned_files"] += 1
            for line_no, line in enumerate(f, start=1):
                if "rate_limits" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                payload = rec.get("payload", rec)
                if not isinstance(payload, dict):
                    continue
                rl = payload.get("rate_limits")
                if not rl:
                    continue
                ts = rec.get("timestamp")
                result["rate_limit_events"] += 1
                event_seq += 1
                try:
                    event_epoch = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
                except Exception:
                    event_epoch = mtime
                key = (event_epoch, mtime, event_seq)
                entry = {
                    "rate_limits": rl,
                    "timestamp": ts,
                    "path": path,
                    "file_mtime": mtime,
                    "line_number": line_no,
                }
                # 全イベント中の最新（フォールバック）
                if best_any_key is None or key > best_any_key:
                    best_any_key = key
                    best_any = entry
                # primary/secondary に有効な枠データを持つイベントのうち最新
                if rl_is_usable(rl):
                    if best_usable_key is None or key > best_usable_key:
                        best_usable_key = key
                        best_usable = entry
    except Exception:
        continue
# usable イベントを優先し、無ければ any にフォールバック
best = best_usable if best_usable is not None else best_any
if best:
    result.update(best)
    result["ok"] = True
print(json.dumps(result, ensure_ascii=False))
'''
    rc, out, err = run_wsl_cmd(cfg, ["python3", "-c", code, str(max_days)], timeout=30)
    if rc != 0:
        meta["error"] = mask_path(redact_text((err or out).strip()))[:200]
        return None, None, None, meta
    try:
        data = json.loads(out)
    except Exception:
        meta["error"] = "WSL 側 Codex セッションの診断結果を解釈できませんでした。"
        return None, None, None, meta
    meta["sessions_exists"] = bool(data.get("sessions_exists"))
    meta["candidate_files"] = int(data.get("candidate_files") or 0)
    meta["scanned_files"] = int(data.get("scanned_files") or 0)
    meta["rate_limit_events"] = int(data.get("rate_limit_events") or 0)
    mtime = data.get("file_mtime")
    meta["file_mtime"] = datetime.fromtimestamp(float(mtime), tz=timezone.utc) if mtime else None
    meta["line_number"] = data.get("line_number")
    if not data.get("ok"):
        return None, None, None, meta
    return data.get("rate_limits"), parse_dt(data.get("timestamp")), data.get("path"), meta


# window_minutes → 表示ラベルのマッピング（既知の Codex 枠サイズ）
_CODEX_WINDOW_LABELS = {300: "5時間", 10080: "週", 43200: "月"}


def _codex_window_label(minutes, fallback):
    """window_minutes からラベル文字列を返す。
    既知のマッピングにあればそれを使い、未知の値は分数から「N日」「N時間」「N分」を
    導出する。minutes が無効な場合は fallback（位置固定ラベル）を返す。
    Plus(300/10080) が回帰しないことを保証するために既知マップを先に引く。"""
    if isinstance(minutes, (int, float)) and int(minutes) in _CODEX_WINDOW_LABELS:
        return _CODEX_WINDOW_LABELS[int(minutes)]
    if isinstance(minutes, (int, float)) and minutes > 0:
        m = int(minutes)
        if m % 1440 == 0:
            return f"{m // 1440}日"
        if m % 60 == 0:
            return f"{m // 60}時間"
        return f"{m}分"
    return fallback


def provider_codex(cfg):
    res = {"name": "Codex", "ok": False, "error": None, "windows": [], "note": ""}
    max_days = int(cfg.get("codex_max_days", 10))
    use_wsl = _provider_uses_wsl(cfg, "codex")
    if use_wsl:
        ready, message = _wsl_running_status(cfg)
        if not ready:
            res["error"] = message
            return res
        if not _wsl_linux_command_exists(cfg, "python3"):
            res["error"] = f"{_wsl_label(cfg)} に Linux 側 python3 が見つかりません。WSL 側で python3 をインストールしてください。"
            return res
        rl, ts, path, meta = find_latest_codex_event_wsl(cfg, max_days=max_days)
    else:
        sessions_dir = os.path.join(HOME, ".codex", "sessions")
        rl, ts, path, meta = find_latest_codex_event(sessions_dir, max_days=max_days)
    if rl is None:
        if use_wsl and meta.get("error"):
            res["error"] = f"WSL 側 Codex セッション確認に失敗しました: {meta['error']}"
        elif use_wsl:
            res["error"] = f"セッションデータが見つかりません ({_wsl_label(cfg)} ~/.codex/sessions)。Codexで一度メッセージを送ると生成されます。"
        else:
            res["error"] = "セッションデータが見つかりません (~/.codex/sessions)。Codexで一度メッセージを送ると生成されます。"
        return res
    base = ts or now_utc()
    data_age = fmt_age(ts) if ts else "イベント時刻 不明"
    file_age = fmt_age(meta.get("file_mtime"))
    source = f"{_wsl_label(cfg)} / " if use_wsl else ""
    res["note"] = f"{source}Codexデータ: {data_age} / ログ更新: {file_age}"

    def window_from(key, fallback_label):
        d = rl.get(key)
        if not isinstance(d, dict):
            return None
        used = d.get("used_percent")
        if used is None:
            used = d.get("usedPercent")
        # window_minutes からラベルを導出する。Free は 43200(月) や 10080(週)、
        # Plus は 300(5時間) / 10080(週) が入る。既知マップ優先で Plus が回帰する。
        minutes = d.get("window_minutes")
        if minutes is None:
            minutes = d.get("windowMinutes")
        label = _codex_window_label(minutes, fallback_label)
        reset_at = None
        # 1) 相対秒(resets_in_seconds 系)
        for rk in ("resets_in_seconds", "reset_in_seconds", "resets_in",
                   "reset_after_seconds", "secondsUntilReset"):
            v = d.get(rk)
            if isinstance(v, (int, float)):
                reset_at = base + timedelta(seconds=float(v))
                break
        # 2) 相対分(window_minutes ではなく reset_in_minutes 系)
        if reset_at is None:
            for rk in ("resets_in_minutes", "reset_in_minutes", "minutesUntilReset"):
                v = d.get(rk)
                if isinstance(v, (int, float)):
                    reset_at = base + timedelta(minutes=float(v))
                    break
        # 3) 絶対時刻(resets_at / reset_at / reset_time 系: ISO文字列 or epoch)
        if reset_at is None:
            for rk in ("resets_at", "reset_at", "reset_time", "resetTime",
                       "resetAt", "reset"):
                v = d.get(rk)
                if v is not None:
                    reset_at = parse_dt(v)
                    if reset_at is not None:
                        break
        return make_window(label, used_pct=used, reset_at=reset_at,
                           detail=f"データ {data_age}")

    w5 = window_from("primary", "5時間")
    ww = window_from("secondary", "週")
    for w in (w5, ww):
        if w:
            res["windows"].append(w)
    if res["windows"]:
        res["ok"] = True
    else:
        # usable イベントが1件も無かった場合のエッジ: credits のみのプランか、
        # 本当に枠データが空か、を credits で切り分ける
        credits = rl.get("credits") if isinstance(rl, dict) else None
        if isinstance(credits, dict) and credits.get("unlimited"):
            res["ok"] = True
            res["note"] = (res.get("note") or "") + " / 無制限プラン（使用枠なし）"
        else:
            res["error"] = (
                "無料プランの利用枠情報が取得できませんでした"
                "（Codex を一度利用すると Monthly limit が表示されます）。"
            )
    return res
