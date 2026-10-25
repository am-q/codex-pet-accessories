Option Explicit
Dim shell, fs, folder, python, script, data, flag
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
python = folder & "\.venv\Scripts\pythonw.exe"
script = folder & "\src\pet_base.py"
If Not fs.FileExists(python) Then
    MsgBox "Run Install.ps1 first. See README.md for setup instructions.", 48, "Codex Pet Accessories"
    WScript.Quit 1
End If
data = shell.Environment("Process")("CODEX_PET_DATA_DIR")
If data = "" Then data = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\CodexPetAccessories"
flag = data & "\stop.flag"
If fs.FileExists(flag) Then fs.DeleteFile flag
shell.CurrentDirectory = folder
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & script & Chr(34), 0, False
