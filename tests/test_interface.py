"""Roda o teste de interface em navegador (tests/interface.e2e.js), se Node + Playwright estiverem instalados."""
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from loja import Loja
from loja.backup import Backups
from loja.servidor import criar_servidor

SCRIPT = Path(__file__).with_name("interface.e2e.js")


def _playwright_disponivel():
    if not shutil.which("node"):
        return False
    r = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, cwd=tempfile.gettempdir())
    return r.returncode == 0


@unittest.skipUnless(_playwright_disponivel(), "Node.js com Playwright não está instalado")
class TestInterface(unittest.TestCase):
    def test_navegador(self):
        with tempfile.TemporaryDirectory() as pasta:
            loja = Loja(os.path.join(pasta, "loja.db"))
            servidor = criar_servidor(loja, porta=0, silencioso=True, backups=Backups(loja, os.path.join(pasta, "backups")),
                                      ao_desligar=lambda: servidor.shutdown())
            threading.Thread(target=servidor.serve_forever, daemon=True).start()
            try:
                r = subprocess.run(["node", str(SCRIPT), f"http://127.0.0.1:{servidor.server_address[1]}"],
                                   capture_output=True, text=True, timeout=300, cwd=tempfile.gettempdir())
                print(r.stdout)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(loja.verificar_integridade(), [])
            finally:
                servidor.shutdown()
                servidor.server_close()
                loja.fechar()
