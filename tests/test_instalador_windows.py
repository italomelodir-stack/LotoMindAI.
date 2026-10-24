"""Testa o instalador do Windows (instalador/instalar.ps1) de ponta a ponta.

Precisa do PowerShell (pwsh). Com o wine instalado, também abre o programa instalado usando o Python de
Windows, como o atalho da área de trabalho faz. Sem essas ferramentas, o teste é pulado.
Para não baixar o Python a cada execução: LOJA_PYTHON_NUPKG=/caminho/python.3.13.16.nupkg
"""
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PWSH = shutil.which("pwsh") or next((str(p) for p in [Path.home() / ".dotnet/tools/pwsh"] if p.exists()), None)
WINE = shutil.which("wine")
VERSAO_PYTHON = "3.13.16"


@unittest.skipUnless(PWSH and os.name != "nt", "precisa do PowerShell (pwsh) num Linux de testes")
class TestInstaladorWindows(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.local = self.tmp / "João Silva" / "AppData" / "Local"      # nome de usuário com acento e espaço
        self.local.mkdir(parents=True)
        (self.tmp / "temp").mkdir()
        self.extraido = self.tmp / "extraido"
        ignorar = shutil.ignore_patterns("__pycache__", "*.nupkg")
        shutil.copytree(RAIZ / "loja", self.extraido / "loja", ignore=ignorar)
        shutil.copytree(RAIZ / "instalador", self.extraido / "instalador", ignore=ignorar)
        pacote = os.environ.get("LOJA_PYTHON_NUPKG")
        if pacote and Path(pacote).is_file():
            shutil.copy(pacote, self.extraido / "instalador" / f"python.{VERSAO_PYTHON}.nupkg")
        self.destino = self.local / "Programs" / "LojaMaterialConstrucao"

    def tearDown(self):
        self._tmp.cleanup()

    def pwsh(self, script, *args):
        env = dict(os.environ, LOCALAPPDATA=str(self.local), TEMP=str(self.tmp / "temp"))
        return subprocess.run([PWSH, "-NoProfile", "-File", str(self.extraido / "instalador" / script), *args],
                              cwd=self.extraido, env=env, capture_output=True, text=True, timeout=600)

    def test_instalar_usar_e_desinstalar(self):
        r = self.pwsh("instalar.ps1", "-NaoAbrir")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Pronto! O sistema da loja foi instalado.", r.stdout)
        python = self.destino / "python"
        app = self.destino / "app"
        self.assertTrue((python / "pythonw.exe").is_file())
        self.assertEqual((python / "versao-instalada.txt").read_text().strip(), VERSAO_PYTHON)
        self.assertTrue((app / "loja" / "__main__.py").is_file())
        self.assertEqual(list(app.rglob("__pycache__")), [])
        self.assertTrue((self.destino / "loja.ico").is_file())
        self.assertEqual((python / "Lib" / "site-packages" / "loja-app.pth").read_text(encoding="utf-8").strip(), str(app))
        if WINE:
            self.abrir_com_wine(python, app)
        # reinstalar (atualizar) reaproveita o Python
        r = self.pwsh("instalar.ps1", "-NaoAbrir")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("já está instalado", r.stdout)
        # desinstalar remove o programa e mantém os dados
        dados = self.local / "LojaMaterialConstrucao"
        dados.mkdir(exist_ok=True)
        (dados / "loja.db").write_bytes(b"dados do cliente")
        r = self.pwsh("desinstalar.ps1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.destino.exists())
        self.assertEqual((dados / "loja.db").read_bytes(), b"dados do cliente")

    def abrir_com_wine(self, python, app):
        """Abre o programa instalado como o atalho faz (pythonw.exe -m loja) e usa pelo navegador."""
        def winepath(p):
            return subprocess.run(["winepath", "-w", str(p)], capture_output=True, text=True).stdout.strip()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        dados, backups = self.tmp / "dados-win", self.tmp / "backups-win"
        env = dict(os.environ, WINEDEBUG="-all", LANG="C.UTF-8", LC_ALL="C.UTF-8", LOJA_SEM_JANELAS="1",
                   LOJA_DADOS=winepath(dados), LOJA_BACKUPS=winepath(backups))
        abrir = ["wine", "start", "/unix", str(python / "pythonw.exe"), "-m", "loja", "--sem-navegador", "--porta", str(porta)]
        subprocess.run(abrir, cwd=app, env=env, timeout=120)
        url = f"http://127.0.0.1:{porta}"
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def pedir(caminho, corpo=None):
            req = urllib.request.Request(url + caminho, data=json.dumps(corpo).encode() if corpo is not None else None,
                                         method="POST" if corpo is not None else "GET", headers={"Content-Type": "application/json"})
            with abridor.open(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8"))

        cfg = None
        for _ in range(90):
            try:
                cfg = pedir("/api/config")
                break
            except OSError:
                time.sleep(1)
        self.assertIsNotNone(cfg, "o programa instalado não abriu")
        self.assertEqual(cfg["backup"]["motivo"], "automático do dia")
        # segundo clique no atalho: não abre outra cópia
        subprocess.run(["wine", "start", "/wait", *abrir[2:]], cwd=app, env=env, timeout=120)
        pedir("/api/caixa/abrir", {"valor_inicial": "50"})
        p = pedir("/api/produtos", {"nome": "Cimento", "unidade": "SC", "preco_venda": "38,90", "estoque_inicial": "10"})
        venda = pedir("/api/vendas", {"itens": [{"produto_id": p["id"], "quantidade": "3"}],
                                      "pagamentos": [{"forma": "DINHEIRO", "valor": "150"}]})
        self.assertEqual((venda["total"], venda["troco"]), (11670, 3330))
        self.assertTrue(pedir("/api/integridade")["ok"])
        self.assertEqual(pedir("/api/desligar", {}), {"ok": True})
        for _ in range(60):
            try:
                pedir("/api/config")
                time.sleep(0.5)
            except OSError:
                break
        time.sleep(2)
        registro = (dados / "loja.log").read_text(encoding="utf-8")
        self.assertIn("rodando em", registro)
        self.assertIn("já está aberto", registro)
        self.assertIn("Sistema fechado", registro)
        self.assertEqual(len([b for b in backups.iterdir() if b.suffix == ".db"]), 2)   # do dia e do fechamento

    def test_pacote_do_python_adulterado_e_recusado(self):
        (self.extraido / "instalador" / f"python.{VERSAO_PYTHON}.nupkg").write_bytes(b"arquivo falso")
        r = self.pwsh("instalar.ps1", "-NaoAbrir")
        self.assertEqual(r.returncode, 1)
        self.assertIn("não confere com o esperado", r.stdout)
        self.assertFalse((self.destino / "python").exists())

    def test_zip_nao_extraido(self):
        shutil.rmtree(self.extraido / "loja")
        r = self.pwsh("instalar.ps1", "-NaoAbrir")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Extraia o ZIP inteiro", r.stdout)
