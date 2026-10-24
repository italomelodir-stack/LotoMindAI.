; Instalador do Sistema da Loja para Windows 10/11 (NSIS 3).
; Não use este arquivo direto: rode  python instalador/construir_instalador.py  (ele monta a pasta com o
; Python e o programa e chama o makensis com as definições abaixo).
;   VERSAO   versão do sistema (ex.: 1.0.0)
;   ORIGEM   pasta montada, com python/, app/, loja.ico e lateral.bmp
;   SAIDA    caminho do .exe gerado
;
; Não precisa de administrador nem de internet. O programa vai para AppData\Local\Programs e os dados
; ficam em AppData\Local\LojaMaterialConstrucao, que este instalador nunca apaga: atualizar é só rodar
; o instalador novo por cima.

Unicode true
ManifestDPIAware true
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

!ifndef VERSAO | ORIGEM | SAIDA
  !error "Use instalador/construir_instalador.py para gerar o instalador."
!endif

!define NOME "Sistema da Loja"
!define ATALHO "Sistema da Loja.lnk"
!define CHAVE "Software\Microsoft\Windows\CurrentVersion\Uninstall\LojaMaterialConstrucao"
!define ABRIR_ARGS "-I -m loja"

Name "${NOME}"
Caption "Instalar o ${NOME} ${VERSAO}"
OutFile "${SAIDA}"
InstallDir "$LOCALAPPDATA\Programs\LojaMaterialConstrucao"
InstallDirRegKey HKCU "${CHAVE}" "InstallLocation"
BrandingText "${NOME} ${VERSAO}"
ShowInstDetails hide
ShowUninstDetails hide

VIProductVersion "${VERSAO}.0"
VIFileVersion "${VERSAO}.0"
VIAddVersionKey /LANG=0 "ProductName" "${NOME}"
VIAddVersionKey /LANG=0 "ProductVersion" "${VERSAO}"
VIAddVersionKey /LANG=0 "FileVersion" "${VERSAO}"
VIAddVersionKey /LANG=0 "FileDescription" "Instalador do ${NOME} (loja de materiais de construção)"
VIAddVersionKey /LANG=0 "LegalCopyright" "${NOME}"

!define MUI_ICON "${ORIGEM}/loja.ico"
!define MUI_UNICON "${ORIGEM}/loja.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "${ORIGEM}/lateral.bmp"
!define MUI_ABORTWARNING
!define MUI_ABORTWARNING_TEXT "Quer mesmo cancelar a instalação?"
!define MUI_WELCOMEPAGE_TITLE "Instalar o ${NOME}"
!define MUI_WELCOMEPAGE_TEXT "Este assistente vai instalar o ${NOME} ${VERSAO} neste computador.$\r$\n$\r$\nNão precisa de internet nem de senha de administrador.$\r$\n$\r$\nOs dados da loja (produtos, clientes, vendas e contas) ficam guardados à parte e não são apagados ao atualizar ou desinstalar. Se o sistema estiver aberto, ele será fechado com backup antes de atualizar.$\r$\n$\r$\nClique em Instalar para continuar."
!define MUI_FINISHPAGE_TITLE "Pronto! O ${NOME} foi instalado."
!define MUI_FINISHPAGE_TEXT "Para abrir, use o atalho $\"${NOME}$\" na área de trabalho ou no menu Iniciar.$\r$\n$\r$\nOs backups automáticos ficam em Documentos\Backup da Loja."
!define MUI_FINISHPAGE_TEXT_LARGE
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o sistema agora"
!define MUI_FINISHPAGE_RUN_FUNCTION AbrirSistema

!define MUI_PAGE_CUSTOMFUNCTION_SHOW TrocarBotaoAvancar
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!define MUI_UNCONFIRMPAGE_TEXT_TOP "O programa será removido deste computador. Os dados da loja e os backups NÃO serão apagados."
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

; Pede para o sistema aberto fechar (ele faz backup antes) e espera o processo terminar.
; Se ainda assim os arquivos estiverem em uso, pede para fechar e tentar de novo (nada foi mexido ainda).
!macro FecharSistema
  ${If} ${FileExists} "$INSTDIR\python\python.exe"
    DetailPrint "Fechando o sistema, se estiver aberto (com backup)..."
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" ${ABRIR_ARGS} --fechar'
    Pop $0
  ${EndIf}
  ${DoWhile} ${FileExists} "$INSTDIR\python\python313.dll"
    ClearErrors
    FileOpen $1 "$INSTDIR\python\python313.dll" a
    ${IfNot} ${Errors}
      FileClose $1
      ${Break}
    ${EndIf}
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "O sistema da loja ainda está aberto.$\r$\n$\r$\nFeche o sistema (Configurações > Fechar o sistema) e clique em Repetir. Se não der certo, reinicie o computador e rode o instalador de novo." /SD IDCANCEL IDRETRY +2
    Abort "O sistema estava aberto. Nada foi alterado."
  ${Loop}
