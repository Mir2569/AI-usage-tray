# -*- coding: utf-8 -*-
"""共通ユーティリティ。日時整形・サブプロセス実行・コマンド解決。"""

import os
import subprocess
from datetime import datetime, timezone


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
        # fromisoformat 失敗時(古い Python 等)の strptime フォールバック。
        # Python 3.10 以下は ミリ秒(%f)付き ISO を fromisoformat で扱えないため %f 形式も用意。
        # まず %z でTZオフセット付きのまま解釈し、オフセットを失わないようにする
        # (Python 3.7+ の %z は Z / +0900 / +09:00 を解釈できる)。
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        # TZ 指定が無い文字列のみ UTC とみなす
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
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


def _decode_best(data):
    """bytes を UTF-8 優先、ダメなら CP932 でデコードする。

    Windows ネイティブのコマンド(npm/npx など)はシステムロケール(日本語環境では
    CP932)でエラーメッセージを出すことがある。UTF-8 固定の errors="replace" だと
    日本語が `�` だらけになり原因が読めなくなるため、UTF-8 で失敗したら CP932 で
    再試行する。どちらの厳密デコードも失敗した場合のみ UTF-8(置換)で確実に文字列化する。
    JSON 出力(Codex/Antigravity/WSL)は妥当な UTF-8 なので UTF-8 で成功し、CP932 へは
    落ちない。"""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    for enc in ("utf-8", "cp932"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def run_cmd(cmd, timeout=30):
    """コマンドを実行し (returncode, stdout, stderr)。Windows の .cmd shim も考慮。
    timeout=None を渡すと無期限に待つ(終了が不定なサブプロセス用)。
    出力は UTF-8 優先・CP932 フォールバックでデコードする(日本語 Windows のネイティブ
    エラーが文字化けしないように)。"""
    rc, out, err = run_cmd_bytes(cmd, timeout=timeout)
    return rc, _decode_best(out), _decode_best(err)


def run_cmd_bytes(cmd, timeout=30):
    """コマンドを実行し (returncode, stdout_bytes, stderr_bytes) を返す。"""
    kwargs = {}
    shell = False
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        target = cmd[0] if isinstance(cmd, list) else cmd
        if str(target).lower().endswith((".bat", ".cmd")):
            shell = True
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=timeout,
            shell=shell,
            **kwargs,
        )
        return proc.returncode, proc.stdout or b"", proc.stderr or b""
    except FileNotFoundError as e:
        return 127, b"", str(e).encode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, b"", b"timeout"
    except Exception as e:
        return 1, b"", str(e).encode("utf-8", errors="replace")


def resolve_cmd(name, explicit=""):
    """実行可能なコマンドのパスを返す。見つからなければ None。
    コマンドプリロード攻撃を防ぐため、PATH 内の絶対パスのディレクトリのみを探索する。"""
    if explicit:
        if os.path.exists(explicit):
            return explicit
        # Windows では拡張子を省略して指定されることがあるので補完して再確認
        if os.name == "nt":
            for ext in (".cmd", ".exe", ".bat"):
                if os.path.exists(explicit + ext):
                    return explicit + ext

    exts = [""]
    if os.name == "nt":
        exts = [".cmd", ".exe", ".bat", ""]

    path_env = os.environ.get("PATH", "")
    sep = ";" if os.name == "nt" else ":"
    for folder in path_env.split(sep):
        folder = folder.strip().strip('"')
        if not folder or not os.path.isabs(folder):
            continue
        for ext in exts:
            p = os.path.join(folder, name + ext)
            # Windows では os.access(X_OK) がファイル存在でほぼ常に True を返し実行可否
            # 判定にならない。拡張子(PATHEXT 相当の exts)で既に絞っているため isfile で十分。
            # POSIX のみ実行ビットを併用する。
            if os.name == "nt":
                if os.path.isfile(p):
                    return p
            elif os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None
