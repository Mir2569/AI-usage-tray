# リポジトリ共通ガイド

## このファイルの役割

`AGENTS.md` は、AI コーディングエージェントが最初に読む共通ルールです。
このリポジトリでは、Windows 向けの小さなタスクトレイアプリとして、実用的で小さな変更を優先します。

詳しい GitHub 運用やレビュー観点は `.agents/skills/` 配下の Agent Skill を参照してください。

- Issue 起票: `.agents/skills/issue/SKILL.md`
- PR 作成: `.agents/skills/pr/SKILL.md`
- レビュー: `.agents/skills/review/SKILL.md`

この `.agents/skills/` が内容の正です。Claude Code は同内容の同期コピーを `.claude/skills/` から自動検出し、`/github-issue`・`/github-pr`・`/github-review` として使えます。編集は `.agents/skills/` 側で行い、`.claude/skills/` へコピーして同期すること（詳細は `.claude/skills/README.md`）。GitHub PR のレビューは、指摘を該当行へインラインコメントで投稿するのを既定とします。

## 基本方針

- やり取り、PR 本文、レビューコメント、開発メモは基本的に日本語で書く。
- コマンドで文字コードを指定できる場合は、基本的に UTF-8 を指定する。
- Windows / PowerShell 前提で考える。macOS / Linux 対応は明示依頼がある場合だけ扱う。
- 変更は要求された範囲に絞り、`ai_usage_tray/` パッケージの責務分割（Issue #55）に沿って、該当モジュールへ最小限に加える。
- 既存の設定キー、README、`config.example.json`、ビルド手順の整合性を崩さない。
- `.bat` は ASCII を基本にする。日本語表示が必要な場合は Python や Markdown 側へ寄せる。

## 作業開始チェック

作業を始める前に、必ず次を確認します。

```powershell
git status --short --branch
git branch --show-current
git log --oneline --decorate -5
```

- 未コミット変更や未追跡ファイルがある場合は、ユーザー由来の変更として扱い、勝手に破棄しない。
- ユーザーが「新しいブランチで」と指示した場合は、`main` に直接コミットしない。
- 既存ブランチを再開する場合は、必要に応じて `origin/main` との差分を確認する。

## プロジェクト概要

AI Usage Tray は、Claude Code / Codex / Antigravity の残り使用量を Windows の通知領域に常駐表示する Python アプリです。

主な構成:

- `ai_usage_tray.py`: 薄いランチャ。実体は `ai_usage_tray/` パッケージへ委譲（`python -m ai_usage_tray` でも起動可）。
- `ai_usage_tray/`: 本体パッケージ。トレイ UI（`tray.py`）、各 provider（`providers/`）、設定読み込み（`config.py`）、WSL ヘルパー（`wsl.py`）、診断（`probe.py`）、設定 GUI（`gui.py`）等に分割。
- `config.example.json`: 公開用の設定サンプル。
- `config.json`: ローカル設定。コミットしない。
- `requirements.txt`: 実行依存。
- `build_exe.bat`: Python 3.12 venv と PyInstaller による onedir ビルド。
- `run.bat`, `setup.bat`, `start_hidden.vbs`: ローカル実行補助。
- `CLAUDE.md`: 調査済み仕様と引き継ぎメモ。

## ローカル状態と秘密情報

以下はローカル状態や秘密情報を含む可能性があるため、コミットしません。

- `config.json`
- `build/`
- `dist/`
- `*.spec`
- `.venv/`, `.venv312/`, `venv/`, `env/`
- `scratch/`
- `*.log`
- `*.tmp`

公開用の設定例は `config.example.json` を使います。

特に注意すること:

- Claude Code の OAuth トークンは `~/.claude/.credentials.json` または環境変数から読むだけにし、ログや README、Issue、PR に値を出さない。WSL 切替時は WSL 側 `~/.claude/.credentials.json` / `CLAUDE_CODE_OAUTH_TOKEN` を参照するが、同様に値は出さない。
- `python ai_usage_tray.py --probe` の出力を外部に貼るときは、API レスポンスやローカルパスに不要な情報が含まれていないか確認する。WSL 側の `/home/<user>` や `/mnt/<drive>/Users/<user>` も `mask_path` でマスクされるが、貼る前に必ず目視確認する。
- `npx -y antigravity-usage --json` など外部コマンドの出力をそのまま公開しない。

## 開発コマンド

依存関係のインストール:

```powershell
python -m pip install -r requirements.txt
```

1 回だけ取得して確認:

```powershell
python ai_usage_tray.py --once
```

診断:

```powershell
python ai_usage_tray.py --probe
```

トレイ常駐起動:

```powershell
python ai_usage_tray.py
```

ビルド:

```powershell
.\build_exe.bat
```

## 検証コマンド

変更内容に応じて、可能な範囲で実行します。

```powershell
python -m py_compile ai_usage_tray.py
git diff --check
```

