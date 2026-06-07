# -*- coding: utf-8 -*-
"""秘匿・マスク処理。--probe 出力等を Issue/PR に貼っても環境情報が漏れにくくする。"""

import os
import re

from .constants import HOME


def mask_path(path):
    """パスに含まれる HOME / ユーザー名部分をマスクする。
    HOME だけでなく C:\\Users\\<名前>(区切り・大小文字違い)や環境変数のユーザー名も伏せ、
    --probe 出力を Issue/PR に貼ってもローカル環境が漏れにくいようにする。"""
    if not path:
        return path
    if isinstance(path, list):
        return [mask_path(p) for p in path]
    s = str(path).replace(HOME, "~")
    # C:\Users\<名前> / C:/Users/<名前> 等(ドライブ・区切り・大小文字を問わず)
    s = re.sub(r"([A-Za-z]:[\\/]+Users[\\/]+)[^\\/]+", r"\1***", s, flags=re.IGNORECASE)
    s = re.sub(r"(/home/)[^/]+", r"\1***", s)
    s = re.sub(r"(/mnt/[A-Za-z]/Users/)[^/]+", r"\1***", s, flags=re.IGNORECASE)
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if user:
        s = re.sub(re.escape(user), "***", s, flags=re.IGNORECASE)
    return s


# 機密と思しきキー名(値を伏せる対象)。dict / 文字列の両方の秘匿で共用する。
_SECRET_KEYS = (
    r"access_?token|refresh_?token|id_?token|api[_-]?key|secret|password|passwd|"
    r"authorization|bearer|cookie|credential|token|email"
)
_SECRET_KEY_RE = re.compile(r"(" + _SECRET_KEYS + r")", re.IGNORECASE)

# 文字列(JSON 化できない生出力)向け: "key": "値" / key=値 / クォート無し値 を *** にする。
_SECRET_TEXT_QUOTED_RE = re.compile(
    r'("(?:' + _SECRET_KEYS + r')"\s*:\s*")[^"]*(")', re.IGNORECASE)
# key の後ろは "Bearer <token>" のように値が複数語になり得るので、区切り(改行/カンマ等)
# まで丸ごと伏せて取りこぼしを防ぐ。
_SECRET_TEXT_BARE_RE = re.compile(
    r'((?:' + _SECRET_KEYS + r')\s*[:=]\s*)([^\r\n,;}]+)', re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def redact_secrets(obj):
    """dict/list を再帰的に走査し、機密と思しきキーの値を *** に置換する。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEY_RE.search(k):
                out[k] = "***"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(v) for v in obj]
    return obj


def redact_text(s):
    """JSON 化できない生文字列向けの秘匿。機密キーの値や素のメールアドレスを *** にする。
    壊れた JSON や警告ログ混じりの出力でもトークン/メール等が漏れないようにする。"""
    if not s:
        return s
    s = _SECRET_TEXT_QUOTED_RE.sub(r"\1***\2", s)
    s = _SECRET_TEXT_BARE_RE.sub(r"\1***", s)
    s = _EMAIL_RE.sub("***@***", s)
    return s
