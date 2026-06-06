#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Usage Tray  -  Claude Code / Codex / Antigravity の残り使用量を
Windows のタスクトレイにまとめて表示する常駐アプリ。

- Claude Code : 公式 OAuth usage API (api.anthropic.com/api/oauth/usage) から 5h/週 の使用%とリセットを取得
- Codex       : ~/.codex/sessions の rollout-*.jsonl から primary(5h)/secondary(週) の使用%とリセットを取得
- Antigravity : antigravity-usage (npm) の --json から各モデルの残り割合とリセットを取得

使い方:
    python ai_usage_tray.py            # トレイ常駐で起動
    python ai_usage_tray.py --once     # 1回だけ取得してテキスト表示(テスト用)
    python ai_usage_tray.py --probe    # 各データソースの生データを表示(設定の診断用)

設定は同じフォルダの config.json で上書き可能(無ければ既定値)。
"""

import sys
import os
import re
import json
import glob
import time
import shutil
import argparse
import threading
import subprocess
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")


def mask_path(path):
    """パスに含まれる HOME フォルダ部分を ~ にマスクする。"""
    if not path:
        return path
    if isinstance(path, list):
        return [mask_path(p) for p in path]
    return str(path).replace(HOME, "~")

# PyInstaller などで exe 化(凍結)された場合は exe のあるフォルダを基準にする
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "refresh_seconds": 300,            # 自動更新間隔(秒)
    "codex_max_days": 10,              # Codex セッションログの走査日数
    "enabled": {"claude": True, "codex": True, "antigravity": True},
    # Antigravity で表示したいモデル名の部分一致フィルタ(空なら主要モデルを自動選択)
    "antigravity_models": [],
    # Antigravity のオートコンプリート専用モデルも表示するか(既定は非表示)
    "antigravity_show_autocomplete": False,
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


# ---------------------------------------------------------------------------
# 共通ユーティリティ
# ---------------------------------------------------------------------------
def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(value):
    """ISO文字列/epoch などを aware datetime(UTC) に。失敗で None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # 秒 or ミリ秒 epoch を推定
        v = float(value)
        if v > 1e12:
            v /= 1000.0
        try:
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        s2 = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def fmt_reset(reset_at):
    """リセットまでの残り時間を 'あとX時間Y分 (HH:MM)' で。"""
    if not reset_at:
        return "リセット時刻 不明"
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    delta = reset_at - now_utc()
    secs = int(delta.total_seconds())
    local = reset_at.astimezone()
    clock = local.strftime("%H:%M")
    if secs <= 0:
        return f"まもなくリセット ({clock})"
    h, rem = divmod(secs, 3600)
    m = rem // 60
    if h > 0:
        return f"あと{h}時間{m}分 ({clock})"
    return f"あと{m}分 ({clock})"


def fmt_age(dt):
    """datetime を 'N分前 (HH:MM)' 形式にする。"""
    if not dt:
        return "不明"
    delta = now_utc() - dt.astimezone(timezone.utc)
    secs = int(delta.total_seconds())
    local = dt.astimezone()
    clock = local.strftime("%H:%M")
    if secs < 0:
        return f"未来時刻 ({clock})"
    if secs < 60:
        return f"{secs}秒前 ({clock})"
    mins = secs // 60
    if mins < 60:
        return f"{mins}分前 ({clock})"
    hours = mins // 60
    if hours < 48:
        return f"{hours}時間前 ({clock})"
    days = hours // 24
    return f"{days}日前 ({clock})"


