@echo off
title Instalando o sistema da loja
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalador\instalar.ps1"
if errorlevel 1 (
  echo.
  echo A instalacao NAO terminou. Leia a mensagem acima.
)
echo.
pause
