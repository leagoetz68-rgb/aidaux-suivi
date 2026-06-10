@echo off
chcp 65001 >nul
title Aid'aux suivi - Activer le demarrage automatique
cd /d "%~dp0"
echo Activation du demarrage automatique du serveur Aid'aux...
echo.
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut([Environment]::GetFolderPath('Startup')+'\Aidaux Serveur.lnk'); $lnk.TargetPath='%~dp0serveur_silencieux.vbs'; $lnk.WorkingDirectory='%~dp0'; $lnk.IconLocation='%~dp0static\icon.ico'; $lnk.Save()"
echo.
echo ==========================================================
echo  Demarrage automatique ACTIVE.
echo  Le serveur se lancera tout seul au demarrage de Windows.
echo.
echo  (Pour le lancer maintenant sans redemarrer, double-cliquez
echo   sur "Demarrer le serveur (bureau).bat")
echo ==========================================================
pause
