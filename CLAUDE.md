# AI Usage Tray — 引き継ぎ／開発メモ

Claude Code / Codex / Antigravity の残り使用量を Windows のタスクトレイにまとめて常駐表示する Python アプリ。
このファイルは作業を引き継ぐ人（および Claude Code）向けの設計・仕様・既知の課題メモ。

## AI エージェント向け共通ルール

作業開始時の Git 確認、秘密情報の扱い、検証コマンド、PR/Issue 運用は `AGENTS.md` を参照してください。
この `CLAUDE.md` は、調査済み仕様や実装上の注意を残す引き継ぎメモとして扱います。

## 何をするアプリか
- バックグラウンドスレッドで既定 5 分ごと（`config.json` の `refresh_seconds`）に 3 サービスの残量を取得。
- トレイアイコンに「最も余裕のない枠の残り%」を数字＋色（緑≥50 / 黄≥20 / 赤<20）で表示。
- アイコンは Windows のライト/ダークテーマを検出（レジストリ `SystemUsesLightTheme`）して縁取り・文字色を反転。
- 右クリックメニューに各サービスの枠ごとの残り%・リセット時刻、「今すぐ更新」「終了」。

## ファイル構成
- `ai_usage_tray.py` … 薄いランチャ（`from ai_usage_tray.__main__ import main`）。配布・起動スクリプトのエントリ参照を維持するための入口。
- `ai_usage_tray/` … 本体パッケージ（Issue #55 で責務ごとに分割）。
  - `__main__.py`（CLI/argparse）, `config.py`（既定設定・load/凍結パス）, `redact.py`（秘匿・マスク）, `utils.py`（日時整形・`run_cmd`/`resolve_cmd`）, `state.py`（共有ロック/キャッシュ）, `wsl.py`（WSL ヘルパー）, `collect.py`（集約・`summarize_text`）, `tray.py`（トレイ UI）, `gui.py`（設定ダイアログ）, `probe.py`（診断）, `constants.py`。
  - `providers/`（`codex.py` / `claude.py` / `antigravity.py` / `types.py`、`PROVIDERS` レジストリは `__init__.py`）。
  - **凍結/非凍結の config パス**: `config.py` の `SCRIPT_DIR` は凍結時 `dirname(sys.executable)`、非凍結時 **パッケージの親**（`dirname(dirname(__file__))`）= リポジトリ/配布ルート。`config.json` は常にランチャ/exe と同階層から読む。
  - **設定再起動**: `tray.py` は `__file__` ではなく `sys.argv[0]` を再実行する（ランチャ/`-m` 両対応）。
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
- `isAutocompleteOnly: true` のモデルは**常に除外**（Issue #63 で `antigravity_show_autocomplete` 設定・GUI チェックボックスを撤去。共通枠化で独立行を持たず、枠の代表値=残量最小を不必要に押し下げるのを避けるため固定除外）。古い config の残存キーは無害に無視。
- **共通枠の集約（Issue #20 → #64 で固定2枠化）**: Antigravity の枠は実データ上 Gemini 系 / Claude+GPT-OSS 系の2枠。モデル名のファミリ（`ANTIGRAVITY_POOLS` のキーワード `gemini` / `claude`,`gpt`）で常にこの2枠へ分けて集約する（`_antigravity_pool_of`）。**両枠の remaining%・resetTime がたまたま一致しても1行に潰さない**。表示順は `ANTIGRAVITY_POOLS` の定義順に固定（`Gemini (共通枠)` を上段、`Claude / GPT-OSS (共通枠)` を下段）し、Antigravity だけは残量昇順ソートを行わない。各枠の代表値は枠内で残量最小（最も余裕のない）モデル。既知ファミリに該当しないモデルは末尾に残量昇順で個別表示。
  - 旧実装は `(remaining_pct, reset_at)` 一致でグループ化＋共通接頭辞ラベル付けだったが、値が揃うと全モデルが1行（例 `Claude / Gemini / GPT-OSS (共通枠)`）に潰れて枠の区別が消える問題があったため、ファミリ固定方式へ変更した。
- 旧 `antigravity_models`（モデル部分一致フィルタ）は共通枠化により無意味なため **撤去済み**（設定 GUI・DEFAULT_CONFIG から削除。古い config の残存キーは無害に無視）。
- 出典: https://github.com/skainguyen1412/antigravity-usage

