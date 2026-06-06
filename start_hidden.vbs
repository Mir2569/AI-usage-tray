' Start AI Usage Tray without console window (for startup)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = scriptDir

Dim pythonwPath
pythonwPath = "pythonw.exe"

' Check if virtual environments exist and use their pythonw.exe
If fso.FileExists(scriptDir & "\.venv312\Scripts\pythonw.exe") Then
    pythonwPath = """" & scriptDir & "\.venv312\Scripts\pythonw.exe"""
ElseIf fso.FileExists(scriptDir & "\.venv\Scripts\pythonw.exe") Then
    pythonwPath = """" & scriptDir & "\.venv\Scripts\pythonw.exe"""
End If

sh.Run pythonwPath & " """ & scriptDir & "\ai_usage_tray.py""", 0, False