README、Agent Skill、設定サンプルなどのドキュメントのみを変更した場合も、`git diff --check` は実行してください。

## レビュー観点

- `config.json` などのローカル状態がコミット対象に入っていないか。
- `config.example.json` と実装の設定キーがずれていないか。
- Windows の文字コード、PowerShell、`.bat`、`subprocess`、PyInstaller onedir ビルドが壊れていないか。
- `shell=False` やコマンド解決の安全性が維持されているか。
- OAuth トークン、API レスポンス、ローカルパスを不用意に出力していないか。
- WSL 切替（`wsl.enabled.*`）が既定 false で、設定なしの従来 Windows 動作を維持しているか。`wsl.exe` 実行も `shell=False` と interop（`/mnt/`）誤実行回避が保たれているか。
- README の使い方と実際のコマンドが一致しているか。

## GitHub 運用

- PR 本文、Issue 本文、コメントは日本語で書く。
- Windows / PowerShell のクォート事故を避けるため、長い本文は `scratch/` に置き、`gh ... --body-file` で投稿する。
- 対応 Issue がある PR では、本文に `Closes #<Issue番号>` または `Fixes #<Issue番号>` を正確に書く。
- 作業完了時は、変更ファイル、検証結果、未実行チェックを短く報告する。

### マージ完了の連絡を受けたとき

ユーザーが「マージした」「マージ済み」などと伝えたら、作業ツリーを確認してから `main` を最新化します。

```powershell
git status --short --branch
git switch main
git pull origin main
```

未コミット変更がある場合は、切り替えずに内容を報告して指示を待ちます。

## リリース作成

Releases へバイナリ配布を追加するときの手順です。既存リリース（v1.0.0 / v1.1.0 / v1.2.0）の形式に合わせます。

### バージョン番号

- タグは `vX.Y.Z`（SemVer）。`main` の最新コミットを対象にします。
- MAJOR: 互換性を壊す変更 / MINOR: 後方互換の新機能 / PATCH: 後方互換の不具合修正。
- 直前リリースからの変更を確認します。

```powershell
git tag --sort=-v:refname
git log v<直前>..main --oneline --merges
```

### exe ビルド

`build_exe.bat` と同じく **Python 3.12 専用 venv** でビルドします（**3.14 は不可**。起動しない exe ができる）。`.bat` は末尾に `pause` があり非対話実行ではハングするため、エージェントが回す場合は手順を直接実行します。

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
.\.venv312\Scripts\python.exe -m PyInstaller --onedir --noconsole --clean --noconfirm `
  --name AIUsageTray --icon app.ico --hidden-import pystray._win32 `
  --collect-submodules ai_usage_tray ai_usage_tray.py
Copy-Item -Force app.ico dist\AIUsageTray\app.ico   # 設定ウィンドウのアイコン用
```

- `dist\AIUsageTray\` が成果物（onedir）。`AIUsageTray.exe` を起動して常駐することを確認してから配布します。
- **個人の `config.json` は同梱しない**（WSL distro 名などローカル設定が漏れる）。`build_exe.bat` はローカル用に config.json をコピーするが、リリース zip には含めないこと。`app.ico` は exe 同階層へ同梱する。
- `*.spec`・`build/`・`dist/`・`.venv312/` は追跡しない（gitignore 済み）。

### zip 化と公開

成果物を `AIUsageTray-vX.Y.Z-windows-x64.zip` にまとめ、`gh release create` で添付します。

```powershell
Compress-Archive -Path "dist\AIUsageTray\*" -DestinationPath "AIUsageTray-vX.Y.Z-windows-x64.zip" -CompressionLevel Optimal
# zip に config.json が混ざっていないか確認してから公開する
gh release create vX.Y.Z --target main --title "vX.Y.Z — 要約" `
  --notes-file scratch\release_notes.md "AIUsageTray-vX.Y.Z-windows-x64.zip"
```

### リリースノートの書式

絵文字は使わず、既存リリースと同じ構成にします（本文は `scratch/` に置いて `--notes-file` で渡す）。

```markdown
## AI Usage Tray vX.Y.Z

<!-- 1-2文の概要 -->

### 主な変更

- <!-- ユーザー視点の変更を平易な箇条書きで。外部貢献は「（@user さんによる貢献）」を付ける -->

### インストール方法

1. 下の `AIUsageTray-vX.Y.Z-windows-x64.zip` をダウンロード
2. 任意のフォルダに展開
3. `AIUsageTray.exe` をダブルクリックで起動

### 動作要件

<!-- v1.1.0 / v1.2.0 と同じ Windows 10/11・各サービスの認証情報の節 -->

### 設定

<!-- 初回起動ダイアログ・トレイの「設定...」・config.json の案内 -->
```

末尾に `**Full Changelog**: https://github.com/Mir2569/ai-usage-tray/compare/v<直前>...vX.Y.Z` を付けます。
