# -*- coding: utf-8 -*-
"""Provider: Antigravity  (antigravity-usage --json)。"""

import os
import re
import json

from ..config import DEFAULT_CONFIG
from ..utils import parse_dt, run_cmd, resolve_cmd
from ..redact import mask_path, redact_text
from ..wsl import (
    _provider_uses_wsl,
    _wsl_running_status,
    _wsl_label,
    _resolve_wsl_exe,
    _wsl_linux_command_path,
    build_wsl_cmd,
)
from .types import make_window


def _walk_find_models(obj, found, parent_key=None, depth=0):
    """JSON を再帰的に走査し、remaining 系 + reset 系を持つオブジェクトを収集。
    モデル名が辞書のキー(例 {"models":{"Gemini 3.5 Flash":{...}}})の場合は
    parent_key を名前として採用する。
    入力は信頼できる CLI 出力だが、想定外に深くネストした JSON でのスタック超過を
    避けるため depth に上限を設け、超えたら打ち切る。"""
    if depth > 50:
        return
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
            found.append({
                "name": name,
                "remain_raw": obj.get(remain_key) if remain_key else None,
                "used_raw": obj.get(used_key) if used_key else None,
                "reset_raw": obj.get(reset_key) if reset_key else None,
                "auto": auto,
            })
        for k, v in obj.items():
            _walk_find_models(v, found, parent_key=k, depth=depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk_find_models(v, found, parent_key=parent_key, depth=depth + 1)


def _antigravity_npx_pkg(cfg):
    version = str(cfg.get("antigravity_usage_version", "") or "").strip()
    if version and not re.fullmatch(r"[0-9A-Za-z._-]+", version):
        version = DEFAULT_CONFIG["antigravity_usage_version"]
    return f"antigravity-usage@{version}" if version else "antigravity-usage"


def build_antigravity_cmd(cfg):
    """antigravity-usage 実行コマンドを決める。返り値は (cmd or None, reason)。
    cmd が None のとき reason に理由(ユーザー向けメッセージ)を入れる。"""
    if _provider_uses_wsl(cfg, "antigravity"):
        if not _resolve_wsl_exe():
            return None, "wsl.exe が見つかりません。WSL を有効化してから再実行してください。"
        fallback = bool(cfg.get("antigravity_npx_fallback", False))
        pkg = _antigravity_npx_pkg(cfg)
        exe = _wsl_linux_command_path(cfg, "antigravity-usage")
        if exe:
            return build_wsl_cmd(cfg, [exe, "--json"]), None
        if fallback:
            npx = _wsl_linux_command_path(cfg, "npx")
            if npx:
                return build_wsl_cmd(cfg, [npx, "-y", pkg, "--json"]), None
            return None, "Linux 側の antigravity-usage も npx も見つかりません。WSL 側で npm i -g antigravity-usage を実行してください。"
        return None, "Linux 側の antigravity-usage が見つかりません。WSL 側で npm i -g antigravity-usage を実行するか、antigravity_npx_fallback を有効化してください。"

    paths_cfg = cfg.get("paths", {})
    if not isinstance(paths_cfg, dict):
        paths_cfg = {}
    exe = resolve_cmd("antigravity-usage", paths_cfg.get("antigravity_usage", ""))
    if exe:
        return [exe, "--json"], None
    # ローカルに見つからない場合の npx フォールバック。常駐アプリが裏で npm から
    # コードを取得・実行することになるため、既定では無効(opt-in)。
    if not cfg.get("antigravity_npx_fallback", False):
        return None, ("antigravity-usage が見つかりません。`npm i -g antigravity-usage` で導入するか、"
                      "設定で antigravity_npx_fallback を有効化してください。")
    npx = resolve_cmd("npx")
    if not npx:
        return None, "antigravity-usage も npx も見つかりません。`npm i -g antigravity-usage` を実行してください。"
    # 版固定でサプライチェーンリスクを抑える(空なら無印=最新だが非推奨)。
    pkg = _antigravity_npx_pkg(cfg)
    return [npx, "-y", pkg, "--json"], None


def provider_antigravity(cfg):
    res = {"name": "Antigravity", "ok": False, "error": None, "windows": [], "note": ""}
    use_wsl = _provider_uses_wsl(cfg, "antigravity")
    if use_wsl:
        ready, message = _wsl_running_status(cfg)
        if not ready:
            res["error"] = message
            return res
    cmd, reason = build_antigravity_cmd(cfg)
    if not cmd:
        res["error"] = reason
        return res

    rc, out, err = run_cmd(cmd, timeout=60)
    if rc != 0 or not out.strip():
        # 外部 CLI の stderr/stdout には email/token/パス等が混じり得る。エラー文は
        # --probe / --once の正規化結果やトレイにも表示されるため、必ず秘匿・パスマスク
        # してから(全文に適用後に)切り詰める。
        detail = mask_path(redact_text((err or out).strip()))[:200]
        res["error"] = f"antigravity-usage 実行失敗: {detail}"
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
    raw_windows = []
    for item in found:
        if item.get("auto") and not show_auto:
            continue
        name = str(item["name"]) if item["name"] is not None else "model"
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        rp = remaining_pct_of(item)
        reset_at = parse_dt(item["reset_raw"])
        raw_windows.append(make_window(name, remaining_pct=rp, reset_at=reset_at))

    # 同一残り割合・リセット日時のモデルをグループ化して集約する
    groups = {}
    keys_order = []
    for w in raw_windows:
        rp = w["remaining_pct"]
        rp_key = round(rp, 2) if rp is not None else None
        reset_key = w["reset_at"]
        key = (rp_key, reset_key)
        if key not in groups:
            groups[key] = []
            keys_order.append(key)
        groups[key].append(w)

    for key in keys_order:
        group = groups[key]
        if len(group) == 1:
            res["windows"].append(group[0])
        else:
            labels = [w["label"] for w in group]
            common_prefix = os.path.commonprefix(labels).rstrip(" -_/.([")
            if len(common_prefix) >= 3:
                # 共通接頭辞がある(例: Gemini 3.x 群)→ それをそのまま枠名にする
                base = common_prefix
            else:
                # 接頭辞が無い混在枠(例: Claude + GPT-OSS)→ 先頭ファミリ名を列挙
                fams = []
                for lb in labels:
                    fam = lb.split(" ")[0]
                    if fam not in fams:
                        fams.append(fam)
                base = " / ".join(fams)

            repr_w = dict(group[0])
            repr_w["label"] = f"{base} (共通枠)"
            res["windows"].append(repr_w)

    # 残りが少ない枠を上に表示(最も余裕のない枠を優先)。残量不明は末尾へ。
    res["windows"].sort(key=lambda w: w["remaining_pct"] if w["remaining_pct"] is not None else float("inf"))

    if res["windows"]:
        res["ok"] = True
        if use_wsl:
            res["note"] = _wsl_label(cfg)
    else:
        res["error"] = "モデルを抽出できませんでした(--probe で生データ確認)。"
    return res
