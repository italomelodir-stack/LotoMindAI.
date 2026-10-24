"""Backup automático, restauração, configurações da loja e o programa de inicialização."""
import datetime
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from loja import Loja, LojaError
from loja.aplicativo import importar_banco
from loja.backup import Backups
from tests.base import Relogio

RAIZ = Path(__file__).resolve().parent.parent


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.relogio = Relogio()
        self.loja = Loja(str(self.tmp / "loja.db"), hoje=self.relogio)
        self.loja.abrir_caixa("100")
        self.cimento = self.loja.cadastrar_produto({"nome": "Cimento", "unidade": "SC", "preco_venda": "38,90",
                                                    "estoque_inicial": "100", "categoria": "Cimento"})
        self.agora = datetime.datetime(2026, 3, 10, 18, 0, 0)
        self.backups = Backups(self.loja, self.tmp / "Backup da Loja", agora=lambda: self.agora)

    def tearDown(self):
        self.loja.fechar()
        self._tmp.cleanup()

    def vender(self, qtd):
        return self.loja.registrar_venda({"itens": [{"produto_id": self.cimento["id"], "quantidade": qtd}],
                                          "pagamentos": [{"forma": "PIX", "valor": f"{38.9 * int(qtd):.2f}"}]})


class TestBackups(Base):
    def test_backup_gera_arquivo_unico_e_conferido(self):
        st = self.backups.fazer()
        arquivo = Path(st["arquivo"])
        Loja.verificar_banco(arquivo)
        self.assertEqual(sorted(p.name for p in arquivo.parent.iterdir()), [arquivo.name])   # nada de -wal/-shm
        self.assertEqual(arquivo.name, "loja-2026-03-10-180000.db")
        Loja.verificar_banco(arquivo)
        copia = Loja(str(arquivo))
        self.assertEqual(copia.obter_produto(self.cimento["id"])["estoque"], 100000)
        copia.fechar()
        self.assertEqual(self.backups.ultimo()["arquivo"], str(arquivo))
        self.assertEqual([b["nome"] for b in self.backups.listar()], [arquivo.name])

    def test_dois_backups_no_mesmo_segundo(self):
        a, b = self.backups.fazer(), self.backups.fazer()
        self.assertNotEqual(a["arquivo"], b["arquivo"])
        self.assertEqual(len(self.backups.listar()), 2)

    def test_backup_do_dia_so_uma_vez(self):
        self.assertIsNotNone(self.backups.diario())
        self.assertIsNone(self.backups.diario())
        self.agora += datetime.timedelta(days=1)
        self.assertIsNotNone(self.backups.diario())
        self.assertEqual(len(self.backups.listar()), 2)

    @unittest.skipIf(os.name == "nt" and os.environ.get("WINEPREFIX"),
                     "o wine 9 não tem a função CopyFile2, que existe no Windows desde a versão 8")
    def test_copia_extra_e_pen_drive_desconectado(self):
        pen = self.tmp / "pendrive"
        pen.mkdir()
        self.loja.salvar_configuracoes({"pasta_backup_extra": str(pen)})
        st = self.backups.fazer()
        self.assertTrue(Path(st["copia_extra"]).is_file())
        self.assertIsNone(st["erro_extra"])
        pen.rmdir() if not any(pen.iterdir()) else [p.unlink() for p in pen.iterdir()] and pen.rmdir()
        st = self.backups.fazer()                               # pen drive tirado: o backup principal continua
        self.assertTrue(Path(st["arquivo"]).is_file())
        self.assertIn("Não foi possível copiar", st["erro_extra"])
        self.assertIn("Não foi possível copiar", self.backups.ultimo()["erro_extra"])

    def test_limpeza_guarda_historico_suficiente(self):
        inicio = datetime.datetime(2026, 1, 1, 12, 0, 0)
        for dia in range(150):                                  # 150 dias, 3 backups por dia
            for hora in (9, 13, 18):
                self.agora = inicio + datetime.timedelta(days=dia, hours=hora - 12)
                self.backups.fazer()
        hoje = self.agora.date()
        dias = [datetime.date.fromisoformat(b["nome"][5:15]) for b in self.backups.listar()]
        recentes = [d for d in dias if (hoje - d).days <= 7]
        self.assertEqual(len(recentes), 8 * 3)                  # últimos 7 dias: todos
        antigos = [d for d in dias if (hoje - d).days > 7]
        self.assertEqual(len(antigos), len(set(antigos)))       # depois: um por dia
        self.assertEqual(max((hoje - d).days for d in dias), 90)  # nada além de 90 dias

    def test_restaurar(self):
        self.vender("2")
        nome = Path(self.backups.fazer()["arquivo"]).name
        self.vender("5")
        self.assertEqual(self.loja.obter_produto(self.cimento["id"])["estoque"], 93000)
        r = self.backups.restaurar(nome)
        self.assertEqual(self.loja.obter_produto(self.cimento["id"])["estoque"], 98000)
        self.assertEqual(len(self.loja.listar_vendas()), 1)
        self.assertEqual(self.loja.verificar_integridade(), [])
        # a cópia feita antes de restaurar permite desfazer
        self.backups.restaurar(r["copia_anterior"])
        self.assertEqual(self.loja.obter_produto(self.cimento["id"])["estoque"], 93000)
        self.vender("1")                                        # o sistema continua funcionando normalmente
        self.assertEqual(self.loja.obter_produto(self.cimento["id"])["estoque"], 92000)

    def test_restaurar_backup_de_versao_antiga_atualiza_o_banco(self):
        antigo = self.tmp / "Backup da Loja" / "loja-2025-01-01-120000.db"
        antigo.parent.mkdir(parents=True, exist_ok=True)
        self.loja.backup(str(antigo))
        con = sqlite3.connect(antigo)
        con.executescript("DROP TABLE baixas; DROP TABLE configuracoes;")
        con.close()
        self.backups.restaurar(antigo.name)
        self.loja.salvar_configuracoes({"telefone": "123"})     # tabela recriada
        self.assertEqual(self.loja.listar_baixas(), [])

    def test_restaurar_recusa_arquivos_ruins(self):
        self.vender("2")
        pasta = self.tmp / "Backup da Loja"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "loja-2026-03-01-120000.db").write_bytes(b"isto nao e um banco de dados" * 100)
        outro = sqlite3.connect(pasta / "loja-2026-03-02-120000.db")
        outro.execute("CREATE TABLE qualquer (x)")
        outro.close()
        for nome in ["loja-2026-03-01-120000.db", "loja-2026-03-02-120000.db", "../loja.db", "nada.db",
                     "loja-2026-03-03-120000.db"]:
            with self.subTest(nome=nome):
                with self.assertRaises(LojaError):
                    self.backups.restaurar(nome)
        self.assertEqual(len(self.loja.listar_vendas()), 1)    # nada foi mexido

    def test_verificar_banco_em_pasta_com_acento_e_espaco(self):
        pasta = self.tmp / "Usuários" / "Área de Trabalho"
        pasta.mkdir(parents=True)
        self.loja.backup(str(pasta / "cópia.db"))
        Loja.verificar_banco(pasta / "cópia.db")


