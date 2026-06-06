# AI Usage Tray Agent Skills

`.agents/skills/` は、AI コーディングエージェントが GitHub 運用やレビューで参照する共通スキル置き場です。

- `skills/issue/SKILL.md`: GitHub Issue の起票、整理、調査用。
- `skills/pr/SKILL.md`: Pull Request の作成、本文テンプレート、Issue 連動用。
- `skills/review/SKILL.md`: Pull Request やローカル差分レビュー用（GitHub PR では該当行へインラインコメントで投稿）。

## `.claude/skills/` との同期

Claude Code はスキルを `.claude/skills/` からしか自動検出しないため、同じ内容のコピーが `.claude/skills/{github-issue,github-pr,github-review}/SKILL.md` にあります。

- **`.claude/skills/` が「正」**。スキルを変更したら、こちら（`.agents/skills/`）の対応ファイルも同じ内容へ更新して同期する。
- Windows ではシンボリックリンクが使えないため、リンクではなくファイルコピーで運用する。

共通のリポジトリ前提はルートの `AGENTS.md` を参照してください。
