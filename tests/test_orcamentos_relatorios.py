from loja.valores import LojaError
from tests.base import BaseLoja


class TestOrcamentos(BaseLoja):
    def orcar(self, itens, **extra):
        dados = {"itens": [{"produto_id": p["id"], "quantidade": q} for p, q in itens]}
        dados.update(extra)
        return self.loja.criar_orcamento(dados)

    def test_orcamento_nao_mexe_no_estoque(self):
        o = self.orcar([(self.cimento, "20"), (self.areia, "3")], nome_cliente="Maria", desconto="25")
        self.assertEqual(o["subtotal"], 20 * 3890 + 3 * 14500)
        self.assertEqual(o["total"], o["subtotal"] - 2500)
        self.assertEqual(o["validade"], "2026-03-20")
        self.assertEqual(self.estoque(self.cimento), 100000)

    def test_orcamento_aceita_quantidade_acima_do_estoque_mas_venda_nao(self):
        o = self.orcar([(self.cimento, "150")])
        with self.assertRaises(LojaError):
            self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "PIX", "valor": "5835"}]})
        self.assertEqual(self.loja.obter_orcamento(o["id"])["status"], "ABERTO")

    def test_converter_mantem_preco_combinado(self):
        o = self.orcar([(self.cimento, "10")], desconto="9")
        self.loja.atualizar_produto(self.cimento["id"], {"preco_venda": "45"})
        v = self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "PIX", "valor": "380"}]})
        self.assertEqual(v["total"], 38000)
        self.assertEqual(v["itens"][0]["preco_unitario"], 3890)
        self.assertEqual(v["orcamento_id"], o["id"])
        self.assertEqual(self.estoque(self.cimento), 90000)
        o = self.loja.obter_orcamento(o["id"])
        self.assertEqual((o["status"], o["venda_id"]), ("CONVERTIDO", v["id"]))
        with self.assertRaises(LojaError):
            self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "PIX", "valor": "380"}]})

    def test_converter_com_crediario(self):
        o = self.orcar([(self.areia, "2,5")], cliente_id=self.cliente["id"])
        v = self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "CREDIARIO", "valor": "362,50"}],
                                                    "crediario": {"parcelas": 2}})
        self.assertEqual(sum(p["valor"] for p in v["parcelas"]), 36250)
        self.assertEqual(v["cliente_id"], self.cliente["id"])

    def test_orcamento_vencido(self):
        o = self.orcar([(self.cimento, "1")], validade_dias=5)
        self.relogio.avancar(6)
        self.assertTrue(self.loja.obter_orcamento(o["id"])["vencido"])
        with self.assertRaises(LojaError):
            self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "PIX", "valor": "38,90"}]})

    def test_conversao_com_pagamento_errado_nao_converte(self):
        o = self.orcar([(self.cimento, "1")])
        with self.assertRaises(LojaError):
            self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "PIX", "valor": "30"}]})
        self.assertEqual(self.loja.obter_orcamento(o["id"])["status"], "ABERTO")
        self.assertEqual(self.loja.listar_vendas(), [])

    def test_cancelar(self):
        o = self.orcar([(self.cimento, "1")])
        self.loja.cancelar_orcamento(o["id"])
        with self.assertRaises(LojaError):
            self.loja.converter_orcamento(o["id"], {"pagamentos": [{"forma": "PIX", "valor": "38,90"}]})
        with self.assertRaises(LojaError):
            self.loja.cancelar_orcamento(o["id"])


