@echo off
rem Abre o sistema direto desta pasta, com uma janela de mensagens (para testes).
rem Para o uso no dia a dia, instale com INSTALAR.bat e use o atalho "Sistema da Loja".
cd /d "%~dp0"
python -m loja
pause