class TestConfiguracoes(Base):
    def test_padrao_e_salvar(self):
        c = self.loja.obter_configuracoes()
        self.assertEqual(c["nome_loja"], "Loja de Materiais de Construção")
        c = self.loja.salvar_configuracoes({"nome_loja": "Casa do Construtor", "documento": "11.222.333/0001-81",
                                            "telefone": "(11) 3333-4444", "endereco": "Rua A, 10", "campo_estranho": "x"})
        self.assertEqual((c["nome_loja"], c["documento"]), ("Casa do Construtor", "11222333000181"))
        self.assertNotIn("campo_estranho", c)
        # persiste após reabrir
        self.loja.fechar()
        self.loja = Loja(str(self.tmp / "loja.db"))
        self.assertEqual(self.loja.obter_configuracoes()["telefone"], "(11) 3333-4444")

    def test_validacoes(self):
        for dados in [{"nome_loja": ""}, {"documento": "123"}, {"endereco": "x" * 301},
                      {"pasta_backup_extra": str(self.tmp / "nao-existe")}]:
            with self.subTest(dados=dados):
                with self.assertRaises(LojaError):
                    self.loja.salvar_configuracoes(dados)

    def test_valores_internos_nao_aparecem(self):
        self.loja.gravar_interno("ultimo_backup", "{}")
        self.assertNotIn("_ultimo_backup", self.loja.obter_configuracoes())
        self.assertEqual(self.loja.ler_interno("ultimo_backup"), "{}")

    def test_importar_banco_antigo(self):
        self.vender("3")
        destino = self.tmp / "dados" / "loja.db"
        self.assertTrue(importar_banco(self.tmp / "loja.db", destino))
        self.assertFalse(importar_banco(self.tmp / "loja.db", destino))   # nunca sobrescreve
        copia = Loja(str(destino))
        self.assertEqual(copia.obter_produto(self.cimento["id"])["estoque"], 97000)
        copia.fechar()


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestAplicativo(unittest.TestCase):
    """Roda o sistema como o atalho da área de trabalho faz, num processo separado."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.processos = []
        # PYTHONIOENCODING: no Windows, a saída redirecionada sai em cp1252 se não pedirmos UTF-8
        self.env = dict(os.environ, LOJA_SEM_JANELAS="1", PYTHONPATH=str(RAIZ), PYTHONIOENCODING="utf-8")

    def tearDown(self):
        for p in self.processos:
            if p.poll() is None:
                p.kill()
                p.wait()
        self._tmp.cleanup()

    def iniciar(self, porta, *extra, cwd=None, codigo=None):
        args = [sys.executable, "-m", "loja", "--dados", str(self.tmp / "dados"), "--backups", str(self.tmp / "backups"),
                "--porta", str(porta), "--sem-navegador", *extra]
        if codigo:   # roda o main() por código (para simular o pythonw, que não tem saída de texto)
            args = [sys.executable, "-c", codigo, *args[3:]]
        p = subprocess.Popen(args, cwd=cwd or str(self.tmp), env=self.env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        self.processos.append(p)
        return p

    def pedir(self, porta, caminho, corpo=None):
        req = urllib.request.Request(f"http://127.0.0.1:{porta}{caminho}", method="POST" if corpo is not None else "GET",
                                     data=json.dumps(corpo).encode() if corpo is not None else None,
                                     headers={"Content-Type": "application/json"})
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with abridor.open(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def esperar(self, porta, processo, segundos=30):
        limite = time.time() + segundos
        while time.time() < limite:
            if processo.poll() is not None:
                self.fail("o sistema fechou ao abrir:\n" + processo.stdout.read())
            try:
                return self.pedir(porta, "/api/config")
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        self.fail("o sistema não respondeu a tempo")

    def test_abrir_abrir_de_novo_e_fechar_pela_tela(self):
        porta = porta_livre()
        p = self.iniciar(porta)
        cfg = self.esperar(porta, p)
        self.assertTrue(cfg["pode_desligar"])
        self.assertEqual(cfg["backup"]["motivo"], "automático do dia")
        self.assertTrue((self.tmp / "dados" / "loja.db").is_file())
        # clicar no atalho de novo não abre uma segunda cópia
        segundo = self.iniciar(porta)
        saida, _ = segundo.communicate(timeout=30)
        self.assertEqual(segundo.returncode, 0)
        self.assertIn("já está aberto", saida)
        # fechar pelo botão da tela: faz backup e encerra
        self.assertEqual(self.pedir(porta, "/api/desligar", {}), {"ok": True})
        saida, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, saida)
        self.assertIn("Sistema fechado", saida)
        arquivos = sorted(b.name for b in (self.tmp / "backups").iterdir())
        self.assertEqual(len(arquivos), 2, arquivos)            # o do dia e o do fechamento, sem arquivos auxiliares
        self.assertTrue(all(a.endswith(".db") for a in arquivos))

    def test_porta_ocupada_por_outro_programa(self):
        porta = porta_livre()
        outro = socket.socket()
        outro.bind(("127.0.0.1", porta))
        outro.listen(1)
        try:
            p = self.iniciar(porta)
            saida = ""
            limite = time.time() + 30
            while time.time() < limite and "rodando em" not in saida:
                saida += p.stdout.readline()
            self.assertIn(f"localhost:{porta + 1}", saida)
            self.esperar(porta + 1, p)
            self.pedir(porta + 1, "/api/desligar", {})
            p.communicate(timeout=30)
        finally:
            outro.close()

    def test_dados_da_versao_anterior_sao_copiados(self):
        antiga = self.tmp / "versao-antiga"
        antiga.mkdir()
        loja = Loja(str(antiga / "loja.db"))
        loja.cadastrar_cliente({"nome": "Cliente Antigo"})
        loja.fechar()
        porta = porta_livre()
        p = self.iniciar(porta, cwd=str(antiga))
        self.esperar(porta, p)
        clientes = self.pedir(porta, "/api/clientes")
        self.assertEqual([c["nome"] for c in clientes], ["Cliente Antigo"])
        self.pedir(porta, "/api/desligar", {})
        p.communicate(timeout=30)
        self.assertTrue((antiga / "loja.db").is_file())       # o arquivo antigo é preservado

    def test_sem_janela_escreve_no_registro(self):
        porta = porta_livre()
        codigo = ("import sys; sys.stdout = None; sys.stderr = None; sys.argv[0] = 'loja'; "
                  "from loja.aplicativo import main; raise SystemExit(main(sys.argv[1:]))")
        p = self.iniciar(porta, codigo=codigo)
        self.esperar(porta, p)
        self.pedir(porta, "/api/desligar", {})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)
        registro = (self.tmp / "dados" / "loja.log").read_text(encoding="utf-8")
        self.assertIn("rodando em", registro)
        self.assertIn("Sistema fechado", registro)

    def test_erro_ao_abrir_avisa_e_registra(self):
        p = self.iniciar(porta_livre(), "--banco", str(self.tmp))   # uma pasta no lugar do arquivo do banco
        saida, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 1)
        self.assertIn("Não foi possível abrir o sistema da loja", saida)
