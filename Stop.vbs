Option Explicit
Dim shell, fs, folder, python, script
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
python = folder & "\.venv\Scripts\pythonw.exe"
script = folder & "\src\pet_base.py"
If Not fs.FileExists(python) Then WScript.Quit 1
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & script & Chr(34) & " --stop", 0, False