def run_cmd(cmd, timeout=30):
    """コマンドを実行し (returncode, stdout, stderr)。Windows の .cmd shim も考慮。"""
    # noconsole(pythonw / exe)で動かすと、子プロセス起動のたびに黒いコンソール窓が
    # 一瞬出る。CREATE_NO_WINDOW でそれを抑止する(Windows のみ)。
    kwargs = {}
    shell = False
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        # コマンドの拡張子が .bat や .cmd の場合は shell=True が必要
        target = cmd[0] if isinstance(cmd, list) else cmd
        if str(target).lower().endswith((".bat", ".cmd")):
            shell = True
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=shell,
            **kwargs,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as e:
        return 127, "", str(e)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def resolve_cmd(name, explicit=""):
    """実行可能なコマンドのパスを返す。見つからなければ None。
    コマンドプリロード攻撃を防ぐため、PATH 環境変数のディレクトリのみを探索する。"""
    if explicit:
        if os.path.exists(explicit):
            return explicit

    exts = [""]
    if os.name == "nt":
        exts = [".cmd", ".exe", ".bat", ""]

    path_env = os.environ.get("PATH", "")
    sep = ";" if os.name == "nt" else ":"
    for folder in path_env.split(sep):
        folder = folder.strip('"')
        if not folder:
            continue
        for ext in exts:
            p = os.path.join(folder, name + ext)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None


