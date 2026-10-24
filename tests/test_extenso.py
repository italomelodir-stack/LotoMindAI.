"""Roda os testes do valor por extenso (tests/extenso.test.js), se o Node.js estiver instalado."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("node"), "Node.js não está instalado")
class TestExtenso(unittest.TestCase):
    def test_valores_por_extenso(self):
        r = subprocess.run(["node", str(Path(__file__).with_name("extenso.test.js"))], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("valores por extenso conferidos", r.stdout)