### WSL データソース切替（Issue #51 / PR #52）
- provider ごとに WSL 側の認証情報・セッションログ・CLI を参照できる。設定 `wsl.distro`（空欄=既定 distro）と `wsl.enabled.{claude,codex,antigravity}`（既定すべて `false`）。**既定では従来どおり Windows 側を使う**ため、設定しない限り挙動は変わらない。型不一致や非 dict はデフォルトへフォールバック（`_provider_uses_wsl` 等が防御）。
- 実行は `wsl.exe` 経由（`build_wsl_cmd` → `run_wsl_sh`/`run_wsl_cmd`）。`shell=False`・`CREATE_NO_WINDOW`・UTF-8 `errors="replace"` は Windows 経路と共通の `run_cmd` を通すため維持。distro・コマンドは独立 argv で渡し、スクリプト埋め込みのパス/パッケージ名は `_shell_quote` でエスケープ。
- **停止中 distro を自動起動しない**: 各 provider は実行前に `_wsl_running_status`（`wsl --list --running --quiet`）でガードし、未起動なら `wsl -d <distro>` を促すメッセージで早期終了する。`wsl.distro` 空欄時は `wsl -l -v` の `*` から既定 distro 名を解決して照合。
- **WSL 側に `python3` が必須**: Codex 解析・Claude credentials 読取・存在確認は WSL 内 `python3` を使う。未導入時は専用メッセージ（`_wsl_linux_command_exists` で事前判定）。
- **Windows shim の誤実行回避**: WSL は Windows PATH を interop 継承するため、`_wsl_linux_command_path` が `command -v` の結果 `/mnt/<drive>/...` を除外。`claude --version` / `antigravity-usage` / `npx` すべてこの経路に統一し、interop 経由で Windows バイナリを掴まない。
- Codex: WSL 内 `python3 -c` のインラインスクリプトで `~/.codex/sessions` を走査し、非機密な `rate_limits` のみ JSON で Windows 側へ返す（`find_latest_codex_event_wsl`。spawn は 1 回）。
- Claude: WSL 側 `~/.claude/.credentials.json` を `python3` で読む。無ければ env トークンへフォールバックするが、`~/.profile` を source する方式のため **`~/.bashrc` だけの export は参照されない**。キャッシュは `source`（`Windows`/`WSL:<distro>`）で分離し混線を防ぐ。
- Antigravity: WSL 側 Linux 版 `antigravity-usage --json`。`antigravity_npx_fallback: true` で WSL 側 `npx -y antigravity-usage@<版> --json` にフォールバック。
- パスマスク: `mask_path` に `/home/<user>` と `/mnt/<drive>/Users/<user>` のマスクを追加済み（`--probe` 出力の共有対策）。
- 既知の任意改善（low）: spawn 回数のメモ化（Issue #53）、`wsl --list` の UTF-16LE 明示デコードで非 ASCII distro 名対応（Issue #54）。
- 出典: PR https://github.com/Mir2569/ai-usage-tray/pull/52

## Windows 固有の注意（ハマりどころ・対処済み）
- **バッチファイル(.bat)は必ず ASCII のみで書く**。日本語を入れると cp932 コンソールで文字化けし、壊れたバイトをコマンドとして実行してしまう。日本語表示は Python 側に任せる。
- **`.bat` の `echo` 内の `>` は必ず `^>` でエスケープする**。`echo Done -> dist\...\AIUsageTray.exe` のように書くと `>` がリダイレクトとして解釈され、**できたての exe を echo の文字列で上書き**してしまう（11 バイトの壊れた exe →「アプリが使用できません」）。Python バージョンは無関係なので注意（2026-06-06 に build_exe.bat で実際に踏んだ）。
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
  .venv312\Scripts\python -m pip install -r requirements-build.txt   # pip/pyinstaller を固定（再現性）
  .venv312\Scripts\python -m pip install -r requirements.txt
  .venv312\Scripts\python -m PyInstaller --onedir --noconsole --clean --noconfirm ^
      --name AIUsageTray --icon app.ico --hidden-import pystray._win32 ^
      --collect-submodules ai_usage_tray ai_usage_tray.py
  copy /Y config.json dist\AIUsageTray\config.json
  ```
  → 成果物: `dist\AIUsageTray\AIUsageTray.exe`（onedir。フォルダごと配布。config.json は exe と同階層）。
  - エントリは薄いランチャ `ai_usage_tray.py` のまま。本体は `ai_usage_tray/` パッケージへ静的 import されるが、取りこぼし保険として `--collect-submodules ai_usage_tray`（`AIUsageTray.spec` では `collect_submodules('ai_usage_tray')`）を付ける。
- 注意: `python -m PyInstaller` のままだと PATH の **3.14 を拾って再発**する。必ず 3.12 venv の python を使うこと（`build_exe.bat` は対応済み）。
- `.venv312/` はビルド専用。`.gitignore` で除外推奨。
- 代替の常駐手段として **`start_hidden.vbs`（pythonw）** も引き続き有効。

## 動作確認の早道
- `python ai_usage_tray.py --once` … 1 回だけ取得してテキスト表示。
- `python ai_usage_tray.py --probe` … 各データソースの生データ・検出パス・正規化結果を表示（exe は noconsole なので診断は .py で）。

## 検証状況
- Claude/Codex/Antigravity の各パーサはユーザー実データ・模擬データで個別検証済み（Claude 49%/23%、Codex 5h/週、Antigravity 実 JSON で 13→9 モデル、フィルタ動作）。
- exe 化も完了（Python 3.12 ビルドで起動・常駐を確認）。主要タスクは全て完了。
- WSL データソース切替（#51 / PR #52）を追加。Windows 既定設定と WSL Ubuntu 24.04 設定の `--probe`/`--once` で確認済み（Antigravity は `antigravity-usage 0.2.9` で取得成功。Claude/Codex は token/session 不在環境のため provider エラー表示まで確認）。
- **モジュール分割（Issue #55）完了**: 単一ファイル（約 2,004 行）を `ai_usage_tray/` パッケージへ責務ごとに分割。薄いランチャ `ai_usage_tray.py` を残し配布・起動スクリプトは無改修。`compileall` / `--once` / `--probe`（ランチャ・`-m` 両経路）/ PyInstaller onedir ビルド + 凍結 exe 常駐を確認済み。
