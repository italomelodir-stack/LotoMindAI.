# Instalador do sistema da loja para Windows 10/11. Não precisa de administrador.
# Uso normal: dois cliques em INSTALAR.bat (na pasta principal do programa).
param(
    [string]$Destino = '',
    [switch]$NaoAbrir
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'comum.ps1')

# Python oficial para Windows (pacote "python" da Python Software Foundation no NuGet).
# O SHA-256 garante que o arquivo baixado é exatamente o que foi testado.
$PythonVersao = '3.13.16'
$PythonSha256 = '95FAD176338F1D6A799E45946488063F4AA61764E6CFF2F132DDEFFBF7A04C34'
$PythonUrl = "https://api.nuget.org/v3-flatcontainer/python/$PythonVersao/python.$PythonVersao.nupkg"

try {
    if (-not $Destino) { $Destino = Pasta-Programa }
    $Origem = Split-Path -Parent $PSScriptRoot
    $PastaPython = Join-Path $Destino 'python'
    $PastaApp = Join-Path $Destino 'app'
    $Pythonw = Join-Path $PastaPython 'pythonw.exe'
    $Python = Join-Path $PastaPython 'python.exe'

    if (-not (Test-Path ([System.IO.Path]::Combine($Origem, 'loja', '__main__.py')))) {
        throw "Não encontrei os arquivos do programa em $Origem. Extraia o ZIP inteiro numa pasta antes de instalar."
    }
    Write-Host 'Instalando o sistema da loja...' -ForegroundColor Green
    Fechar-SistemaAberto
    New-Item -ItemType Directory -Force -Path $Destino | Out-Null

    # 1. Python
    $Marcador = Join-Path $PastaPython 'versao-instalada.txt'
    $jaTem = (Test-Path $Pythonw) -and (Test-Path $Marcador) -and ((Get-Content $Marcador -Raw).Trim() -eq $PythonVersao)
    if ($jaTem) {
        Passo "Python $PythonVersao já está instalado"
    } else {
        $pacote = Join-Path $PSScriptRoot "python.$PythonVersao.nupkg"   # instalação sem internet: deixe o arquivo aqui
        if (-not (Test-Path $pacote)) {
            Passo "Baixando o Python $PythonVersao (cerca de 15 MB)..."
            $pacote = Join-Path $env:TEMP "python.$PythonVersao.nupkg"
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $PythonUrl -OutFile $pacote -UseBasicParsing
            } catch {
                throw "Não consegui baixar o Python. Confira a internet e tente de novo. ($($_.Exception.Message))"
            }
        }
        $hash = (Get-FileHash -Algorithm SHA256 -Path $pacote).Hash
        if ($hash -ne $PythonSha256) {
            Remove-Item $pacote -Force -ErrorAction SilentlyContinue
            throw 'O arquivo do Python não confere com o esperado (pode ter vindo corrompido). Tente instalar de novo.'
        }
        Passo 'Instalando o Python...'
        $temp = Join-Path $env:TEMP ('loja-python-' + [guid]::NewGuid().ToString())
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($pacote, $temp)
        if (Test-Path $PastaPython) { Remove-Item $PastaPython -Recurse -Force }
        Move-Item (Join-Path $temp 'tools') $PastaPython
        Remove-Item $temp -Recurse -Force
        Set-Content -Path $Marcador -Value $PythonVersao -Encoding ASCII
    }

    # 2. Programa (os dados ficam em outra pasta e não são tocados)
    Passo 'Copiando o programa...'
    if (Test-Path $PastaApp) { Remove-Item $PastaApp -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $PastaApp | Out-Null
    Copy-Item -Path (Join-Path $Origem 'loja') -Destination $PastaApp -Recurse
    Get-ChildItem -Path $PastaApp -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
    Copy-Item -Path (Join-Path $PSScriptRoot 'loja.ico') -Destination (Join-Path $Destino 'loja.ico') -Force
    Copy-Item -Path (Join-Path $PSScriptRoot 'comum.ps1') -Destination (Join-Path $Destino 'comum.ps1') -Force
    Copy-Item -Path (Join-Path $PSScriptRoot 'desinstalar.ps1') -Destination (Join-Path $Destino 'desinstalar.ps1') -Force
    # faz o Python achar o programa (arquivo .pth com caminho relativo: funciona com qualquer nome de usuário)
    $pth = [System.IO.Path]::Combine($PastaPython, 'Lib', 'site-packages', 'loja-app.pth')
    [System.IO.File]::WriteAllText($pth, "..\..\..\app`r`n", [System.Text.Encoding]::ASCII)

    # 3. Dados da versão anterior (antes o banco ficava junto do programa, aberto pelo iniciar.bat)
    $bancoAntigo = Join-Path $Origem 'loja.db'
    if (Test-Path $bancoAntigo) {
        Passo 'Trazendo os dados da versão anterior...'
        & $Python -I -m loja --importar $bancoAntigo
        if ($LASTEXITCODE -ne 0) { throw 'Não foi possível trazer os dados da versão anterior.' }
    }

    # 4. Atalhos na área de trabalho e no menu Iniciar
    Passo 'Criando os atalhos...'
    try {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($pasta in Pastas-Atalho) {
            $atalho = $shell.CreateShortcut((Join-Path $pasta $NomeAtalho))
            $atalho.TargetPath = $Pythonw
            $atalho.Arguments = '-I -m loja'
            $atalho.WorkingDirectory = $PastaApp
            $atalho.IconLocation = (Join-Path $Destino 'loja.ico')
            $atalho.Description = 'Sistema da loja de materiais de construção'
            $atalho.Save()
        }
    } catch {
        Write-Warning "Não consegui criar os atalhos ($($_.Exception.Message)). Para abrir o sistema, use: `"$Pythonw`" -I -m loja"
    }

    # 5. Abrir
    if (-not $NaoAbrir) {
        Passo 'Abrindo o sistema...'
        try { Start-Process -FilePath $Pythonw -ArgumentList '-I', '-m', 'loja' -WorkingDirectory $PastaApp }
        catch { Write-Warning 'Não consegui abrir o sistema agora. Use o atalho na área de trabalho.' }
    }
    Write-Host ''
    Write-Host 'Pronto! O sistema da loja foi instalado.' -ForegroundColor Green
    Write-Host 'Para abrir, use o atalho "Sistema da Loja" na área de trabalho.'
    Write-Host 'Os backups automáticos ficam na pasta Documentos\Backup da Loja.'
    exit 0
} catch {
    Write-Host ''
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