# ---------------------------------------------------------------------------
# 正規化された結果の型(辞書ベース)
#   window = {label, used_pct, remaining_pct, reset_at, detail}
#   result = {name, ok, error, windows:[window...], note}
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Provider: Codex  (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl)
# ---------------------------------------------------------------------------
def find_latest_codex_event(sessions_dir, max_days=10):
    """最新の rate_limits イベントと診断メタ情報を返す。"""
    meta = {
        "candidate_files": 0,
        "scanned_files": 0,
        "rate_limit_events": 0,
        "file_mtime": None,
        "line_number": None,
    }
    if not os.path.isdir(sessions_dir):
        return None, None, None, meta
    files = glob.glob(os.path.join(sessions_dir, "**", "rollout-*.jsonl"), recursive=True)
    if not files:
        return None, None, None, meta
    def get_mtime_safe(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0
    files.sort(key=get_mtime_safe, reverse=True)
    cutoff = time.time() - max_days * 86400
    best = None
    best_key = None
    event_seq = 0
    for path in files:
        try:
            mtime = os.path.getmtime(path)
            if mtime < cutoff:
                break
        except OSError:
            continue
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
                    if best_key is None or key > best_key:
                        best_key = key
                        best = {
                            "rate_limits": rl,
                            "timestamp": ts,
                            "path": path,
                            "file_mtime": datetime.fromtimestamp(mtime, tz=timezone.utc),
                            "line_number": line_no,
                        }
        except Exception:
            continue
    if best is None:
        return None, None, None, meta
    meta["file_mtime"] = best["file_mtime"]
    meta["line_number"] = best["line_number"]
    return best["rate_limits"], best["timestamp"], best["path"], meta


def provider_codex(cfg):
    res = {"name": "Codex", "ok": False, "error": None, "windows": [], "note": ""}
    sessions_dir = os.path.join(HOME, ".codex", "sessions")
    max_days = int(cfg.get("codex_max_days", 10))
    rl, ts, path, meta = find_latest_codex_event(sessions_dir, max_days=max_days)
    if rl is None:
        res["error"] = "セッションデータが見つかりません (~/.codex/sessions)。Codexで一度メッセージを送ると生成されます。"
        return res
    base = ts or now_utc()
    data_age = fmt_age(ts) if ts else "イベント時刻 不明"
    file_age = fmt_age(meta.get("file_mtime"))
    res["note"] = (
        f"Codexデータ: {data_age} / ログ更新: {file_age}"
    )

    def window_from(key, label):
        d = rl.get(key)
        if not isinstance(d, dict):
            return None
        used = d.get("used_percent")
        if used is None:
            used = d.get("usedPercent")
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
        res["error"] = "rate_limits を解釈できませんでした。"
    return res


# ---------------------------------------------------------------------------
# Provider: Claude Code  (公式 OAuth usage API)
# ---------------------------------------------------------------------------
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_claude_cache = {"ts": 0.0, "data": None}
claude_lock = threading.Lock()
ui_lock = threading.Lock()


def _read_claude_token():
    """~/.claude/.credentials.json から OAuth アクセストークンと有効期限(epoch ms)を読む。"""
    path = os.path.join(HOME, ".claude", ".credentials.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, None
    except Exception:
        return None, None
    oauth = data.get("claudeAiOauth") or data.get("claude_ai_oauth") or {}
    if isinstance(oauth, dict):
        return oauth.get("accessToken") or oauth.get("access_token"), \
            oauth.get("expiresAt") or oauth.get("expires_at")
    return None, None


def _claude_code_version():
    """User-Agent 用に claude のバージョンを取得(取れなければ既定値)。"""
    exe = resolve_cmd("claude")
    if exe:
        rc, out, err = run_cmd([exe, "--version"], timeout=15)
        if rc == 0:
            m = re.search(r"(\d+\.\d+\.\d+)", out or "")
            if m:
                return m.group(1)
    return "2.0.0"


def provider_claude(cfg):
    res = {"name": "Claude Code", "ok": False, "error": None, "windows": [], "note": ""}

    # レート制限(429)回避のため API レスポンスを 90 秒キャッシュ
    data = None
    with claude_lock:
        if _claude_cache["data"] is not None and (time.time() - _claude_cache["ts"]) < 90:
            data = _claude_cache["data"]

    if data is None:
        token, expires_at = _read_claude_token()
        if not token:
            token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if not token:
            res["error"] = "認証情報が見つかりません (~/.claude/.credentials.json)。Claude Code にログインしてください。"
            return res

        import urllib.request
        import urllib.error
        ver = _claude_code_version()
        req = urllib.request.Request(CLAUDE_USAGE_URL, headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": f"claude-code/{ver}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                res["error"] = "トークン期限切れ。Claude Code を一度起動/実行すると自動更新されます。"
            elif e.code == 429:
                res["error"] = "レート制限(429)。数分待って再取得してください。"
            else:
                res["error"] = f"API エラー {e.code}"
            return res
        except Exception as e:
            res["error"] = f"取得失敗: {str(e)[:150]}"
            return res
        with claude_lock:
            _claude_cache["ts"] = time.time()
            _claude_cache["data"] = data

    def win(key, label):
        d = data.get(key)
        if not isinstance(d, dict):
            return None
        util = d.get("utilization")
        if util is None:
            return None
        try:
            used_pct = float(util)
        except (ValueError, TypeError):
            return None
        reset_at = parse_dt(d.get("resets_at"))
        return make_window(label, used_pct=used_pct, reset_at=reset_at)

    for key, label in (("five_hour", "5時間"), ("seven_day", "週")):
        w = win(key, label)
        if w:
            res["windows"].append(w)

    # 参考: モデル別の週次(あれば)
    for key, label in (("seven_day_opus", "週(Opus)"), ("seven_day_sonnet", "週(Sonnet)")):
        w = win(key, label)
        if w:
            res["windows"].append(w)

    res["ok"] = bool(res["windows"])
    if not res["ok"]:
        res["error"] = "使用量データが空でした(現在アクティブな枠なし)。"
    return res


# ---------------------------------------------------------------------------
# Provider: Antigravity  (antigravity-usage --json)
# ---------------------------------------------------------------------------
def _norm(s):
    """照合用に英数字のみへ正規化(区切り文字・大文字小文字・空白を無視)。"""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _walk_find_models(obj, found, parent_key=None):
    """JSON を再帰的に走査し、remaining 系 + reset 系を持つオブジェクトを収集。
    モデル名が辞書のキー(例 {"models":{"Gemini 3.5 Flash":{...}}})の場合は
    parent_key を名前として採用する。"""
    if isinstance(obj, dict):
        keys = {k.lower(): k for k in obj.keys()}
        remain_key = None
        for cand in ("remainingfraction", "remaining_fraction", "remaining",
                     "remainingpercentage", "remaining_percentage",
                     "remainingpercent", "remaining_percent", "fraction"):
            if cand in keys:
                remain_key = keys[cand]
                break
        used_key = None
        for cand in ("used_percent", "usedpercent", "used", "usage", "usagepercent"):
            if cand in keys:
                used_key = keys[cand]
                break
        reset_key = None
        for cand in ("resettime", "reset_time", "reset", "resetat", "reset_at",
                     "resets_at", "resetsat"):
            if cand in keys:
                reset_key = keys[cand]
                break
        if (remain_key or used_key):
            name = None
            for cand in ("name", "model", "modelname", "model_name", "displayname",
                         "display_name", "label", "id"):
                if cand in keys:
                    name = obj[keys[cand]]
                    break
            if name is None and parent_key is not None:
                name = parent_key
            # オートコンプリート専用 / 枯渇フラグ(あれば)
            auto = False
            for cand in ("isautocompleteonly", "autocompleteonly", "autocomplete"):
                if cand in keys and bool(obj[keys[cand]]):
                    auto = True
                    break
            model_id = None
            for cand in ("modelid", "model_id"):
                if cand in keys:
                    model_id = obj[keys[cand]]
                    break
            found.append({
                "name": name,
                "model_id": model_id,
                "remain_raw": obj.get(remain_key) if remain_key else None,
                "used_raw": obj.get(used_key) if used_key else None,
                "reset_raw": obj.get(reset_key) if reset_key else None,
                "auto": auto,
            })
        for k, v in obj.items():
            _walk_find_models(v, found, parent_key=k)
    elif isinstance(obj, list):
        for v in obj:
            _walk_find_models(v, found, parent_key=parent_key)


def provider_antigravity(cfg):
    res = {"name": "Antigravity", "ok": False, "error": None, "windows": [], "note": ""}
    exe = resolve_cmd("antigravity-usage", cfg["paths"].get("antigravity_usage", ""))
    cmd = None
    if exe:
        cmd = [exe, "--json"]
    else:
        npx = resolve_cmd("npx")
        if npx:
            cmd = [npx, "-y", "antigravity-usage", "--json"]
    if not cmd:
        res["error"] = "antigravity-usage が見つかりません。`npm i -g antigravity-usage` を実行してください。"
        return res

    rc, out, err = run_cmd(cmd, timeout=60)
    if rc != 0 or not out.strip():
        res["error"] = f"antigravity-usage 実行失敗: {(err or out).strip()[:200]}"
        return res
    try:
        data = json.loads(out)
    except Exception:
        m = re.search(r"[\{\[].*[\}\]]", out, re.S)
        if not m:
            res["error"] = "antigravity-usage の出力を解釈できませんでした。"
            return res
        try:
            data = json.loads(m.group(0))
        except Exception:
            res["error"] = "antigravity-usage の JSON 解析に失敗しました。"
            return res

    found = []
    _walk_find_models(data, found)
    if not found:
        res["error"] = "モデル使用量の項目が見つかりませんでした(--probe で生データ確認)。"
        return res

    filters = [_norm(s) for s in cfg.get("antigravity_models", []) if s]
    show_auto = bool(cfg.get("antigravity_show_autocomplete", False))

    def remaining_pct_of(item):
        if item["remain_raw"] is not None:
            v = item["remain_raw"]
            if isinstance(v, (int, float)):
                return v * 100.0 if v <= 1.0 else float(v)
        if item["used_raw"] is not None and isinstance(item["used_raw"], (int, float)):
            u = item["used_raw"]
            u = u * 100.0 if u <= 1.0 else float(u)
            return max(0.0, 100.0 - u)
        return None

    seen = set()
    candidates = 0  # オートコンプリート除外後の候補数
    for item in found:
        if item.get("auto") and not show_auto:
            continue
        candidates += 1
        name = str(item["name"]) if item["name"] is not None else "model"
        # ラベルと modelId の両方を区切り無視で照合(ハイフン/スペース/ドットを吸収)
        haystack = _norm(name) + _norm(item.get("model_id"))
        if filters and not any(f in haystack for f in filters):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        rp = remaining_pct_of(item)
        reset_at = parse_dt(item["reset_raw"])
        res["windows"].append(make_window(name, remaining_pct=rp, reset_at=reset_at))

    if res["windows"]:
        res["ok"] = True
    elif filters and candidates > 0:
        # フィルタが厳しすぎて全部消えた場合は、全件に戻さず明示する
        res["error"] = "antigravity_models のフィルタに一致するモデルがありません。config を確認してください。"
    else:
        res["error"] = "モデルを抽出できませんでした(--probe で生データ確認)。"
    return res


# ---------------------------------------------------------------------------
# 集約
# ---------------------------------------------------------------------------
PROVIDERS = [
    ("claude", provider_claude),
    ("codex", provider_codex),
    ("antigravity", provider_antigravity),
]


def collect(cfg):
    results = []
    for key, fn in PROVIDERS:
        if not cfg["enabled"].get(key, True):
            continue
        try:
            results.append(fn(cfg))
        except Exception as e:
            results.append({"name": key, "ok": False, "error": f"内部エラー: {e}",
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


# ---------------------------------------------------------------------------
# トレイ表示
# ---------------------------------------------------------------------------
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


def make_icon_image(remaining):
    from PIL import Image, ImageDraw
    light = _windows_is_light_theme()
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 残量で塗り色を決定
    if remaining is None:
        fill = (130, 130, 130, 255)
    elif remaining >= 50:
        fill = (46, 160, 67, 255)
    elif remaining >= 20:
        fill = (210, 153, 34, 255)
    else:
        fill = (218, 54, 51, 255)

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

    state = {"results": [], "lock": threading.Lock()}

    def build_menu():
        items = []
        with state["lock"]:
            results = list(state["results"])
        if not results:
            items.append(Item("取得中...", None, enabled=False))
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
        items.append(Item("今すぐ更新", lambda icon, item: refresh(icon)))
        items.append(Item("終了", lambda icon, item: icon.stop()))
        return Menu(*items)

    def refresh(icon=None):
        results = collect(cfg)
        with state["lock"]:
            state["results"] = results
        rem = min_remaining(results)
        if icon is not None:
            with ui_lock:
                icon.icon = make_icon_image(rem)
                icon.title = build_tooltip(results)
                icon.menu = build_menu()
                icon.update_menu()

    def build_tooltip(results):
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
        return "AI Usage  |  " + "   ".join(parts)

    icon = pystray.Icon("ai_usage", make_icon_image(None), "AI Usage 取得中...", menu=build_menu())

    def worker():
        while True:
            try:
                refresh(icon)
            except Exception as e:
                print(f"[worker] {e}", file=sys.stderr)
            time.sleep(max(30, int(cfg.get("refresh_seconds", 300))))

    threading.Thread(target=worker, daemon=True).start()
    icon.run()


# ---------------------------------------------------------------------------
# 診断 (probe)
# ---------------------------------------------------------------------------
def run_probe(cfg):
    print("=" * 60)
    print("AI Usage Tray  PROBE")
    print("=" * 60)
    print(f"HOME = {mask_path(HOME)}")
    print(f"claude            : {mask_path(resolve_cmd('claude'))}")
    print(f"antigravity-usage : {mask_path(resolve_cmd('antigravity-usage', cfg['paths'].get('antigravity_usage','')))}")
    print(f"npx               : {mask_path(resolve_cmd('npx'))}")
    print()

    # Codex 生データ
    sessions_dir = os.path.join(HOME, ".codex", "sessions")
    codex_max_days = int(cfg.get("codex_max_days", 10))
    print(f"[Codex] sessions dir exists: {os.path.isdir(sessions_dir)}  ({mask_path(sessions_dir)})")
    print(f"[Codex] max_days: {codex_max_days}")
    rl, ts, path, meta = find_latest_codex_event(sessions_dir, max_days=codex_max_days)
    print(f"[Codex] latest rate_limits file: {mask_path(path)}")
    print(f"[Codex] timestamp: {ts}")
    print(f"[Codex] data age: {fmt_age(ts) if ts else None}")
    print(f"[Codex] file mtime: {meta.get('file_mtime')}")
    print(f"[Codex] file age: {fmt_age(meta.get('file_mtime')) if meta.get('file_mtime') else None}")
    print(f"[Codex] selected line: {meta.get('line_number')}")
    print(f"[Codex] candidate files: {meta.get('candidate_files')}")
    print(f"[Codex] scanned files: {meta.get('scanned_files')}")
    print(f"[Codex] rate_limits events: {meta.get('rate_limit_events')}")
    print(f"[Codex] rate_limits: {json.dumps(rl, ensure_ascii=False) if rl else None}")
    print()

    # Claude Code 公式 OAuth usage API
    cred_path = os.path.join(HOME, ".claude", ".credentials.json")
    token, expires_at = _read_claude_token()
    print(f"[Claude] credentials: {mask_path(cred_path)}  (exists={os.path.exists(cred_path)})")
    print(f"[Claude] token: {'取得OK' if token else '見つかりません'}", end="")
    if expires_at:
        exp = parse_dt(expires_at)
        print(f"  (expiresAt={exp})", end="")
    print()
    print(f"[Claude] user-agent version: claude-code/{_claude_code_version()}")
    print(f"[Claude] endpoint: {CLAUDE_USAGE_URL}")
    if token:
        # キャッシュを無視して生レスポンスを 1 回取得
        with claude_lock:
            _claude_cache["data"] = None
        r = provider_claude(cfg)
        print(f"[Claude] ok={r['ok']}  error={r['error']}")
        # 生データから機密情報が含まれる可能性のある部分を排除し主要キーのみ表示
        raw_data = _claude_cache.get("data")
        safe_raw = None
        if isinstance(raw_data, dict):
            safe_raw = {}
            for k in ("five_hour", "seven_day", "seven_day_sonnet", "seven_day_opus", "extra_usage"):
                if k in raw_data:
                    safe_raw[k] = raw_data[k]
        print(f"[Claude] raw (safe-subset): {json.dumps(safe_raw, ensure_ascii=False)}")
    print()

    # antigravity-usage 生出力
    exe = resolve_cmd("antigravity-usage", cfg["paths"].get("antigravity_usage", ""))
    cmd = [exe, "--json"] if exe else None
    if not cmd:
        npx = resolve_cmd("npx")
        cmd = [npx, "-y", "antigravity-usage", "--json"] if npx else None
    print(f"[Antigravity] cmd: {mask_path(cmd)}")
    if cmd:
        rc, out, err = run_cmd(cmd, timeout=60)
        print(f"[Antigravity] rc={rc}  stderr={err.strip()[:200]}")
        # 出力内容に含まれるパスやメールアドレスをマスク
        sanitized_out = mask_path(out.strip()[:1500])
        sanitized_out = re.sub(r'"email":\s*"[^"]+"', '"email": "******@******"', sanitized_out)
        print(f"[Antigravity] stdout(先頭1500): {sanitized_out}")
    print()

    print("=" * 60)
    print("正規化結果:")
    print("=" * 60)
    print(summarize_text(collect(cfg)))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="AI Usage Tray")
    ap.add_argument("--once", action="store_true", help="1回だけ取得してテキスト表示")
    ap.add_argument("--probe", action="store_true", help="各データソースの生データを表示")
    args = ap.parse_args()

    # Windows の cp932 コンソールだと中点(·)等の出力で UnicodeEncodeError になるため、
    # 標準出力/標準エラーを UTF-8(置換)に固定する(--once/--probe のテキスト表示用)。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    cfg = load_config()

    if args.probe:
        run_probe(cfg)
        return
    if args.once:
        print(summarize_text(collect(cfg)))
        return
    run_tray(cfg)


if __name__ == "__main__":
    main()
