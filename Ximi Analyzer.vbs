Dim dossier
dossier = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim shell
Set shell = CreateObject("WScript.Shell")

' Lancer l'application dans sa fenêtre native (serveur Flask intégré).
' Fenêtre console cachée (0) ; pythonw évite toute fenêtre noire.
shell.Run "cmd /c cd /d """ & dossier & """ && pythonw desktop.py", 0, False
