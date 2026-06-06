# Claude Code Skills（正本）

このディレクトリは **Claude Code が自動検出する invokable スキル**の置き場です。
Claude Code はスキルを `.claude/skills/`（プロジェクト）または `~/.claude/skills/`（ユーザー）からのみ検出するため、
`/github-issue`・`/github-pr`・`/github-review` として使うにはここに置く必要があります。

## スキル一覧

- `github-issue/SKILL.md`: GitHub Issue の起票・整理・調査。
- `github-pr/SKILL.md`: Pull Request の作成・本文テンプレート・Issue 連動。
- `github-review/SKILL.md`: PR / ローカル差分レビュー。**GitHub PR では指摘を該当行へインラインコメントとして投稿する**。

## `.agents/skills/` との関係（同期メモ）

同じ内容のコピーが `.agents/skills/{issue,pr,review}/SKILL.md` にもあります（Codex など Claude Code 以外のエージェントが読むため）。

- **本ディレクトリ（`.claude/skills/`）を「正」**とする。
- スキルの内容を変更したら、`.agents/skills/` 側の対応ファイルも**同じ内容に更新**して同期する。
- Windows ではシンボリックリンクが使えないため、リンクではなくファイルコピーで運用する。

## 注意

- `.claude/settings.local.json` はローカル設定のためコミットしない（`.gitignore` 済み）。本ディレクトリ（`skills/`）のみコミットする。
