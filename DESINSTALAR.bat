@echo off
title Removendo o sistema da loja
cd /d "%~dp0"
echo Isto remove o programa e os atalhos. Seus dados e backups sao mantidos.
choice /c SN /m "Deseja continuar"
if errorlevel 2 exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalador\desinstalar.ps1"
echo.
pause
