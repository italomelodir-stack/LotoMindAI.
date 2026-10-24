"""Testa o instalador .exe do Windows (instalador/loja.nsi) de ponta a ponta, num Windows simulado (wine).

Gera o instalador, instala num "computador novo" (prefixo do wine vazio), abre o sistema pelo atalho da
área de trabalho, vende, atualiza com o sistema aberto e desinstala, conferindo que os dados ficam.
Precisa do NSIS (makensis) e do wine com suporte a 32 bits; sem eles, o teste é pulado.
Para não baixar o Python a cada execução: LOJA_PYTHON_NUPKG=/caminho/python.3.13.16.nupkg
"""
import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "instalador"))
import construir_instalador  # noqa: E402

WINE = shutil.which("wine")
WINE32 = any(glob.glob(p) for p in ("/usr/lib/i386-linux-gnu/wine/i386-windows", "/usr/lib/wine/i386-windows",
                                    "/opt/wine*/lib/wine/i386-windows"))
CHAVE = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\LojaMaterialConstrucao"


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(shutil.which("makensis") and WINE and WINE32 and os.name != "nt",
                     "precisa do NSIS (makensis) e do wine com 32 bits num Linux de testes")
class TestInstaladorExe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="loja-exe-"))
        pacote = os.environ.get("LOJA_PYTHON_NUPKG")
        cls.exe = construir_instalador.construir(cls.tmp / "dist", pacote if pacote and Path(pacote).is_file() else None)
        cls.porta = porta_livre()
        (cls.tmp / "home").mkdir()
        cls.env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}   # sem tela: tudo em modo silencioso
        cls.env.update(WINEPREFIX=str(cls.tmp / "prefixo"), HOME=str(cls.tmp / "home"), WINEDEBUG="-all",
                       WINEDLLOVERRIDES="winemenubuilder.exe=d", LANG="C.UTF-8", LC_ALL="C.UTF-8",
                       LOJA_PORTA=str(cls.porta), LOJA_SEM_NAVEGADOR="1", LOJA_SEM_JANELAS="1")
        subprocess.run(["wineboot", "-i"], env=cls.env, capture_output=True, timeout=300)
        usuarios = [u for u in (cls.tmp / "prefixo" / "drive_c" / "users").iterdir() if u.name != "Public"]
        cls.usuario = usuarios[0]
        cls.programa = cls.usuario / "AppData" / "Local" / "Programs" / "LojaMaterialConstrucao"
        cls.dados = cls.usuario / "AppData" / "Local" / "LojaMaterialConstrucao"
        cls.backups = cls.usuario / "Documents" / "Backup da Loja"
        cls.atalhos = [cls.usuario / "Desktop" / "Sistema da Loja.lnk",
                       cls.usuario / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Sistema da Loja.lnk"]

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["wineserver", "-k"], env=cls.env, capture_output=True, timeout=60)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def wine(self, *args, timeout=300):
        return subprocess.run(["wine", *args], env=self.env, cwd=self.tmp, capture_output=True, text=True, timeout=timeout)

    def pedir(self, caminho, corpo=None):
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"http://127.0.0.1:{self.porta}{caminho}",
                                     data=json.dumps(corpo).encode() if corpo is not None else None,
                                     method="POST" if corpo is not None else "GET", headers={"Content-Type": "application/json"})
        with abridor.open(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def aberto(self):
        try:
            return self.pedir("/api/config")
        except OSError:
            return None

    def abrir_pelo_atalho(self, atalho):
        self.assertIsNone(self.aberto())
        caminho = "C:\\" + str(atalho.relative_to(self.tmp / "prefixo" / "drive_c")).replace("/", "\\")
        # sem capturar a saída: o sistema aberto herdaria o canal e o teste esperaria ele fechar
        subprocess.run(["wine", "start", caminho], env=self.env, cwd=self.tmp, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(90):
            cfg = self.aberto()
            if cfg:
                return cfg
            time.sleep(1)
        self.fail("o sistema não abriu pelo atalho:\n" + self.registro())

    def registro(self):
        log = self.dados / "loja.log"
        return log.read_text(encoding="utf-8") if log.exists() else "(sem loja.log)"

    def backups_db(self):
        return sorted(b.name for b in self.backups.glob("*.db")) if self.backups.exists() else []

    def chave_registro(self):
        r = self.wine("reg", "query", CHAVE, timeout=60)
        return r.stdout if r.returncode == 0 else None

    def test_instalar_usar_atualizar_e_desinstalar(self):
        # 1. instalação num computador novo
        r = self.wine(str(self.exe), "/S")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        python = self.programa / "python"
        for arquivo in ("pythonw.exe", "python313.dll", "DLLs/_sqlite3.pyd", "DLLs/sqlite3.dll", "Lib/sqlite3/__init__.py"):
            self.assertTrue((python / arquivo).is_file(), arquivo)
        self.assertTrue((self.programa / "app" / "loja" / "static" / "app.js").is_file())
        self.assertTrue((self.programa / "Desinstalar.exe").is_file())
        self.assertFalse(list((python / "Lib" / "site-packages").glob("pip*")), "o pip não precisa ir junto")
        self.assertEqual((python / "Lib" / "site-packages" / "loja-app.pth").read_bytes(), b"..\\..\\..\\app\r\n")
        for atalho in self.atalhos:
            self.assertTrue(atalho.is_file(), atalho)
        chave = self.chave_registro()
        self.assertIsNotNone(chave, "não apareceu em Configurações > Aplicativos")
        self.assertIn("Sistema da Loja", chave)
        self.assertIn(construir_instalador.versao_do_sistema(), chave)
        self.assertIn("Desinstalar.exe", chave)

        # 2. abre pelo atalho da área de trabalho e usa
        cfg = self.abrir_pelo_atalho(self.atalhos[0])
        self.assertEqual(cfg["backup"]["motivo"], "automático do dia")
        self.assertTrue((self.dados / "loja.db").is_file())
        self.pedir("/api/caixa/abrir", {"valor_inicial": "50"})
        p = self.pedir("/api/produtos", {"nome": "Cimento", "unidade": "SC", "preco_venda": "38,90", "estoque_inicial": "10"})
        venda = self.pedir("/api/vendas", {"itens": [{"produto_id": p["id"], "quantidade": "3"}],
                                           "pagamentos": [{"forma": "DINHEIRO", "valor": "150"}]})
        self.assertEqual((venda["total"], venda["troco"]), (11670, 3330))
        self.assertEqual(len(self.backups_db()), 1)

        # 3. atualizar com o sistema aberto: o instalador fecha o sistema (com backup) antes de trocar os arquivos
        (self.programa / "app" / "loja" / "sobra-da-versao-antiga.py").write_text("x = 1\n")
        r = self.wine(str(self.exe), "/S")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNone(self.aberto(), "o instalador deveria ter fechado o sistema")
        self.assertIn("Sistema fechado.", self.registro())
        self.assertEqual(len(self.backups_db()), 2)   # + o backup ao fechar
        self.assertFalse((self.programa / "app" / "loja" / "sobra-da-versao-antiga.py").exists())

        # 4. abre pelo menu Iniciar: os dados continuam lá
        self.abrir_pelo_atalho(self.atalhos[1])
        produtos = self.pedir("/api/produtos")
        self.assertEqual([(x["nome"], x["estoque"]) for x in produtos], [("Cimento", 7000)])
        self.assertTrue(self.pedir("/api/integridade")["ok"])

        # 5. desinstalar com o sistema aberto: fecha com backup, remove o programa e mantém os dados
        r = self.wine(str(self.programa / "Desinstalar.exe"), "/S")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for _ in range(120):   # o desinstalador roda uma cópia de si mesmo e volta antes de terminar
            if not self.programa.exists() and self.chave_registro() is None:
                break
            time.sleep(1)
        self.assertFalse(self.programa.exists(), "a pasta do programa deveria ter sido apagada")
        self.assertIsNone(self.chave_registro())
        for atalho in self.atalhos:
            self.assertFalse(atalho.exists(), atalho)
        self.assertIsNone(self.aberto())
        self.assertTrue((self.dados / "loja.db").is_file(), "os dados da loja não podem ser apagados")
        self.assertEqual(len(self.backups_db()), 3)

        # 6. instalar de novo: tudo volta como estava
        r = self.wine(str(self.exe), "/S")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.abrir_pelo_atalho(self.atalhos[0])
        self.assertEqual(len(self.pedir("/api/vendas")), 1)
        self.pedir("/api/desligar", {})
        for _ in range(60):
            if self.aberto() is None:
                break
            time.sleep(0.5)
