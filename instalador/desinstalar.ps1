# Remove o programa e os atalhos. Os DADOS e os BACKUPS são mantidos.
param([string]$Destino = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'comum.ps1')
try {
    if (-not $Destino) { $Destino = Pasta-Programa }
    Fechar-SistemaAberto
    Passo 'Removendo os atalhos...'
    foreach ($pasta in Pastas-Atalho) {
        $atalho = Join-Path $pasta $NomeAtalho
        if (Test-Path $atalho) { Remove-Item $atalho -Force }
    }
    Passo 'Removendo o programa...'
    if (Test-Path $Destino) { Remove-Item $Destino -Recurse -Force }
    Write-Host ''
    Write-Host 'O programa foi removido.' -ForegroundColor Green
    Write-Host ('Seus dados continuam guardados em ' + (Join-Path $env:LOCALAPPDATA 'LojaMaterialConstrucao'))
    Write-Host 'e os backups em Documentos\Backup da Loja. Se instalar de novo, tudo volta.'
    exit 0
} catch {
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
