# -*- coding: utf-8 -*-
"""診断 (probe)。各データソースの検出パス・生データ・正規化結果を表示する。"""

import os
import json

from .constants import HOME
from .redact import mask_path, redact_secrets, redact_text
from .utils import resolve_cmd, parse_dt, fmt_age, run_cmd
from .state import claude_lock, _claude_cache
from .wsl import (
    _wsl_running_status,
    _resolve_wsl_exe,
    _wsl_distro,
    _provider_uses_wsl,
    _wsl_label,
    _wsl_linux_command_exists,
    _wsl_path_exists,
)
from .providers import PROVIDERS, PROVIDER_NAMES
from .providers.codex import find_latest_codex_event, find_latest_codex_event_wsl
from .providers.claude import _read_claude_token, _claude_code_version, CLAUDE_USAGE_URL, provider_claude
from .providers.antigravity import build_antigravity_cmd
from .collect import collect, summarize_text


def run_probe(cfg, show_raw=False):
    cfg["_wsl_cycle_cache"] = {}
    print("=" * 60)
    print("AI Usage Tray  PROBE")
    print("=" * 60)
    if not show_raw:
        print("（外部 CLI の生出力は既定で非表示です。必要なら --probe-raw を使ってください。）")
        print("（出力を Issue/PR に貼る前に、機密やローカル情報が無いか確認してください。）")
    print(f"HOME = {mask_path(HOME)}")
    wsl_ready, wsl_message = _wsl_running_status(cfg)
    print(f"wsl.exe           : {mask_path(_resolve_wsl_exe())}")
    print(f"WSL distro        : {_wsl_distro(cfg) or '(既定)'}")
    print(f"WSL running       : {wsl_ready} {('- ' + wsl_message) if not wsl_ready else ''}")
    wsl_enabled = cfg.get("wsl", {}).get("enabled", {}) if isinstance(cfg.get("wsl", {}), dict) else {}
    if isinstance(wsl_enabled, dict):
        enabled_text = ", ".join(f"{PROVIDER_NAMES.get(k, k)}={bool(wsl_enabled.get(k, False))}"
                                 for k, _fn in PROVIDERS)
    else:
        enabled_text = str(bool(wsl_enabled))
    print(f"WSL enabled       : {enabled_text}")
    print(f"claude            : {mask_path(resolve_cmd('claude'))}")
    paths_cfg = cfg.get("paths", {})
    if not isinstance(paths_cfg, dict):
        paths_cfg = {}
    print(f"antigravity-usage : {mask_path(resolve_cmd('antigravity-usage', paths_cfg.get('antigravity_usage','')))}")
    print(f"npx               : {mask_path(resolve_cmd('npx'))}")
    print()

    # Codex 生データ
    codex_uses_wsl = _provider_uses_wsl(cfg, "codex")
    codex_max_days = int(cfg.get("codex_max_days", 10))
    if codex_uses_wsl:
        print(f"[Codex] source: {_wsl_label(cfg)}")
        if not wsl_ready:
            rl, ts, path = None, None, None
            meta = {"error": wsl_message, "sessions_exists": False}
        elif not _wsl_linux_command_exists(cfg, "python3"):
            rl, ts, path = None, None, None
            meta = {"error": "Linux 側 python3 が見つかりません。", "sessions_exists": False}
        else:
            rl, ts, path, meta = find_latest_codex_event_wsl(cfg, max_days=codex_max_days)
        print(f"[Codex] sessions dir exists: {bool(meta.get('sessions_exists'))}  ({_wsl_label(cfg)} ~/.codex/sessions)")
        if meta.get("error"):
            print(f"[Codex] source error: {meta.get('error')}")
    else:
        sessions_dir = os.path.join(HOME, ".codex", "sessions")
        rl, ts, path, meta = find_latest_codex_event(sessions_dir, max_days=codex_max_days)
        print("[Codex] source: Windows")
        print(f"[Codex] sessions dir exists: {os.path.isdir(sessions_dir)}  ({mask_path(sessions_dir)})")
    print(f"[Codex] max_days: {codex_max_days}")
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
    claude_uses_wsl = _provider_uses_wsl(cfg, "claude")
    if claude_uses_wsl:
        cred_label = f"{_wsl_label(cfg)} ~/.claude/.credentials.json"
        has_wsl_python = wsl_ready and _wsl_linux_command_exists(cfg, "python3")
        cred_exists = has_wsl_python and _wsl_path_exists(cfg, "-f", '"$HOME/.claude/.credentials.json"')
    else:
        has_wsl_python = False
        cred_path = os.path.join(HOME, ".claude", ".credentials.json")
        cred_label = mask_path(cred_path)
        cred_exists = os.path.exists(cred_path)
    if claude_uses_wsl and (not wsl_ready or not has_wsl_python):
        token, expires_at = None, None
    else:
        token, expires_at = _read_claude_token(cfg)
    print(f"[Claude] source: {_wsl_label(cfg) if claude_uses_wsl else 'Windows'}")
    print(f"[Claude] credentials: {cred_label}  (exists={cred_exists})")
    print(f"[Claude] token: {'取得OK' if token else '見つかりません'}", end="")
    if expires_at:
        exp = parse_dt(expires_at)
        print(f"  (expiresAt={exp})", end="")
    print()
    claude_ver = _claude_code_version(cfg) if (not claude_uses_wsl or wsl_ready) else "2.0.0"
    print(f"[Claude] user-agent version: claude-code/{claude_ver}")
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
        # 主要キーのみ抽出済みだが、念のため機密キーを redact してから表示
        print(f"[Claude] raw (safe-subset): {json.dumps(redact_secrets(safe_raw), ensure_ascii=False)}")
    print()

    # antigravity-usage 生出力
    antigravity_uses_wsl = _provider_uses_wsl(cfg, "antigravity")
    print(f"[Antigravity] source: {_wsl_label(cfg) if antigravity_uses_wsl else 'Windows'}")
    if antigravity_uses_wsl and not wsl_ready:
        cmd, reason = None, wsl_message
    else:
        cmd, reason = build_antigravity_cmd(cfg)
    print(f"[Antigravity] npx_fallback: {bool(cfg.get('antigravity_npx_fallback', False))}"
          f"  version: {cfg.get('antigravity_usage_version', '')!r}")
    print(f"[Antigravity] cmd: {mask_path(cmd)}")
    if not cmd:
        print(f"[Antigravity] スキップ: {reason}")
    if cmd:
        rc, out, err = run_cmd(cmd, timeout=60)
        print(f"[Antigravity] rc={rc}")
        if show_raw:
            # 秘匿・パスマスクは必ず全文に適用してから表示長を切り詰める。先に切ると、
            # 値が長さ境界(200/1500)をまたいだ際に正規表現へ一致せず途中まで漏れる。
            safe_err = mask_path(redact_text(err.strip()))
            print(f"[Antigravity] stderr: {safe_err[:200]}")
            # JSON ならキー名で再帰 redact、壊れた JSON 等はそのまま。最後に必ず
            # 文字列向け redact_text を通し、email 以外のキー配下のメール等(JSON 経路で
            # redact_secrets が拾えない値)も含めて秘匿してから表示する。
            raw = out.strip()
            try:
                shown = json.dumps(redact_secrets(json.loads(raw)), ensure_ascii=False)
            except Exception:
                shown = raw
            shown = mask_path(redact_text(shown))
            print(f"[Antigravity] stdout(redacted, 先頭1500): {shown[:1500]}")
        else:
            print("[Antigravity] raw 出力は非表示(--probe-raw で表示)。値は下の正規化結果を参照。")
    print()

    print("=" * 60)
    print("正規化結果:")
    print("=" * 60)
    print(summarize_text(collect(cfg)))
