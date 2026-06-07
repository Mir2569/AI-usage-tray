# -*- coding: utf-8 -*-
"""Provider: Claude Code  (公式 OAuth usage API)。"""

import os
import re
import json
import time

from ..constants import HOME
from ..utils import parse_dt, run_cmd, resolve_cmd
from ..redact import mask_path, redact_text
from ..state import claude_lock, _claude_cache
from ..wsl import (
    _provider_uses_wsl,
    _wsl_running_status,
    _wsl_linux_command_exists,
    _wsl_linux_command_path,
    _wsl_label,
    run_wsl_cmd,
    run_wsl_sh,
)
from .types import make_window

CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def _read_claude_token_from_json(text):
    try:
        data = json.loads(text)
    except Exception:
        return None, None
    oauth = data.get("claudeAiOauth") or data.get("claude_ai_oauth") or {}
    if isinstance(oauth, dict):
        return oauth.get("accessToken") or oauth.get("access_token"), \
            oauth.get("expiresAt") or oauth.get("expires_at")
    return None, None


def _read_claude_token(cfg=None):
    """~/.claude/.credentials.json から OAuth アクセストークンと有効期限(epoch ms)を読む。"""
    if cfg and _provider_uses_wsl(cfg, "claude"):
        code = (
            'import os, sys; '
            'path=os.path.expanduser("~/.claude/.credentials.json"); '
            'sys.stdout.write(open(path, encoding="utf-8").read()) if os.path.isfile(path) else sys.exit(2)'
        )
        rc, out, err = run_wsl_cmd(cfg, ["python3", "-c", code], timeout=15)
        if rc != 0:
            return None, None
        return _read_claude_token_from_json(out)

    path = os.path.join(HOME, ".claude", ".credentials.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return None, None
    except Exception:
        return None, None
    return _read_claude_token_from_json(text)


def _read_claude_env_token_wsl(cfg):
    script = (
        'token="${CLAUDE_CODE_OAUTH_TOKEN:-}"; '
        'if [ -z "$token" ] && [ -r "$HOME/.profile" ]; then '
        '. "$HOME/.profile" >/dev/null 2>/dev/null || true; '
        'token="${CLAUDE_CODE_OAUTH_TOKEN:-}"; '
        'fi; '
        'printf "%s" "$token"'
    )
    rc, out, err = run_wsl_sh(cfg, script, timeout=10)
    if rc == 0 and out.strip():
        return out.strip()
    return None


def _claude_code_version(cfg=None):
    """User-Agent 用に claude のバージョンを取得(取れなければ既定値)。"""
    if cfg and _provider_uses_wsl(cfg, "claude"):
        exe = _wsl_linux_command_path(cfg, "claude")
        if exe:
            rc, out, err = run_wsl_cmd(cfg, [exe, "--version"], timeout=15)
            if rc == 0:
                m = re.search(r"(\d+\.\d+\.\d+)", out or "")
                if m:
                    return m.group(1)
        return "2.0.0"

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
    use_wsl = _provider_uses_wsl(cfg, "claude")
    source = _wsl_label(cfg) if use_wsl else "Windows"
    if use_wsl:
        ready, message = _wsl_running_status(cfg)
        if not ready:
            res["error"] = message
            return res
        if not _wsl_linux_command_exists(cfg, "python3"):
            res["error"] = f"{_wsl_label(cfg)} に Linux 側 python3 が見つかりません。WSL 側で python3 をインストールしてください。"
            return res

    # レート制限(429)回避のため API レスポンスを 90 秒キャッシュ
    data = None
    with claude_lock:
        if (_claude_cache["data"] is not None
                and _claude_cache.get("source") == source
                and (time.time() - _claude_cache["ts"]) < 90):
            data = _claude_cache["data"]

    if data is None:
        token, expires_at = _read_claude_token(cfg)
        if not token:
            token = _read_claude_env_token_wsl(cfg) if use_wsl else os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if not token:
            if use_wsl:
                res["error"] = f"認証情報が見つかりません ({_wsl_label(cfg)} ~/.claude/.credentials.json)。WSL 側の Claude Code にログインしてください。"
            else:
                res["error"] = "認証情報が見つかりません (~/.claude/.credentials.json)。Claude Code にログインしてください。"
            return res

        # トークンの有効期限(epoch ms)が分かっていて既に過去なら、API を叩く前に
        # 期限切れを返す。無駄なリクエストと 429 誘発を避ける(環境変数トークンは expires_at 無し)。
        if expires_at:
            try:
                if float(expires_at) / 1000.0 <= time.time():
                    res["error"] = "トークン期限切れ。Claude Code を一度起動/実行すると自動更新されます。"
                    return res
            except (TypeError, ValueError):
                pass

        import urllib.request
        import urllib.error
        ver = _claude_code_version(cfg)
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
            # 例外文にローカルパス等が混じる場合に備え、秘匿・マスクしてから切り詰める。
            res["error"] = f"取得失敗: {mask_path(redact_text(str(e)))[:150]}"
            return res
        with claude_lock:
            _claude_cache["ts"] = time.time()
            _claude_cache["data"] = data
            _claude_cache["source"] = source

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
    elif use_wsl:
        res["note"] = _wsl_label(cfg)
    return res
