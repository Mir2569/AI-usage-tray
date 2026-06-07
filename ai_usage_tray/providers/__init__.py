# -*- coding: utf-8 -*-
"""Provider レジストリ。各 provider は cfg を受け取り正規化結果 dict を返す。"""

from .codex import provider_codex
from .claude import provider_claude
from .antigravity import provider_antigravity

PROVIDERS = [
    ("claude", provider_claude),
    ("codex", provider_codex),
    ("antigravity", provider_antigravity),
]

# トレイメニュー等で使うプロバイダの表示名(キー→ラベル)
PROVIDER_NAMES = {
    "claude": "Claude",
    "codex": "Codex",
    "antigravity": "Antigravity",
}

__all__ = [
    "PROVIDERS",
    "PROVIDER_NAMES",
    "provider_codex",
    "provider_claude",
    "provider_antigravity",
]
