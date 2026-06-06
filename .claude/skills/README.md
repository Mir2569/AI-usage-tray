# Claude Code Skills（`.agents/skills/` の同期コピー）

このディレクトリは **Claude Code が自動検出する invokable スキル**の置き場です。
Claude Code はスキルを `.claude/skills/`（プロジェクト）または `~/.claude/skills/`（ユーザー）からのみ検出するため、
`/github-issue`・`/github-pr`・`/github-review` として使うにはここにファイルを置く必要があります。

ただし内容の**正は `.agents/skills/`** です。ここはそれを Claude Code 用に読み込めるよう置いた同期コピーで、直接の編集起点にはしません。

## スキル一覧

- `github-issue/SKILL.md`: GitHub Issue の起票・整理・調査。
- `github-pr/SKILL.md`: Pull Request の作成・本文テンプレート・Issue 連動。
- `github-review/SKILL.md`: PR / ローカル差分レビュー。**GitHub PR では指摘を該当行へインラインコメントとして投稿する**。

## `.agents/skills/` との関係（同期メモ）

正の内容は `.agents/skills/{issue,pr,review}/SKILL.md` にあります（Codex など Claude Code 以外のエージェントが読む場所）。

- **`.agents/skills/` が「正」**。編集はそちらで行う。
- スキルを変更したら、本ディレクトリ（`.claude/skills/`）の対応ファイルも**同じ内容にコピーして同期**する（Claude Code が読みに行くのはここ）。
- Windows ではシンボリックリンクが使えないため、リンクではなくファイルコピーで運用する。

## 注意

- `.claude/settings.local.json` はローカル設定のためコミットしない（`.gitignore` 済み）。本ディレクトリ（`skills/`）のみコミットする。
