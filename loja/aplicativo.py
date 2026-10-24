"""Inicialização do sistema no computador da loja (é o que o atalho da área de trabalho chama).

- Os dados ficam numa pasta própria do usuário (no Windows: AppData\\Local\\LojaMaterialConstrucao),
  separados do programa: atualizar ou reinstalar o programa não apaga nada.
- Os backups ficam em Documentos\\Backup da Loja, fáceis de achar e copiar para um pen drive.
- Se o sistema já estiver aberto, só abre o navegador nele, em vez de abrir uma segunda cópia.
- Rodando sem janela (pythonw.exe), as mensagens vão para o arquivo loja.log na pasta dos dados.
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import traceback
import urllib.request
import webbrowser
from pathlib import Path

from . import VERSAO
from .backup import Backups
from .servidor import criar_servidor
from .sistema import Loja

NOME_PASTA = "LojaMaterialConstrucao"
PORTA_PADRAO = 8080
LOCAL = ("127.0.0.1", "localhost")


def pasta_dados():
    if os.environ.get("LOJA_DADOS"):
        return Path(os.environ["LOJA_DADOS"])
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / NOME_PASTA
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / NOME_PASTA


def pasta_documentos():
    if os.name == "nt":
        try:   # pasta Documentos de verdade (pode estar em outro disco ou no OneDrive)
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def pasta_backups_padrao():
    if os.environ.get("LOJA_BACKUPS"):
        return Path(os.environ["LOJA_BACKUPS"])
    return pasta_documentos() / "Backup da Loja"


def preparar_registro(pasta):
    """Sem janela (pythonw) não há onde escrever mensagens: elas vão para loja.log."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    log = pasta / "loja.log"
    if log.exists() and log.stat().st_size > 2_000_000:
        os.replace(log, pasta / "loja.log.1")
    arquivo = open(log, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = arquivo
    return arquivo


def sistema_ja_aberto(porta):
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # nunca passar por proxy
    try:
        with abridor.open(f"http://127.0.0.1:{porta}/api/config", timeout=3) as r:
            return "nome_loja" in json.loads(r.read().decode("utf-8"))
    except Exception:
        return False


def importar_banco(origem, destino):
    """Copia o banco de uma versão anterior (que ficava na pasta do programa) para a pasta dos dados."""
    destino = Path(destino)
    if destino.exists():
        return False
    Loja.verificar_banco(origem, imutavel=False)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fonte = sqlite3.connect(origem)   # abre normal: se o programa antigo fechou de repente, o SQLite recupera o diário
    try:
        alvo = sqlite3.connect(destino)
        try:
            fonte.backup(alvo)
        finally:
            alvo.close()
    finally:
        fonte.close()
    return True


def aviso_fatal(mensagem):
    print(mensagem, file=sys.stderr)
    if os.name == "nt" and not os.environ.get("LOJA_SEM_JANELAS"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, mensagem, "Sistema da loja", 0x10)
        except Exception:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(prog="loja", description="Sistema para loja de material de construção")
    p.add_argument("--dados", help="pasta dos dados (padrão: pasta do usuário)")
    p.add_argument("--banco", help="arquivo do banco (padrão: loja.db dentro da pasta dos dados)")
    p.add_argument("--backups", help="pasta dos backups (padrão: Documentos/Backup da Loja)")
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 para liberar o acesso de outros computadores da rede")
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    p.add_argument("--sem-navegador", action="store_true", help="não abre o navegador")
    p.add_argument("--importar", metavar="ARQUIVO", help="copia um banco antigo para a pasta dos dados e sai")
    args = p.parse_args(argv)

    pasta = Path(args.dados) if args.dados else pasta_dados()
    pasta.mkdir(parents=True, exist_ok=True)
    preparar_registro(pasta)
    banco = Path(args.banco) if args.banco else pasta / "loja.db"
    try:
        if args.importar:
            if importar_banco(args.importar, banco):
                print(f"Dados importados de {args.importar} para {banco}")
            else:
                print(f"Já existem dados em {banco}; nada foi importado")
            return 0
        if not banco.exists():
            for antigo in (Path.cwd() / "loja.db", Path(__file__).resolve().parent.parent / "loja.db"):
                if antigo.is_file():
                    importar_banco(antigo, banco)
                    print(f"Dados da versão anterior copiados de {antigo}")
                    break

        loja = backups = servidor = None
        for porta in range(args.porta, args.porta + 20):
            if args.host in LOCAL and sistema_ja_aberto(porta):
                print(f"O sistema já está aberto na porta {porta}; abrindo o navegador.")
                if not args.sem_navegador:
                    webbrowser.open(f"http://localhost:{porta}")
                return 0
            if loja is None:
                loja = Loja(str(banco))
                backups = Backups(loja, Path(args.backups) if args.backups else pasta_backups_padrao())
            try:
                servidor = criar_servidor(loja, args.host, porta, silencioso=True, backups=backups,
                                          ao_desligar=lambda: servidor.shutdown())
                break
            except OSError:
                continue   # porta ocupada por outro programa
        if servidor is None:
            raise OSError(f"Nenhuma porta livre entre {args.porta} e {args.porta + 19}")

        try:
            backups.diario()
        except Exception:
            traceback.print_exc()
        url = f"http://localhost:{servidor.server_address[1]}"
        print(f"Sistema da loja {VERSAO} rodando em {url}")
        print(f"Dados: {banco}")
        print(f"Backups: {backups.pasta}")
        backups.iniciar_automatico()
        if not args.sem_navegador:
            webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            backups.parar()
            try:
                backups.fazer("ao fechar o sistema")
            except Exception:
                traceback.print_exc()
            servidor.server_close()
            loja.fechar()
            print("Sistema fechado.")
        return 0
    except Exception as e:
        traceback.print_exc()
        aviso_fatal(f"Não foi possível abrir o sistema da loja:\n\n{e}\n\nDetalhes no arquivo {pasta / 'loja.log'}")
        return 1
