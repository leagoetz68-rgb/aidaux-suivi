@echo off
title Aid'aux suivi - Desactiver le demarrage automatique
powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('Startup')+'\Aidaux Serveur.lnk') -ErrorAction SilentlyContinue"
echo Demarrage automatique desactive.
pause
