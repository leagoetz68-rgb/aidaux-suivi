@echo off
chcp 65001 >nul
title Aid'aux suivi - Adresse du serveur
cd /d "%~dp0"
python -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); ip=s.getsockname()[0]; s.close(); print(); print('  Adresse a donner aux collegues :'); print('     http://'+ip+':5000'); print(); print('  Sur ce PC : http://localhost:5000'); print()"
pause
