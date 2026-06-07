# -*- coding: utf-8 -*-
"""WSL データソース切替用ヘルパー。

provider ごとに WSL 側の認証情報・セッションログ・CLI を参照する。実行は wsl.exe
経由(shell=False / CREATE_NO_WINDOW)で、Windows 側と同じ run_cmd を通す。"""

import os
import re
import time

from .redact import mask_path, redact_text
from .utils import resolve_cmd, run_cmd, run_cmd_bytes


def _provider_uses_wsl(cfg, provider):
    """provider のデータソースを WSL 側へ切り替えるかを返す。"""
    if os.name != "nt":
        return False
    wsl_cfg = cfg.get("wsl", {})
    if not isinstance(wsl_cfg, dict):
        return False
    enabled = wsl_cfg.get("enabled", {})
    if isinstance(enabled, dict):
        return bool(enabled.get(provider, False))
    return bool(enabled)


def _wsl_distro(cfg):
    wsl_cfg = cfg.get("wsl", {})
    if not isinstance(wsl_cfg, dict):
        return ""
    return str(wsl_cfg.get("distro", "") or "").strip()


_wsl_default_cache = {"ts": 0.0, "name": ""}


def _wsl_default_distro_name():
    cached = _wsl_default_cache.get("name", "")
    if cached and (time.time() - _wsl_default_cache.get("ts", 0.0)) < 30:
        return cached
    exe = _resolve_wsl_exe()
    if not exe:
        return ""
    rc, lines, err = _wsl_list_output_lines(["-l", "-v"], timeout=3)
    if rc != 0:
        return ""
    for line in lines:
        if not line.startswith("*"):
            continue
        parts = line[1:].strip().split()
        if parts:
            name = parts[0]
            _wsl_default_cache["ts"] = time.time()
            _wsl_default_cache["name"] = name
            return name
    return ""


def _wsl_label(cfg):
    distro = _wsl_distro(cfg)
    if distro:
        return f"WSL:{distro}"
    default_distro = _wsl_default_distro_name()
    return f"WSL:{default_distro}" if default_distro else "WSL:既定"


def _wsl_default_help_text():
    default_distro = _wsl_default_distro_name()
    if default_distro:
        return f"  WSL既定: {default_distro} (*付きdistro)"
    return "  WSL既定: wsl -l -v の * が付くdistro"


def _wsl_distro_blank_help_text():
    default_distro = _wsl_default_distro_name()
    if default_distro:
        return f"  Distro空欄時は {default_distro} を使用"
    return "  WSL Distro空欄時にその既定を使用"


def _shell_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def _resolve_wsl_exe():
    exe = resolve_cmd("wsl")
    if not exe and os.name == "nt":
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
        for candidate in (os.path.join(windir, "Sysnative", "wsl.exe"),
                          os.path.join(windir, "System32", "wsl.exe")):
            if os.path.isfile(candidate):
                exe = candidate
                break
    return exe


def _wsl_decode_list_output(data):
    if isinstance(data, bytes):
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return data.decode("utf-16", errors="replace")
        if b"\x00" in data:
            return data.decode("utf-16-le", errors="replace")
        return data.decode("utf-8", errors="replace")
    # wsl.exe -l 系は環境により NUL 混じりで見えることがあるため、表示用に正規化する。
    return (data or "").replace("\x00", "")


def _wsl_output_lines(data):
    text = _wsl_decode_list_output(data)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _wsl_list_output_lines(args, timeout=3):
    exe = _resolve_wsl_exe()
    if not exe:
        return 127, [], "wsl.exe が見つかりません。"
    rc, out, err = run_cmd_bytes([exe, *args], timeout=timeout)
    if rc != 0:
        detail = _wsl_decode_list_output(err or out).strip()
        return rc, [], detail
    return rc, _wsl_output_lines(out), ""


def _wsl_cycle_cache(cfg):
    cache = cfg.get("_wsl_cycle_cache") if isinstance(cfg, dict) else None
    return cache if isinstance(cache, dict) else None


