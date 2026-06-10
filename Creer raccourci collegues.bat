@echo off
chcp 65001 >nul
title Aid'aux suivi - Creer le raccourci pour les collegues
cd /d "%~dp0"
python creer_raccourci_collegues.py
echo.
pause
