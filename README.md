# AI Usage Tray

Claude Code / Codex / Antigravity の残り使用量を、Windows のタスクトレイ（通知領域）にまとめて常駐表示するアプリです。

トレイの丸アイコンは「一番余裕のない枠の残り%」を数字と色（緑→黄→赤）で表示し、ホバーで各ツールの概要、右クリックで枠ごとの残り%・リセット時刻の一覧が出ます。配色は設定から**色弱対応モード（青→黄→赤）**にも切り替えられます（後述）。

---

## 使い方（exe 版・推奨）

`build_exe.bat` でビルドした `dist\AIUsageTray\AIUsageTray.exe` を**ダブルクリック**するだけ。コンソール（ターミナル）は出ず、トレイにアイコンが常駐します。情報取得時も裏で CLI を呼びますが、黒いコンソール窓は出ません。

> 配布・移動するときは **`dist\AIUsageTray\` フォルダごと**扱ってください（exe 単体では動かない onedir 構成です）。`config.json` は exe と同じフォルダに置きます（無くても既定値で動作）。

**初回起動時**（`config.json` が無いとき）は、トレイ常駐の前に設定ダイアログが自動で開きます。使うプロバイダ・更新間隔・WSL データソース・配色モードを選んで「保存」すると、その内容で `config.json` が作成されて常駐が始まります。「キャンセル」で閉じると既定設定のまま常駐し、次回起動でまた表示されます（詳細は後述の「[設定（任意）](#設定任意)」を参照）。

ソースから直接動かす場合:

```bat
python ai_usage_tray.py            # トレイ常駐で起動
python ai_usage_tray.py --once     # 1回だけ取得してテキスト表示（テスト用）
python ai_usage_tray.py --probe    # 検出パス・正規化結果（診断用。外部CLIの生出力は非表示）
python ai_usage_tray.py --probe-raw # 上記に加えて外部CLIの生出力も表示（redact 済み）
```

> ⚠ `--probe` / `--probe-raw` の出力を Issue や PR に貼る前に、トークン・メール・ローカルパス等が残っていないか必ず確認してください。生出力は既定で非表示で、`--probe-raw` 指定時のみ機密キーを伏せた上で表示されます。

---

## 仕組み（どこからデータを取るか）

| ツール | 取得元 | 取れる内容 |
|---|---|---|
| **Claude Code** | 公式 OAuth usage API（`api.anthropic.com/api/oauth/usage`） | 5時間枠・週枠の使用%とリセット時刻（公式値）|
| **Codex** | `~/.codex/sessions` のセッションログを直接読む | 5時間枠・週枠の使用%とリセット時刻（公式値）|
| **Antigravity** | `antigravity-usage`（npm）の `--json` 出力 | 各モデルの残り%とリセット時刻（公式値）|

3ツールとも残り%が公式に取れます。

---

## 色と残量の見方

アイコンの色は「一番余裕のない枠の残り%」のしきい値で決まります。設定の**配色モード**で 2 種類から選べます（既定は標準）。文字色は地色の明るさに応じて自動で白／黒になります。

| 残り% | 標準モード（`classic`） | 色弱対応モード（`colorblind`） |
|---|---|---|
| 50%以上 | 緑 | 青 |
| 20〜49% | 黄 | 黄 |
| 20%未満 | 赤 | 赤 |
| 取得不可 | 灰 | 灰 |

色弱対応モードは、緑と赤が見分けづらい場合に緑を青へ置き換えるモードです。配色は「設定...」→「アイコン表示」で切り替えられ、保存するとすぐ反映されます（`config.json` の `icon_color_mode` でも指定可）。この対応表は右クリックの「ヘルプ」からも確認できます。

- **Claude**: `~/.claude/.credentials.json` の OAuth アクセストークンを使って公式 API を叩きます。トークンは Claude Code を使うと自動更新されます。期限切れなら一度 Claude Code を起動すれば直ります。
- **Codex**: 追加インストール不要。Codex で一度メッセージを送るとセッションログが作られ、そこから読みます。
- **Antigravity**: `antigravity-usage`（npm）が必要。**既定では未導入時に何もしません**（`npm i -g antigravity-usage` での導入を推奨）。`config.json` で `antigravity_npx_fallback: true` にすると、未導入時に `npx -y antigravity-usage@<版>` で取得します（後述の注意あり）。Antigravity の **IDE が起動していれば**ローカル接続で取得できます。

> ### 💡 WSL でも使えます
> WSL（Windows Subsystem for Linux）上で Claude Code / Codex / Antigravity を使っている場合は、provider ごとに **WSL 側の認証情報・セッションログ・CLI を参照して計測**できます。Windows 側と WSL 側を provider 単位で混在させることも可能です。
> 設定を追加しない限り従来どおり Windows 側のデータソースを使うので、既存の動作は変わりません。
> 設定方法と distro の記載例は下記「[WSL のデータソースを使う](#wsl-のデータソースを使う)」を参照してください。

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
- exe はコンソールを出さないので `--once` / `--probe` の文字は見えません。診断は `python ai_usage_tray.py --probe`（生出力も要るなら `--probe-raw`）を使ってください。

---

## 自動起動（PC起動時に常駐）

エクスプローラーのアドレス欄に `shell:startup` と入力して Enter（スタートアップフォルダが開きます）。そこへショートカットを置きます。

- **exe 版（おすすめ）**: `dist\AIUsageTray\AIUsageTray.exe` を右クリック →「ショートカットの作成」→ スタートアップフォルダへ移動。
- **Python 版**: `start_hidden.vbs` のショートカットをスタートアップフォルダへ。`pythonw` でコンソールを出さずに常駐します。

次回ログオンから自動でトレイに表示されます。

---

## 設定（任意）

`config.example.json` を **`config.json`** という名前でコピーして編集すると挙動を変えられます（exe 版は exe と同じフォルダの config.json を読みます）。

> **初回起動時**は `config.json` が無いと、トレイ常駐の前に設定ダイアログが自動で開きます。プロバイダの有効化・更新間隔・WSL データソース・配色モードを選んで「保存」すると、その内容で `config.json` が作成されて常駐が始まります。「キャンセル」や × で閉じると既定設定のまま常駐し、次回起動でまた設定ダイアログが開きます。`--once` / `--probe` / `--settings` などの実行では自動表示しません。

- `refresh_seconds`: 自動更新間隔（秒）。既定5分。
- `codex_max_days`: Codex セッションログをさかのぼって探す日数。既定10日。
- `enabled`: 表示するツールだけ true。
- `icon_color_mode`: アイコンの配色モード。`"classic"`（緑→黄→赤・既定）/ `"colorblind"`（青→黄→赤）。緑と赤が見分けづらい場合は `"colorblind"` を選びます。「設定...」→「アイコン表示」からも変更できます。
- Antigravity のモデルはファミリ単位の**共通枠**に自動でまとめて表示されます。`Gemini (共通枠)` を上段、`Claude / GPT-OSS (共通枠)` を下段に固定し、オートコンプリート専用モデルは常に除外します（表示行には現れないため、旧 `antigravity_show_autocomplete` 設定は撤去しました）。
- `antigravity_npx_fallback`: `antigravity-usage` が未検出のとき `npx` 経由で取得するか（**既定 false = opt-in**）。⚠ 有効にすると、常駐アプリがバックグラウンドで（既定5分ごとや初回・キャッシュ切れ時に）**npm からパッケージを取得・実行**します。気になる場合は無効のまま `npm i -g antigravity-usage` で導入するか、`paths.antigravity_usage` で実行ファイルを明示してください。
- `antigravity_usage_version`: 上記 npx フォールバック時に使う固定バージョン（既定 `"0.2.9"`）。空文字にすると無印（最新）になりますが、サプライチェーンの観点から**非推奨**です。
- `wsl.distro`: WSL のディストリビューション名。空文字なら Windows 側 `wsl.exe` の既定ディストリビューションを使います。設定ダイアログでは検出済み distro を候補から選べますが、空欄や候補外の手入力も可能です。既定は `wsl -l -v` で `*` が付いている distro です（例: `"Ubuntu-24.04"`）。解決できる場合、メニューや診断の `WSL:` 表示には実際の distro 名が出ます。
- `wsl.enabled`: provider ごとに WSL 側のデータソースを使うか。`claude` は WSL 側 `~/.claude/.credentials.json`、`codex` は WSL 側 `~/.codex/sessions`、`antigravity` は WSL 側の Linux コマンドとして実行できる `antigravity-usage --json` を使います。
- `paths.antigravity_usage`: `antigravity-usage` を自動検出できない場合に実行ファイルのフルパスを指定。

### WSL のデータソースを使う

WSL 上で動かしている Claude Code / Codex / Antigravity も計測できます。`wsl.enabled` を provider ごとに `true` にすると、その provider だけ WSL 側の認証情報・セッションログ・CLI を参照します（`true` にしない provider は従来どおり Windows 側）。対象ディストリビューションは `wsl.distro` で指定します（空欄なら既定 distro）。設定ダイアログでは検出済み distro をドロップダウン候補から選べます。

distro 名は環境ごとに異なります。インストール済みの名前は **`wsl -l -v`** で確認できます（`*` が付いているのが既定 distro）:

```text
  NAME            STATE           VERSION
