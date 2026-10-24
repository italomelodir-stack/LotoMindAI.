"""Gera o instalador do Windows: dist/Instalar-Sistema-da-Loja-<versão>.exe

Um arquivo só, com o Python oficial para Windows e o programa dentro. Quem instala não precisa de
internet nem de administrador.

Precisa do NSIS 3 (makensis). Funciona no Windows (https://nsis.sourceforge.io) e no Linux
(apt install nsis). Uso, na pasta principal do projeto:

    python instalador/construir_instalador.py

O Python vem do pacote oficial "python" da Python Software Foundation no NuGet. Para não baixar, deixe o
arquivo python.<versão>.nupkg na pasta instalador/ ou informe com --python. O SHA-256 é conferido.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "instalador"
PYTHON_VERSAO = "3.13.16"
PYTHON_SHA256 = "95fad176338f1d6a799e45946488063f4aa61764e6cff2f132ddeffbf7a04c34"
PYTHON_URL = f"https://api.nuget.org/v3-flatcontainer/python/{PYTHON_VERSAO}/python.{PYTHON_VERSAO}.nupkg"

# partes do Python que o sistema não usa (instalador de pacotes, arquivos para compilar extensões, etc.)
SEM_USO = ["Lib/ensurepip", "Lib/venv", "Lib/idlelib", "Lib/turtledemo", "Lib/test", "Lib/tkinter",
           "include", "libs"]


def versao_do_sistema():
    for linha in (RAIZ / "loja" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if linha.startswith("VERSAO"):
            return linha.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("não achei VERSAO em loja/__init__.py")


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def pacote_python(informado, cache):
    candidatos = [Path(informado)] if informado else [PASTA / f"python.{PYTHON_VERSAO}.nupkg",
                                                      cache / f"python.{PYTHON_VERSAO}.nupkg"]
    for c in candidatos:
        if c.is_file():
            pacote = c
            break
    else:
        if informado:
            raise SystemExit(f"arquivo não encontrado: {informado}")
        pacote = candidatos[-1]
        pacote.parent.mkdir(parents=True, exist_ok=True)
        print(f"Baixando o Python {PYTHON_VERSAO} de {PYTHON_URL}")
        parcial = pacote.with_suffix(".parcial")
        urllib.request.urlretrieve(PYTHON_URL, parcial)
        os.replace(parcial, pacote)
    if sha256(pacote) != PYTHON_SHA256:
        raise SystemExit(f"{pacote} não confere com o SHA-256 esperado do Python {PYTHON_VERSAO}; apague e baixe de novo")
    return pacote


def montar(pacote, montagem):
    """Pasta com tudo que vai dentro do instalador: python/, app/loja/, o ícone e a imagem lateral."""
    if montagem.exists():
        shutil.rmtree(montagem)
    python = montagem / "python"
    with zipfile.ZipFile(pacote) as z:
        for item in z.infolist():
            if not item.filename.startswith("tools/") or item.is_dir():
                continue
            relativo = Path(item.filename[len("tools/"):])
            if ".." in relativo.parts or relativo.is_absolute():
                raise SystemExit(f"caminho inválido no pacote do Python: {item.filename}")
            destino = python / relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as origem, open(destino, "wb") as saida:
                shutil.copyfileobj(origem, saida)
    if not (python / "pythonw.exe").is_file():
        raise SystemExit("o pacote do Python não tem pythonw.exe")
    for parte in SEM_USO:
        shutil.rmtree(python / parte, ignore_errors=True)
    for item in (python / "Lib" / "site-packages").iterdir():
        if item.name.lower().startswith("pip"):
            shutil.rmtree(item)
    for cache in list(python.rglob("__pycache__")):
        shutil.rmtree(cache)
    (python / "versao-instalada.txt").write_text(PYTHON_VERSAO + "\n", encoding="ascii")

    shutil.copytree(RAIZ / "loja", montagem / "app" / "loja",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "*.db-*"))
    for arquivo in ("loja.ico", "lateral.bmp"):
        shutil.copy2(PASTA / arquivo, montagem / arquivo)


def achar_makensis():
    achado = shutil.which("makensis")
    if achado:
        return achado
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and (Path(base) / "NSIS" / "makensis.exe").is_file():
            return str(Path(base) / "NSIS" / "makensis.exe")
    raise SystemExit("makensis não encontrado: instale o NSIS 3 (Windows: nsis.sourceforge.io; Linux: apt install nsis)")


def construir(saida_dir=RAIZ / "dist", python=None):
    versao = versao_do_sistema()
    saida_dir = Path(saida_dir).resolve()
    pacote = pacote_python(python, saida_dir / "cache")
    montagem = saida_dir / "montagem"
    montar(pacote, montagem)
    exe = saida_dir / f"Instalar-Sistema-da-Loja-{versao}.exe"
    cmd = [achar_makensis(), "-V2", "-INPUTCHARSET", "UTF8",
           f"-DVERSAO={versao}", f"-DORIGEM={montagem}", f"-DSAIDA={exe}", str(PASTA / "loja.nsi")]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("o makensis falhou (veja as mensagens acima)")
    shutil.rmtree(montagem)
    return exe


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", default=str(RAIZ / "dist"), help="pasta onde o .exe é gerado (padrão: dist/)")
    p.add_argument("--python", help=f"arquivo python.{PYTHON_VERSAO}.nupkg já baixado")
    args = p.parse_args()
    exe = construir(args.saida, args.python)
    print(f"Instalador gerado: {exe} ({exe.stat().st_size / 1e6:.1f} MB)")
    print(f"SHA-256: {sha256(exe)}")


if __name__ == "__main__":
    sys.exit(main())
