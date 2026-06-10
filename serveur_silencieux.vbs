' serveur_silencieux.vbs — Démarre le serveur Aid'aux en arrière-plan (sans fenêtre).
' Utilisé par le démarrage automatique de Windows.

Dim dossier
dossier = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim shell
Set shell = CreateObject("WScript.Shell")

' pythonw = pas de fenêtre console ; 0 = caché
shell.Run "cmd /c cd /d """ & dossier & """ && pythonw serveur.py", 0, False