* Ubuntu-24.04    Running         2
  AlmaLinux-10    Running         2
```

設定例（Ubuntu の場合）:

```json
{
  "wsl": {
    "distro": "Ubuntu-24.04",
    "enabled": { "claude": true, "codex": true, "antigravity": true }
  }
}
```

設定例（別の distro 名を指定する場合 / 例: AlmaLinux）:

```json
{
  "wsl": {
    "distro": "AlmaLinux-10",
    "enabled": { "claude": true, "codex": true, "antigravity": true }
  }
}
```

`distro` を空欄（`""`）にすると、既定 distro（`wsl -l -v` で `*` が付くもの）を使います。複数 distro があり特定の 1 つを使いたいときは、上記のように名前を明示してください。候補に出ない未起動・未列挙の distro 名も、従来どおり手入力できます。

WSL 側を参照する provider では、WSL 側に `python3` が必要です。Ubuntu 24.04 などの標準的な distro では通常インストール済みです。常駐アプリは停止中の WSL distro を自動起動しないため、値が出ない場合は先に `wsl -d Ubuntu-24.04` などで対象 distro を起動してください。

WSL 側で Antigravity を取得する場合も、既定では WSL 側に Linux 版の `antigravity-usage` が必要です。Windows 側 npm の shim ではなく、WSL 内で `npm i -g antigravity-usage` してください。`antigravity_npx_fallback: true` を有効化すると WSL 側の Linux 版 `npx -y antigravity-usage@<版>` にフォールバックします。

Claude の WSL 側トークンは、通常は WSL 側 `~/.claude/.credentials.json` から読みます。環境変数 `CLAUDE_CODE_OAUTH_TOKEN` だけで使う場合は、WSL 側 `~/.profile` に `export CLAUDE_CODE_OAUTH_TOKEN=...` を置いてください。`~/.bashrc` だけに置いた値は取得されません。

---

## ⚠ npm install が通らないとき（Antigravity 用）

**既定ではグローバルインストールが必要です。** `config.json` で `antigravity_npx_fallback: true` にすると、未検出時に `npx -y antigravity-usage@<版>` へフォールバックします（初回だけ少し遅く、npm からの取得・実行が走る点に注意）。

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

検出パス・正規化結果をまとめて表示します。外部 CLI の生出力は既定で非表示で、必要なときだけ `--probe-raw` で（機密キーを伏せた上で）表示できます。**出力を外部共有する前に、トークン・メール・ローカルパス等が含まれていないか確認してください。**

- **Claude が出ない** → `~/.claude/.credentials.json` が無い／トークン期限切れ。Claude Code に一度ログイン／起動すれば直ります。
- **Codex が出ない** → Codex で一度メッセージを送るとセッションログが作られます。
- **Codex の値が古く見える** → Codex はセッションログの `rate_limits` 由来です。Codex 側が新しい `rate_limits` を書くまで値自体は変わりません。トレイメニューや `--probe` の `Codexデータ` / `ログ更新` を見て、採用データの鮮度を確認してください。
- **Antigravity が出ない** → Antigravity の IDE を一度起動してから再取得（ローカルサーバが立ちます）。
- **WSL 側の値が出ない** → 対象 distro が起動しているか、`wsl.distro` の名前、WSL 側の `python3` / `~/.claude/.credentials.json` / `~/.codex/sessions` / `antigravity-usage` の有無を `python ai_usage_tray.py --probe` で確認してください。

---

## メニュー操作

- トレイアイコンを右クリック → 各ツールの残り%・リセット時刻
- 「ヘルプ」: 色と残量の対応表・使い方の要約・GitHub / X（作者）へのリンク
- 「設定...」: プロバイダの有効化、更新間隔、WSL データソース、配色モードなどを変更
- 「今すぐ更新」: 即時再取得
- 「終了」: 常駐を終了

---

## ファイル構成

- `ai_usage_tray.py` … 薄いランチャ（`python ai_usage_tray.py` / `python -m ai_usage_tray` で起動）
- `ai_usage_tray/` … 本体パッケージ（トレイ UI・各 provider・設定・WSL・診断などに分割）
- `requirements.txt` … pystray, Pillow
- `config.example.json` / `config.json` … 設定（config.json は .gitignore 済み）
- `run.bat` … 通常起動（コンソールあり）
- `start_hidden.vbs` … pythonw でコンソールなし常駐（自動起動向け）
- `setup.bat` … 依存導入＋動作確認
- `build_exe.bat` … PyInstaller で exe 化（Python 3.12 / onedir）
- `app.ico` … exe 埋め込み用アイコン
- `CLAUDE.md` … 開発・引き継ぎメモ（設計と確定仕様）

### パッケージ構成（`ai_usage_tray/`）

責務ごとにモジュール分割されています（矢印は import 依存。下の層ほど依存が少ない）。

```mermaid
graph TD
    L["ai_usage_tray.py<br/>薄いランチャ"] --> M["__main__.py<br/>CLI / argparse"]

    subgraph UI["エントリ・UI 層"]
        M --> TRAY["tray.py<br/>トレイ UI・常駐ループ"]
        M --> GUI["gui.py<br/>設定ダイアログ"]
        M --> PROBE["probe.py<br/>診断 (--probe)"]
    end

    subgraph AGG["集約層"]
        COLLECT["collect.py<br/>集約・summarize_text"]
    end

    subgraph PROV["provider 層"]
        PROVIDERS["providers/<br/>claude・codex・antigravity<br/>(types, PROVIDERS)"]
    end

    subgraph BASE["基盤層"]
        WSL["wsl.py<br/>WSL ヘルパー"]
        CONFIG["config.py<br/>設定・凍結パス"]
        STATE["state.py<br/>共有ロック/キャッシュ"]
        UTILS["utils.py<br/>run_cmd・日時整形"]
        REDACT["redact.py<br/>秘匿・マスク"]
        CONST["constants.py<br/>定数"]
    end

    TRAY --> COLLECT
    PROBE --> COLLECT
    M --> COLLECT
    COLLECT --> PROVIDERS
    TRAY --> PROVIDERS
    PROBE --> PROVIDERS
    GUI --> CONFIG
    TRAY --> CONFIG
    PROVIDERS --> WSL
    PROVIDERS --> CONFIG
    PROVIDERS --> STATE
    PROVIDERS --> UTILS
    PROVIDERS --> REDACT
    COLLECT --> STATE
    WSL --> UTILS
    WSL --> REDACT
    REDACT --> CONST
    TRAY --> STATE
    TRAY --> CONST
```

---

## ライセンス

MIT License です。詳細は `LICENSE` を参照してください。