!macroend

Function .onInit
  ; um instalador aberto por vez (dois cliques a mais no arquivo não abrem outro)
  System::Call 'kernel32::CreateMutex(p 0, i 0, t "LojaMaterialConstrucaoInstalador") p .r1 ?e'
  Pop $R0
  ${If} $R0 = 183
    MessageBox MB_ICONINFORMATION "O instalador do ${NOME} já está aberto." /SD IDOK
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "O ${NOME} precisa do Windows 10 ou 11." /SD IDOK
    Abort
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "O ${NOME} precisa do Windows de 64 bits." /SD IDOK
    Abort
  ${EndIf}
FunctionEnd

Function TrocarBotaoAvancar
  GetDlgItem $0 $HWNDPARENT 1
  SendMessage $0 ${WM_SETTEXT} 0 "STR:&Instalar"
FunctionEnd

Function AbrirSistema
  SetOutPath "$INSTDIR\app"
  Exec '"$INSTDIR\python\pythonw.exe" ${ABRIR_ARGS}'
FunctionEnd

Section "Instalar"
  SetShellVarContext current
  !insertmacro FecharSistema

  ; troca o programa inteiro (sem sobras da versão anterior); os dados ficam em outra pasta
  DetailPrint "Copiando o programa..."
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\python"
  SetOutPath "$INSTDIR\python"
  File /r "${ORIGEM}/python/*"
  SetOutPath "$INSTDIR\app"
  File /r "${ORIGEM}/app/*"
  SetOutPath "$INSTDIR"
  File "${ORIGEM}/loja.ico"
  ; sobras do instalador antigo (INSTALAR.bat)
  Delete "$INSTDIR\comum.ps1"
  Delete "$INSTDIR\desinstalar.ps1"

  ; faz o Python achar o programa (caminho relativo: funciona com qualquer nome de usuário)
  FileOpen $0 "$INSTDIR\python\Lib\site-packages\loja-app.pth" w
  FileWrite $0 "..\..\..\app$\r$\n"
  FileClose $0

  DetailPrint "Criando os atalhos..."
  SetOutPath "$INSTDIR\app"
  CreateShortcut "$DESKTOP\${ATALHO}" "$INSTDIR\python\pythonw.exe" "${ABRIR_ARGS}" "$INSTDIR\loja.ico" 0 SW_SHOWNORMAL "" "Abrir o sistema da loja"
  CreateShortcut "$SMPROGRAMS\${ATALHO}" "$INSTDIR\python\pythonw.exe" "${ABRIR_ARGS}" "$INSTDIR\loja.ico" 0 SW_SHOWNORMAL "" "Abrir o sistema da loja"

  ; desinstalador e o item em Configurações > Aplicativos
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  WriteRegStr HKCU "${CHAVE}" "DisplayName" "${NOME}"
  WriteRegStr HKCU "${CHAVE}" "DisplayVersion" "${VERSAO}"
  WriteRegStr HKCU "${CHAVE}" "Publisher" "${NOME}"
  WriteRegStr HKCU "${CHAVE}" "DisplayIcon" "$INSTDIR\loja.ico"
  WriteRegStr HKCU "${CHAVE}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${CHAVE}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKCU "${CHAVE}" "QuietUninstallString" '"$INSTDIR\Desinstalar.exe" /S'
  WriteRegDWORD HKCU "${CHAVE}" "NoModify" 1
  WriteRegDWORD HKCU "${CHAVE}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${CHAVE}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  SetOutPath "$TEMP"   ; não prender a pasta do programa, que vai ser apagada
  !insertmacro FecharSistema
  Delete "$DESKTOP\${ATALHO}"
  Delete "$SMPROGRAMS\${ATALHO}"
  ; só as pastas do programa: os dados (AppData\Local\LojaMaterialConstrucao) e os backups ficam
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\python"
  Delete "$INSTDIR\loja.ico"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${CHAVE}"
  MessageBox MB_ICONINFORMATION "O programa foi removido.$\r$\n$\r$\nOs dados da loja NÃO foram apagados: continuam em $LOCALAPPDATA\LojaMaterialConstrucao, e os backups na pasta Documentos\Backup da Loja. Se instalar de novo, tudo volta como estava." /SD IDOK
SectionEnd
