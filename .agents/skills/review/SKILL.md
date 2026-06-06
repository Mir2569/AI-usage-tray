---
name: github-review
description: AI Usage Tray で Pull Request、コミット差分、作業中のローカル差分をレビューするときに使う。Windows トレイアプリ、認証情報、外部コマンド、PyInstaller、README 整合性の重点観点を含む。
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
- PyInstaller onedir ビルドで必要なファイル、アイコン、設定コピーが壊れていないか。
- README の使い方、診断手順、ビルド手順が実装と一致しているか。
- `.bat` に日本語を入れて cp932 文字化けやコマンド誤実行を誘発していないか。

## レビュー手順

1. 差分の目的を確認する。
2. 変更ファイルを分類する。
   - 本体: `ai_usage_tray.py`
   - 設定: `config.example.json`, `.gitignore`
   - 実行補助: `*.bat`, `*.vbs`
   - ドキュメント: `README.md`, `CLAUDE.md`, `AGENTS.md`, `.agents/**`
3. 影響範囲に応じて重点項目を確認する。
4. 可能なら関連チェックを実行する。
5. 指摘は「何が起きるか」「なぜ問題か」「どう直すか」を簡潔に書く。

## 出力形式

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

## 検証コマンド

変更内容に応じて必要なものを選びます。

```powershell
python -m py_compile ai_usage_tray.py
python ai_usage_tray.py --once
python ai_usage_tray.py --probe
git diff --check
```

依存関係、認証状態、外部 CLI の不足で実行できない場合は、失敗理由を明記します。
