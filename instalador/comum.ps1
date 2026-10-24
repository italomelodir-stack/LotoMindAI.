# Funções usadas pelo instalador e pelo desinstalador.

function Passo([string]$texto) {
    Write-Host ''
    Write-Host "==> $texto" -ForegroundColor Cyan
}

function Pedir-Sistema([int]$porta, [string]$caminho, [string]$metodo) {
    $req = [System.Net.WebRequest]::Create("http://127.0.0.1:$porta$caminho")
    $req.Proxy = $null
    $req.Timeout = 3000
    $req.Method = $metodo
    if ($metodo -eq 'POST') {
        $req.ContentType = 'application/json'
        $corpo = [Text.Encoding]::UTF8.GetBytes('{}')
        $req.ContentLength = $corpo.Length
        $fluxo = $req.GetRequestStream()
        $fluxo.Write($corpo, 0, $corpo.Length)
        $fluxo.Close()
    }
    $resp = $req.GetResponse()
    $leitor = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $texto = $leitor.ReadToEnd()
    $leitor.Close()
    $resp.Close()
    return $texto
}

# Se o sistema estiver aberto, pede para ele fechar (ele faz backup antes) e espera terminar.
function Fechar-SistemaAberto {
    foreach ($porta in 8080..8099) {
        try {
            if ((Pedir-Sistema $porta '/api/config' 'GET') -notmatch '"nome_loja"') { continue }
        } catch { continue }
        Passo "Fechando o sistema que está aberto (com backup)..."
        try { Pedir-Sistema $porta '/api/desligar' 'POST' | Out-Null } catch { }
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Milliseconds 500
            try { Pedir-Sistema $porta '/api/config' 'GET' | Out-Null } catch { break }
        }
        Start-Sleep -Seconds 1
    }
}

function Pasta-Programa {
    return [System.IO.Path]::Combine($env:LOCALAPPDATA, 'Programs', 'LojaMaterialConstrucao')
}

$NomeAtalho = 'Sistema da Loja.lnk'

# Área de trabalho e menu Iniciar (ignora pastas que o Windows não informar)
function Pastas-Atalho {
    return @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) | Where-Object { $_ }
}
