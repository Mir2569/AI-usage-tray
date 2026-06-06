' AI Usage Tray をコンソール画面なしで起動する(自動起動用)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = scriptDir
' pythonw でウィンドウを出さずに常駐起動
sh.Run "pythonw.exe """ & scriptDir & "\ai_usage_tray.py""", 0, False
