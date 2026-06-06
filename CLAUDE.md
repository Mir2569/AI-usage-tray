# AI Usage Tray — 引き継ぎ／開発メモ

Claude Code / Codex / Antigravity の残り使用量を Windows のタスクトレイにまとめて常駐表示する Python アプリ。
このファイルは作業を引き継ぐ人（および Claude Code）向けの設計・仕様・既知の課題メモ。

## 何をするアプリか
- バックグラウンドスレッドで既定 5 分ごと（`config.json` の `refresh_seconds`）に 3 サービスの残量を取得。
- トレイアイコンに「最も余裕のない枠の残り%」を数字＋色（緑≥50 / 黄≥20 / 赤<20）で表示。
- アイコンは Windows のライト/ダークテーマを検出（レジストリ `SystemUsesLightTheme`）して縁取り・文字色を反転。
- 右クリックメニューに各サービスの枠ごとの残り%・リセット時刻、「今すぐ更新」「終了」。

## ファイル構成
- `ai_usage_tray.py` … 本体（単一ファイル）。
- `requirements.txt` … pystray, Pillow。
- `config.example.json` / `config.json` … 設定（config.json は .gitignore 済み）。
- `run.bat` … 通常起動（コンソールあり）。
- `start_hidden.vbs` … pythonw でコンソールなし常駐（自動起動向け）。
- `setup.bat` … 依存導入＋動作確認。
- `build_exe.bat` … PyInstaller で exe 化（現状 onedir）。
- `app.ico` … exe 埋め込み用アイコン。

## データ取得方式（重要・調査済みの確定仕様）

### Claude Code — 公式 OAuth 使用量 API
- エンドポイント: `GET https://api.anthropic.com/api/oauth/usage`
- 必須ヘッダ:
  - `Authorization: Bearer <accessToken>`
  - `anthropic-beta: oauth-2025-04-20`
  - `User-Agent: claude-code/<version>`（**これが無いと 429 多発**。version は `claude --version` から取得、無ければ "2.0.0"）
  - `Content-Type: application/json`
- 認証情報: `~/.claude/.credentials.json` の `claudeAiOauth.accessToken`（expiresAt は epoch ms）。トークンは Claude Code 利用時に自動更新される。期限切れなら 401 → 起動を促す。
- レスポンス: `five_hour.utilization`(0–100) と `.resets_at`(ISO)、`seven_day.*`、`seven_day_opus/sonnet`。残り% = 100 − utilization。
- レート制限回避のため API 応答を 90 秒キャッシュ（`_claude_cache`）。
- 出典: https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor/issues/202

### Codex — セッションログ直読み（追加インストール不要）
- `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` を新しい順に走査し、最新の `rate_limits` を持つ `token_count` イベントを採用。
- 形式: `payload.rate_limits.primary`(5h) / `.secondary`(週)。各 `used_percent` と、リセットは `resets_in_seconds`（イベント timestamp + 秒）。
- バージョン差に備え reset は `resets_in_seconds` / 相対分 / 絶対時刻(`resets_at` 等) の複数形式に対応済み。
- 出典: https://github.com/xiangz19/codex-ratelimit

### Antigravity — antigravity-usage CLI（npm）
- コマンド: `antigravity-usage --json`（未インストール時はアプリが `npx -y antigravity-usage --json` にフォールバック）。
- ローカルモードは Antigravity の **IDE（エディタ）** が起動していれば自動接続。IDE を使わない場合は `antigravity-usage login`（クラウドモード）が必要。`agy` CLI 単体ではローカルサーバが立たない。
- 実データ形式: `models` は配列。各要素 `label`, `modelId`, `remainingPercentage`(0..1 の割合。1=100%), `resetTime`(ISO), `isAutocompleteOnly`。
- パーサ `_walk_find_models` は JSON を再帰走査して remaining/used + reset を持つオブジェクトを汎用抽出（将来の形式変更に強い）。`remainingPercentage` 等のキー名も対応済み。
- 既定で `isAutocompleteOnly: true` のモデルは除外（`antigravity_show_autocomplete` で表示可）。`antigravity_models` で label/modelId を区切り無視（`_norm`）で部分一致フィルタ。
- 出典: https://github.com/skainguyen1412/antigravity-usage

## Windows 固有の注意（ハマりどころ・対処済み）
- **バッチファイル(.bat)は必ず ASCII のみで書く**。日本語を入れると cp932 コンソールで文字化けし、壊れたバイトをコマンドとして実行してしまう。日本語表示は Python 側に任せる。
- `subprocess` の出力は **UTF-8 + errors="replace"** で読む（`run_cmd`）。既定の cp932 デコードだと `UnicodeDecodeError` でスレッドが落ちる。
- PowerShell の実行ポリシーで `npx.ps1`/`npm.ps1` がブロックされることがある。回避: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`、または cmd を使う／`.cmd` を明示。
- exe 化(凍結)時は `config.json` を **exe と同じフォルダ**から読む（`sys.frozen` 判定で `SCRIPT_DIR = dirname(sys.executable)`）。

## exe 化：解決済み（2026-06-06）
- 原因確定: **Python 3.14 が PyInstaller と非互換**で、起動できない（「このアプリはお使いの PC では実行できません」）exe を生成していた。CPU/アーキは無関係（x64 で正しく生成されていた）。
- 解決: **Python 3.12 の専用 venv でビルド**したら起動した（PE は x64、プロセス常駐を確認済み）。
- 再ビルド手順（`build_exe.bat` がこの流れを自動化済み。`py -3.12` を優先し、無ければ既定 python にフォールバック）:
  ```
  winget install -e --id Python.Python.3.12       # 3.12 が無ければ
  py -3.12 -m venv .venv312
  .venv312\Scripts\python -m pip install -r requirements.txt pyinstaller
  .venv312\Scripts\python -m PyInstaller --onedir --noconsole --clean --noconfirm ^
      --name AIUsageTray --icon app.ico --hidden-import pystray._win32 ai_usage_tray.py
  copy /Y config.json dist\AIUsageTray\config.json
  ```
  → 成果物: `dist\AIUsageTray\AIUsageTray.exe`（onedir。フォルダごと配布。config.json は exe と同階層）。
- 注意: `python -m PyInstaller` のままだと PATH の **3.14 を拾って再発**する。必ず 3.12 venv の python を使うこと（`build_exe.bat` は対応済み）。
- `.venv312/` はビルド専用。`.gitignore` で除外推奨。
- 代替の常駐手段として **`start_hidden.vbs`（pythonw）** も引き続き有効。

## 動作確認の早道
- `python ai_usage_tray.py --once` … 1 回だけ取得してテキスト表示。
- `python ai_usage_tray.py --probe` … 各データソースの生データ・検出パス・正規化結果を表示（exe は noconsole なので診断は .py で）。

## 検証状況
- Claude/Codex/Antigravity の各パーサはユーザー実データ・模擬データで個別検証済み（Claude 49%/23%、Codex 5h/週、Antigravity 実 JSON で 13→9 モデル、フィルタ動作）。
- exe 化も完了（Python 3.12 ビルドで起動・常駐を確認）。主要タスクは全て完了。