class TestRelatorios(BaseLoja):
    def test_relatorio_de_vendas(self):
        self.vender([(self.cimento, "10")], [("DINHEIRO", "400")])                         # 389,00
        self.vender([(self.areia, "2")], [("PIX", "280")], desconto="10")                  # 280,00
        v3 = self.vender([(self.fio, "100")], [("CREDIARIO", "239")], cliente_id=self.cliente["id"])
        self.loja.registrar_devolucao(v3["id"], {"itens": [{"item_id": v3["itens"][0]["id"], "quantidade": "20"}]})
        v4 = self.vender([(self.cimento, "1")], [("DEBITO", "38,90")])
        self.loja.cancelar_venda(v4["id"], "teste")
        self.loja.receber_do_cliente(self.cliente["id"], "50", "PIX")

        r = self.loja.relatorio_vendas()
        self.assertEqual(r["quantidade"], 3)
        self.assertEqual(r["bruto"], 38900 + 29000 + 23900)
        self.assertEqual(r["descontos"], 1000)
        self.assertEqual(r["total"], 38900 + 28000 + 23900)
        self.assertEqual(r["devolucoes"], 4780)
        self.assertEqual(r["liquido"], 38900 + 28000 + 23900 - 4780)
        custo = 10 * 2950 + 2 * 9000 + 80 * 110
        self.assertEqual(r["custo_mercadorias"], custo)
        self.assertEqual(r["lucro_bruto"], r["liquido"] - custo)
        self.assertEqual(r["por_forma"], {"CREDIARIO": 23900, "DINHEIRO": 38900, "PIX": 28000})
        self.assertEqual(r["canceladas"], 1)
        self.assertEqual(r["recebimentos_crediario"], 5000)
        self.assertEqual(r["ticket_medio"], (38900 + 28000 + 23900) // 3)

        mais = self.loja.mais_vendidos()
        self.assertEqual([m["codigo"] for m in mais], ["CIM50", "AREIA", "FIO25"])
        self.assertEqual(mais[2]["quantidade"], 80000)

    def test_relatorio_por_periodo(self):
        self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        self.relogio.avancar(1)
        self.vender([(self.cimento, "2")], [("PIX", "77,80")])
        self.assertEqual(self.loja.relatorio_vendas("2026-03-10", "2026-03-10")["total"], 3890)
        self.assertEqual(self.loja.relatorio_vendas("2026-03-11", "2026-03-11")["total"], 7780)
        self.assertEqual(self.loja.relatorio_vendas("2026-03-10", "2026-03-11")["total"], 11670)
        with self.assertRaises(LojaError):
            self.loja.relatorio_vendas("2026-03-11", "2026-03-10")

    def test_relatorio_estoque(self):
        r = self.loja.relatorio_estoque()
        self.assertEqual(r["valor_custo"], 100 * 2950 + 30500 * 9000 // 1000 + 500 * 110)
        self.assertEqual(r["valor_venda"], 100 * 3890 + 30500 * 14500 // 1000 + 500 * 239)

    def test_painel(self):
        self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        p = self.loja.painel()
        self.assertEqual(p["vendas_hoje"]["total"], 3890)
        self.assertIsNotNone(p["caixa"])
        self.assertEqual(p["estoque_baixo"], 0)


class TestIntegridade(BaseLoja):
    def test_detecta_adulteracao(self):
        """A conferência precisa apontar dados mexidos por fora do sistema."""
        v = self.vender([(self.cimento, "2")], [("CREDIARIO", "77,80")], cliente_id=self.cliente["id"])
        self.assertEqual(self.loja.verificar_integridade(), [])
        conn = self.loja.conn
        conn.execute("UPDATE produtos SET estoque = estoque + 1000 WHERE id = ?", (self.cimento["id"],))
        conn.execute("UPDATE vendas SET subtotal = subtotal + 100, total = total + 100 WHERE id = ?", (v["id"],))
        conn.execute("UPDATE contas_receber SET valor_pago = 100 WHERE venda_id = ?", (v["id"],))
        problemas = self.loja.verificar_integridade()
        textos = " | ".join(problemas)
        self.assertIn("estoque", textos)
        self.assertIn("soma dos itens", textos)
        self.assertIn("pagamentos não fecham", textos)
        self.assertIn("recebimentos", textos)
        # desfaz para o tearDown
        conn.execute("UPDATE produtos SET estoque = estoque - 1000 WHERE id = ?", (self.cimento["id"],))
        conn.execute("UPDATE vendas SET subtotal = subtotal - 100, total = total - 100 WHERE id = ?", (v["id"],))
        conn.execute("UPDATE contas_receber SET valor_pago = 0 WHERE venda_id = ?", (v["id"],))

    def test_banco_recusa_estoque_negativo_mesmo_por_fora(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.loja.conn.execute("UPDATE produtos SET estoque = -1 WHERE id = ?", (self.cimento["id"],))
        with self.assertRaises(sqlite3.IntegrityError):
            self.loja.conn.execute("INSERT INTO caixa_sessoes (abertura, valor_inicial, status) VALUES ('x', 0, 'ABERTO')")


class TestPersistencia(BaseLoja):
    def test_dados_sobrevivem_reinicio(self):
        import os
        import tempfile
        from loja import Loja
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "loja.db")
            a = Loja(caminho, hoje=self.relogio)
            a.abrir_caixa("10")
            p = a.cadastrar_produto({"nome": "Telha", "unidade": "UN", "preco_venda": "3,50", "estoque_inicial": "200"})
            a.registrar_venda({"itens": [{"produto_id": p["id"], "quantidade": "40"}],
                               "pagamentos": [{"forma": "DINHEIRO", "valor": "140"}]})
            a.backup(os.path.join(pasta, "copia.db"))
            a.fechar()
            for arquivo in ("loja.db", "copia.db"):
                b = Loja(os.path.join(pasta, arquivo), hoje=self.relogio)
                self.assertEqual(b.obter_produto(p["id"])["estoque"], 160000)
                self.assertEqual(b.caixa_atual()["saldo_dinheiro"], 1000 + 14000)
                self.assertEqual(b.verificar_integridade(), [])
                b.fechar()
