---
name: github-pr
description: AI Usage Tray で Pull Request を作成・編集するときに使う。専用ブランチ運用、--body-file、本文テンプレート、Issue 連動、公開前の秘密情報確認を含む。
---

# GitHub Pull Request Skill

## 使う場面

Pull Request を作成・編集するときに使います。
PR タイトル、本文、コメントは日本語で書きます。

## 基本方針

- 直接 `main` にコミットしない。専用ブランチで作業する。
- ローカル状態や秘密情報をコミットや本文に含めない。
- 変更は要求された範囲に絞る。
- 長い本文は `scratch/` に置き、`gh pr create --body-file` で投稿する。

## PR 作成手順

1. 作業前に状態を確認する。
   ```powershell
   git status --short --branch
   git branch --show-current
   ```
2. 専用ブランチで変更し、検証する。
3. コミットしてリモートへ push する。
   ```powershell
   git push -u origin <ブランチ名>
   ```
4. PR 本文を `scratch\pr_body.md` に作成し、`--body-file` で PR を作る。
   ```powershell
   gh pr create --base main --head <ブランチ名> `
     --title "[カテゴリ] PR のタイトル" `
     --body-file "scratch\pr_body.md"
   ```

## PR 本文テンプレート

```markdown
## 概要

<!-- 何を直す/作る PR かを1-3文で書く -->

## 変更内容

- <!-- 変更したファイルと内容 -->

## 検証

- <!-- 実行したコマンド。未実行があれば理由を書く -->

## 関連 Issue

<!-- Closes #<番号>。無ければ「なし」 -->
```

## Issue 連動

対応する Issue がある場合は、PR 本文に `Closes #<Issue番号>` または `Fixes #<Issue番号>` を書きます。

例:

```markdown
## 関連 Issue

Closes #12
```

`Closes # 12` のように `#` と番号の間を空けると自動クローズが効かないため注意します。

## 作成前チェック

```powershell
git status --short --ignored
git diff --check
git diff --cached --name-status
```

特に `config.json`, `build/`, `dist/`, `*.spec`, `.venv312/`, `scratch/` が含まれていないことを確認します。
