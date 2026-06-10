@echo off
title Aid'aux suivi - Installation des librairies
cd /d "%~dp0"
echo Installation des librairies necessaires...
echo.
python -m pip install -r requirements.txt
echo.
echo ============================================
echo  Installation terminee.
echo  Vous pouvez maintenant demarrer le serveur.
echo ============================================
pause
