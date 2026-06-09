---
name: github-release
description: AI Usage Tray で GitHub Releases にバイナリ配布を追加するときに使う。タグ命名（vX.Y.Z）、Python 3.12 venv での PyInstaller onedir ビルド、config.json 非同梱、AIUsageTray-vX.Y.Z-windows-x64.zip の添付、絵文字なしのリリースノート書式を含む。
---

# GitHub Release Skill

## 使う場面

GitHub Releases へバイナリ配布（exe の zip）を追加するときに使います。
リリースノートは日本語で、既存リリース（v1.0.0 / v1.1.0 / v1.2.0）の形式に合わせます。

## 基本方針

- タグは `vX.Y.Z`（SemVer）。`main` の最新コミットを対象にする。
- **個人の `config.json` をリリースに同梱しない**（WSL distro 名などローカル設定が漏れる）。
- exe は **Python 3.12 専用 venv** でビルドする（**3.14 は不可**。起動しない exe ができる）。
- リリースノートに絵文字は使わず、既存リリースと同じ構成にする。
- 公開はユーザーの確認・依頼に基づいて行う。

## バージョン番号

- MAJOR: 互換性を壊す変更 / MINOR: 後方互換の新機能 / PATCH: 後方互換の不具合修正。
- 直前リリースからの変更を確認する。

```powershell
git tag --sort=-v:refname
git log v<直前>..main --oneline --merges
```

## exe ビルド

`build_exe.bat` と同じ手順を踏みます。`.bat` は末尾に `pause` があり非対話実行ではハングするため、エージェントが回す場合は手順を直接実行します。

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
.\.venv312\Scripts\python.exe -m PyInstaller --onedir --noconsole --clean --noconfirm `
  --name AIUsageTray --icon app.ico --hidden-import pystray._win32 `
  --collect-submodules ai_usage_tray ai_usage_tray.py
Copy-Item -Force app.ico dist\AIUsageTray\app.ico   # 設定ウィンドウのアイコン用
```

- `dist\AIUsageTray\` が成果物（onedir）。`AIUsageTray.exe` を起動して常駐することを確認してから配布する。
- **個人の `config.json` は同梱しない**。`build_exe.bat` はローカル用に config.json をコピーするが、リリース zip には含めない。`app.ico` は exe 同階層へ同梱する。
- `*.spec`・`build/`・`dist/`・`.venv312/`・`AIUsageTray-*.zip` は追跡しない（gitignore 済み）。

## zip 化と公開

成果物を `AIUsageTray-vX.Y.Z-windows-x64.zip` にまとめ、`gh release create` で添付します。

```powershell
Compress-Archive -Path "dist\AIUsageTray\*" -DestinationPath "AIUsageTray-vX.Y.Z-windows-x64.zip" -CompressionLevel Optimal
# zip に config.json が混ざっていないか確認してから公開する
gh release create vX.Y.Z --target main --title "vX.Y.Z — 要約" `
  --notes-file scratch\release_notes.md "AIUsageTray-vX.Y.Z-windows-x64.zip"
```

## リリースノートの書式

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

## 公開後チェック

```powershell
gh release view vX.Y.Z --json tagName,name,isDraft,assets
```

- 添付が `AIUsageTray-vX.Y.Z-windows-x64.zip` であること、`config.json` が混ざっていないこと、最新（Latest）になっていることを確認します。