def _wsl_running_status(cfg):
    exe = _resolve_wsl_exe()
    if not exe:
        return False, "wsl.exe が見つかりません。WSL を有効化してから再実行してください。"
    distro = _wsl_distro(cfg)
    cache = _wsl_cycle_cache(cfg)
    cache_key = ("running_status", distro.lower())
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    rc, running, err = _wsl_list_output_lines(["--list", "--running", "--quiet"], timeout=3)
    if rc != 0:
        detail = mask_path(redact_text(err.strip()))[:150]
        result = (False, f"WSL の起動状態を確認できませんでした: {detail or '不明なエラー'}")
        if cache is not None:
            cache[cache_key] = result
        return result
    if distro:
        if any(line.lower() == distro.lower() for line in running):
            result = (True, "")
        else:
            result = (False, f"WSL ディストリビューション '{distro}' が起動していません。`wsl -d {distro}` で起動してから再取得してください。")
        if cache is not None:
            cache[cache_key] = result
        return result
    default_distro = _wsl_default_distro_name()
    if default_distro:
        if any(line.lower() == default_distro.lower() for line in running):
            result = (True, "")
        else:
            result = (False, f"WSL 既定ディストリビューション '{default_distro}' が起動していません。`wsl -d {default_distro}` で起動してから再取得してください。")
    elif running:
        result = (False, "WSL 既定ディストリビューションを確認できませんでした。`wsl -l -v` で既定を確認してください。")
    else:
        result = (False, "WSL 既定ディストリビューションが起動していません。WSL を起動してから再取得してください。")
    if cache is not None:
        cache[cache_key] = result
    return result


def _wsl_linux_command_path(cfg, name):
    if not re.fullmatch(r"[0-9A-Za-z._-]+", name or ""):
        return None
    cache = _wsl_cycle_cache(cfg)
    cache_key = ("command_path", _wsl_distro(cfg).lower(), name)
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    script = f'command -v {_shell_quote(name)} 2>/dev/null | head -n 1'
    rc, out, err = run_wsl_sh(cfg, script, timeout=5)
    if rc != 0:
        if cache is not None:
            cache[cache_key] = None
        return None
    path = (out or "").strip().splitlines()
    if not path:
        if cache is not None:
            cache[cache_key] = None
        return None
    path = path[0].strip()
    if re.match(r"^/mnt/[A-Za-z]/", path):
        if cache is not None:
            cache[cache_key] = None
        return None
    result = path or None
    if cache is not None:
        cache[cache_key] = result
    return result


def _wsl_linux_command_exists(cfg, name):
    return _wsl_linux_command_path(cfg, name) is not None


def build_wsl_cmd(cfg, args):
    """wsl.exe 経由で WSL 内コマンドを実行する argv を組み立てる。"""
    exe = _resolve_wsl_exe()
    if not exe:
        return None
    cmd = [exe]
    distro = _wsl_distro(cfg)
    if distro:
        cmd.extend(["-d", distro])
    cmd.append("--")
    cmd.extend(args)
    return cmd


def run_wsl_sh(cfg, script, timeout=30):
    cmd = build_wsl_cmd(cfg, ["sh", "-lc", script])
    if not cmd:
        return 127, "", "wsl.exe が見つかりません。"
    return run_cmd(cmd, timeout=timeout)


def run_wsl_cmd(cfg, args, timeout=30):
    cmd = build_wsl_cmd(cfg, args)
    if not cmd:
        return 127, "", "wsl.exe が見つかりません。"
    return run_cmd(cmd, timeout=timeout)


def _wsl_path_exists(cfg, test_flag, path_expr):
    if test_flag not in ("-f", "-d", "-e"):
        return False
    path = str(path_expr).strip('"')
    if path.startswith("$HOME/"):
        script = f'p="$HOME"/{_shell_quote(path[len("$HOME/"):])}; test {test_flag} "$p"'
    elif path.startswith("~/"):
        script = f'p="$HOME"/{_shell_quote(path[2:])}; test {test_flag} "$p"'
    else:
        script = f'test {test_flag} {_shell_quote(path)}'
    rc, out, err = run_wsl_sh(cfg, script, timeout=5)
    return rc == 0
