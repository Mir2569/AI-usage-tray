# AI Usage Tray

Claude Code / Codex / Antigravity の残り使用量を、Windows のタスクトレイ（通知領域）にまとめて常駐表示するアプリです。

トレイの丸アイコンは「一番余裕のない枠の残り%」を数字と色（緑→黄→赤）で表示し、ホバーで各ツールの概要、右クリックで枠ごとの残り%・リセット時刻の一覧が出ます。

---

## 使い方（exe 版・推奨）

`build_exe.bat` でビルドした `dist\AIUsageTray\AIUsageTray.exe` を**ダブルクリック**するだけ。コンソール（ターミナル）は出ず、トレイにアイコンが常駐します。情報取得時も裏で CLI を呼びますが、黒いコンソール窓は出ません。

> 配布・移動するときは **`dist\AIUsageTray\` フォルダごと**扱ってください（exe 単体では動かない onedir 構成です）。`config.json` は exe と同じフォルダに置きます（無くても既定値で動作）。

ソースから直接動かす場合:

```bat
python ai_usage_tray.py            # トレイ常駐で起動
python ai_usage_tray.py --once     # 1回だけ取得してテキスト表示（テスト用）
python ai_usage_tray.py --probe    # 各データソースの生データ・検出パス・正規化結果（診断用）
```

---

## 仕組み（どこからデータを取るか）

| ツール | 取得元 | 取れる内容 |
|---|---|---|
| **Claude Code** | 公式 OAuth usage API（`api.anthropic.com/api/oauth/usage`） | 5時間枠・週枠の使用%とリセット時刻（公式値）|
| **Codex** | `~/.codex/sessions` のセッションログを直接読む | 5時間枠・週枠の使用%とリセット時刻（公式値）|
| **Antigravity** | `antigravity-usage`（npm）の `--json` 出力 | 各モデルの残り%とリセット時刻（公式値）|

3ツールとも残り%が公式に取れます。

- **Claude**: `~/.claude/.credentials.json` の OAuth アクセストークンを使って公式 API を叩きます。トークンは Claude Code を使うと自動更新されます。期限切れなら一度 Claude Code を起動すれば直ります。
- **Codex**: 追加インストール不要。Codex で一度メッセージを送るとセッションログが作られ、そこから読みます。
- **Antigravity**: `antigravity-usage`（npm）が必要。未導入なら自動で `npx -y antigravity-usage` にフォールバックします。Antigravity の **IDE が起動していれば**ローカル接続で取得できます。

---

## 必要なもの

1. **Python 3.9 以上**（ソースから動かす場合）
2. **Node.js / npm**（Antigravity の取得に必要。Claude は API 直、Codex はログ直読みなので不要）

> **exe をビルドするときは Python 3.12 が必要**です（後述）。

---

## EXE 化（ターミナルを出さない単体アプリにする）

**`build_exe.bat` をダブルクリック**するだけ。`dist\AIUsageTray\AIUsageTray.exe` が生成されます。

仕組み: スクリプトは **Python 3.12 の専用 venv（`.venv312`）** を作ってビルドします。

> ⚠ **Python 3.14 ではビルドした exe が起動しません**（「このアプリはお使いの PC では実行できません」）。3.14 は PyInstaller と非互換です。`build_exe.bat` は `py -3.12` を優先して使うので、3.12 を入れておいてください:
> ```bat
> winget install -e --id Python.Python.3.12
> ```

メモ:
- 成果物は **onedir 構成**（`dist\AIUsageTray\` フォルダ）。フォルダごと配布・移動してください。
- `config.json` は exe と同じ階層に置きます（`build_exe.bat` が自動でコピーします）。
- exe はコンソールを出さないので `--once` / `--probe` の文字は見えません。診断は `python ai_usage_tray.py --probe` を使ってください。

---

## 自動起動（PC起動時に常駐）

エクスプローラーのアドレス欄に `shell:startup` と入力して Enter（スタートアップフォルダが開きます）。そこへショートカットを置きます。

- **exe 版（おすすめ）**: `dist\AIUsageTray\AIUsageTray.exe` を右クリック →「ショートカットの作成」→ スタートアップフォルダへ移動。
- **Python 版**: `start_hidden.vbs` のショートカットをスタートアップフォルダへ。`pythonw` でコンソールを出さずに常駐します。

次回ログオンから自動でトレイに表示されます。

---

## 設定（任意）

`config.example.json` を **`config.json`** という名前でコピーして編集すると挙動を変えられます（exe 版は exe と同じフォルダの config.json を読みます）。

- `refresh_seconds`: 自動更新間隔（秒）。既定5分。
- `codex_max_days`: Codex セッションログをさかのぼって探す日数。既定10日。
- `enabled`: 表示するツールだけ true。
- `antigravity_show_autocomplete`: オートコンプリート専用モデルも表示するか（既定 false）。Antigravity のモデルは残量・リセット時刻が一致する**共通枠**ごとに自動でまとめて1行表示されます（例 `Gemini 3 (共通枠)` / `Claude / GPT-OSS (共通枠)`）。
- `paths.antigravity_usage`: `antigravity-usage` を自動検出できない場合に実行ファイルのフルパスを指定。

---

## ⚠ npm install が通らないとき（Antigravity 用）

**グローバルインストールは必須ではありません。** 見つからなければ自動で `npx` 経由に切り替えます（初回だけ少し遅いだけ）。

それでも入れたい／npm 自体が反応しない場合:

1. **`npm` が「コマンドが見つかりません」** → Node.js 未導入か PATH 未設定。https://nodejs.org の LTS を入れ、ターミナルを開き直して `node -v` / `npm -v` を確認。
2. **`EACCES` / 権限エラー** → 管理者ターミナルで再実行。または `npm config set prefix %APPDATA%\npm` でユーザー領域に変更し、`%APPDATA%\npm` を PATH へ追加。
3. **`ENOENT` / `EPERM` / ファイルロック** → ウイルス対策が書き込みをブロックしている可能性。除外設定にするか `npm cache clean --force` 後に再実行。
4. **プロキシでタイムアウト** → `npm config set proxy http://プロキシ:ポート` と `https-proxy` を設定。
5. **PowerShell で `npx.ps1` がブロックされる** → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`、または `.cmd` を明示。

---

## うまく出ないとき（診断）

```bat
python ai_usage_tray.py --probe
```

各データソースの生出力・検出パス・正規化結果をまとめて表示します。

- **Claude が出ない** → `~/.claude/.credentials.json` が無い／トークン期限切れ。Claude Code に一度ログイン／起動すれば直ります。
- **Codex が出ない** → Codex で一度メッセージを送るとセッションログが作られます。
- **Codex の値が古く見える** → Codex はセッションログの `rate_limits` 由来です。Codex 側が新しい `rate_limits` を書くまで値自体は変わりません。トレイメニューや `--probe` の `Codexデータ` / `ログ更新` を見て、採用データの鮮度を確認してください。
- **Antigravity が出ない** → Antigravity の IDE を一度起動してから再取得（ローカルサーバが立ちます）。

---

## メニュー操作

- トレイアイコンを右クリック → 各ツールの残り%・リセット時刻
- 「今すぐ更新」: 即時再取得
- 「終了」: 常駐を終了

---

## ファイル構成

- `ai_usage_tray.py` … 本体（単一ファイル）
- `requirements.txt` … pystray, Pillow
- `config.example.json` / `config.json` … 設定（config.json は .gitignore 済み）
- `run.bat` … 通常起動（コンソールあり）
- `start_hidden.vbs` … pythonw でコンソールなし常駐（自動起動向け）
- `setup.bat` … 依存導入＋動作確認
- `build_exe.bat` … PyInstaller で exe 化（Python 3.12 / onedir）
- `app.ico` … exe 埋め込み用アイコン
- `CLAUDE.md` … 開発・引き継ぎメモ（設計と確定仕様）

---

## ライセンス

MIT License です。詳細は `LICENSE` を参照してください。
