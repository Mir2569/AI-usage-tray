---
name: github-issue
description: AI Usage Tray で GitHub Issue を作成、整理、調査、または実装タスクへ分解するときに使う。Windows トレイアプリ、設定、ビルド、秘密情報除外を踏まえた Issue 化を含む。
---

# GitHub Issue Skill

## 使う場面

GitHub Issue を作成、整理、調査、または実装タスクへ分解するときに使います。
Issue 本文とコメントは日本語で書きます。

## 基本方針

- 事実、推測、未確認事項を分けて書く。
- `config.json` や診断出力など、ローカル状態や秘密情報を本文に含めない。
- Windows / PowerShell 前提で再現手順を書く。
- 単一ファイル構成の軽さを保ち、必要以上に大きな設計変更へ広げない。
- 変更は必ず Issue を先に立ててから PR を出す。PR を先に作らない。

## Issue 本文テンプレート

```markdown
## 概要

<!-- 何を直す/作る Issue かを1-3文で書く -->

## 背景

<!-- なぜ必要か。ユーザー体験、既存挙動、関連する過去判断を書く -->

## 現状

<!-- 確認できている現在の挙動。未確認なら未確認と書く -->

## 期待する挙動

<!-- 完了後にどう動いてほしいか -->

## 対象ファイル候補

- `ai_usage_tray.py`
- `README.md`
- `config.example.json`

## 受け入れ条件

- [ ] 期待する挙動を満たす
- [ ] `config.json` や秘密情報をコミットしない
- [ ] 必要な README / 設定サンプルを更新する

## 検証

- [ ] `python -m py_compile ai_usage_tray.py`
- [ ] `python ai_usage_tray.py --once`
- [ ] `python ai_usage_tray.py --probe`
- [ ] `git diff --check`
```

## gh で起票するとき

PowerShell のマルチバイト文字やクォート事故を避けるため、本文は `scratch/` に保存して `--body-file` で渡します。

```powershell
gh issue create --title "[カテゴリ] Issue のタイトル" --body-file "scratch\issue_body.md" --label "enhancement"
```

起票後はラベルと内容を確認します。

```powershell
gh issue view <番号> --json number,title,labels,url
```

## ラベルの目安

- `bug`: 起動失敗、取得失敗、表示崩れ、ビルド不備、回帰。
- `documentation`: README、開発者向け説明、セットアップ手順。
- `enhancement`: 新機能、改善、整理、リファクタリング。

ラベルが存在しない場合は、無理に作らず、ユーザーに確認します。
