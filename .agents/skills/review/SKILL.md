---
name: github-review
description: AI Usage Tray で Pull Request、コミット差分、作業中のローカル差分をレビューするときに使う。GitHub PR では指摘を該当行へインラインコメントとして投稿する。Windows トレイアプリ、認証情報、外部コマンド、PyInstaller、README 整合性の重点観点を含む。
---

# GitHub Review Skill

## 使う場面

Pull Request、コミット差分、または作業中のローカル差分をレビューするときに使います。
レビューコメント、要約、提案は日本語で返します。

## レビュー方針

- 指摘は重要度順に並べる。
- バグ、回帰、起動失敗、秘密情報混入、ユーザー操作不能を優先する。
- ファイル名と行番号をできるだけ明示する。
- 推測で断定しない。確認できないものは「未確認」と書く。
- 良い点の列挙より、修正すべき具体的なリスクを優先する。

## 重点的に見ること

- `config.json` などのローカル状態がコミット対象に入っていないか。
- Claude OAuth トークンや API レスポンス、ローカルパスを不用意に表示・保存していないか。
- `config.example.json` と `DEFAULT_CONFIG` の設定キーが一致しているか。
- `subprocess.run(..., shell=False)`、UTF-8 デコード、Windows の `CREATE_NO_WINDOW` が維持されているか。
- `npx -y antigravity-usage --json` のフォールバックが Windows で壊れていないか。
- WSL 切替（`wsl.enabled.*`）が既定 false で従来動作を維持し、`wsl.exe` 実行も `shell=False`・interop（`/mnt/`）誤実行回避が保たれているか。
- PyInstaller onedir ビルドで必要なファイル、アイコン、設定コピーが壊れていないか。
- README の使い方、診断手順、ビルド手順が実装と一致しているか。
- `.bat` に日本語を入れて cp932 文字化けやコマンド誤実行を誘発していないか。

## レビュー手順

1. 差分の目的を確認する。
2. 変更ファイルを分類する。
   - ランチャ: `ai_usage_tray.py` / 本体パッケージ: `ai_usage_tray/`（`providers/`, `tray.py`, `wsl.py`, `config.py` など）
   - 設定: `config.example.json`, `.gitignore`
   - 実行補助: `*.bat`, `*.vbs`
   - ドキュメント: `README.md`, `CLAUDE.md`, `AGENTS.md`, `.agents/**`
3. 影響範囲に応じて重点項目を確認する。
4. 可能なら関連チェックを実行する。
5. 指摘は「何が起きるか」「なぜ問題か」「どう直すか」を簡潔に書く。

## 出力先の使い分け

- **ローカル差分 / コミット差分**のレビュー → 下記「出力形式（テキスト）」の markdown を返す。
- **GitHub PR** のレビュー → 「PR にインラインで投稿する（既定）」に従い、サマリー本文 + 該当行インラインコメントを **1 レビューとして提出**する。

## 出力形式（テキスト）

問題がある場合:

```markdown
## 指摘

- [重大度: high] `path/to/file.py:123`
  問題内容。想定される影響。修正方針。

## 確認したこと

- 実行/確認したコマンドや観点。

## 残るリスク

- 未確認の実行環境や手動確認事項。
```

問題が見つからない場合:

```markdown
大きな問題は見つかりませんでした。

確認した範囲:
- `...`

未実行/残るリスク:
- `...`
```

## PR にインラインで投稿する（既定）

GitHub PR をレビューするときは、**指摘を該当行へインラインコメントで付け、サマリーと併せて 1 レビューとして提出する**のを既定にします。

- **レビュー種別**: `event: "COMMENT"` を使う。`APPROVE` / `REQUEST_CHANGES` は使わない（マージは基本的にユーザーが行うため）。
- **レビュア明示（必須）**: review 本文と各インラインコメントの末尾に `🤖 Claude Code（Opus 4.8）` を入れ、Claude Code のレビューと分かるようにする。
- **インライン 1 件ごとに重大度**: `[重大度: high/medium/low]` を付け、「問題 / 影響 / 修正案」を簡潔に書く。
- **良い点も任意でインライン可**: 設計上効いている箇所は 👍 とともに該当行へ。

### 1. 差分と行番号を確認する

`line` は **新ファイル側（RIGHT）の行番号**で、かつ **diff のハンク内**でなければ API がエラー（422）になります。

```powershell
gh pr view <PR> --json number,headRefName,headRepositoryOwner,headRepository,url
gh pr diff <PR>
```

正確な行番号が要るときは PR head の実ファイルを取得して数えます（`Accept: application/vnd.github.raw` で base64 ではなく生内容が返るため、PowerShell でもそのまま保存できます）。

```powershell
gh api "repos/<owner>/<repo>/contents/<path>?ref=<headRef>" -H "Accept: application/vnd.github.raw" > scratch\head_file.txt
```

### 2. レビュー JSON を `scratch/` に作る

PowerShell のクォート/マルチバイト事故を避けるため、ペイロードは `scratch/` に作って `--input` で渡します。日本語や `"` を含むため Python で書き出すのが安全です。

```json
{
  "event": "COMMENT",
  "body": "## サマリー\n（全体の所見・ブロッカー有無）\n\n🤖 Claude Code（Opus 4.8）",
  "comments": [
    {
      "path": "ai_usage_tray.py",
      "line": 438,
      "side": "RIGHT",
      "body": "[重大度: low] 問題 / 影響 / 修正案。\n\n🤖 Claude Code（Opus 4.8）"
    }
  ]
}
```

### 3. 1 レビューとして提出する

```powershell
gh api -X POST "repos/<owner>/<repo>/pulls/<PR>/reviews" --input "scratch\review.json"
```

確認（任意）:

```powershell
gh api "repos/<owner>/<repo>/pulls/<PR>/reviews" --jq ".[-1] | {state, html_url}"
```

### 注意点

- **行が diff 外だと 422**: コメントは変更行（追加・変更）に付ける。文脈行に付けたいときは近い変更行を選ぶ。
- **closing キーワードを地の文に書かない**: review 本文/コメントに `Closes #NN` を書くと別 PR の closing 参照に拾われ得る。番号参照は「#NN 対応」のようにキーワード無しで書く。
- **スコープ外・任意の指摘**: PR を肥大化させない軽微な改善は、レビューで触れつつ **別 Issue 化してリンク**する（`github-issue` スキルを併用）。ブロッカーでない旨を明記する。

## 検証コマンド

変更内容に応じて必要なものを選びます。

```powershell
python -m py_compile ai_usage_tray.py
python ai_usage_tray.py --once
python ai_usage_tray.py --probe
git diff --check
```

依存関係、認証状態、外部 CLI の不足で実行できない場合は、失敗理由を明記します。
