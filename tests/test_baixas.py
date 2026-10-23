"""Baixa na conta do cliente: tudo de uma vez, só algumas compras/parcelas ou só parte do valor."""
import os
import sqlite3
import tempfile

from loja import Loja
from loja.valores import LojaError
from tests.base import BaseLoja


class TestBaixas(BaseLoja):
    def setUp(self):
        super().setUp()
        # compra 1: 10 sacos de cimento (389,00) em 2x  |  compra 2: 100 m de fio (239,00) em 1x
        self.v1 = self.vender([(self.cimento, "10")], [("CREDIARIO", "389")], cliente_id=self.cliente["id"],
                              crediario={"parcelas": 2})
        self.relogio.avancar(1)
        self.v2 = self.vender([(self.fio, "100")], [("CREDIARIO", "239")], cliente_id=self.cliente["id"])
        self.cid = self.cliente["id"]

    def saldo(self):
        return self.loja.obter_cliente(self.cid)["saldo_devedor"]

    def test_debitos_agrupados_por_compra(self):
        debitos = self.loja.debitos_cliente(self.cid)
        self.assertEqual([d["venda_id"] for d in debitos], [self.v1["id"], self.v2["id"]])
        self.assertEqual([d["restante"] for d in debitos], [38900, 23900])
        self.assertEqual(debitos[0]["produtos"][0]["descricao"], "Cimento CP-II 50kg")
        self.assertEqual(len(debitos[0]["parcelas"]), 2)

    def test_quitar_tudo_de_uma_vez(self):
        b = self.loja.receber_conta_cliente(self.cid, {"forma": "PIX"})
        self.assertEqual(b["valor"], 62800)
        self.assertEqual((b["saldo_anterior"], b["saldo_apos"]), (62800, 0))
        self.assertEqual(len(b["itens"]), 3)
        self.assertEqual(self.saldo(), 0)
        self.assertEqual(self.loja.debitos_cliente(self.cid), [])
        with self.assertRaises(LojaError):
            self.loja.receber_conta_cliente(self.cid, {"forma": "PIX"})

    def test_pagar_metade_abate_das_mais_antigas(self):
        b = self.loja.receber_conta_cliente(self.cid, {"valor": "314,00", "forma": "DINHEIRO"})
        self.assertEqual(b["saldo_apos"], 31400)
        self.assertEqual(self.saldo(), 31400)
        contas = self.loja.listar_contas_receber(self.cid)
        # parcela 1 da compra 1 vence antes; depois a da compra 2 (vence 1 dia depois da 1ª); depois a parcela 2
        pagos = {(c["venda_id"], c["parcela"]): (c["valor_pago"], c["status"]) for c in contas}
        self.assertEqual(pagos[(self.v1["id"], 1)], (19450, "PAGA"))
        self.assertEqual(pagos[(self.v2["id"], 1)], (11950, "ABERTA"))
        self.assertEqual(pagos[(self.v1["id"], 2)], (0, "ABERTA"))
        self.assertEqual(self.dinheiro_caixa(), 20000 + 31400)

    def test_quitar_so_uma_compra(self):
        ids = [p["id"] for p in self.v2["parcelas"]]
        b = self.loja.receber_conta_cliente(self.cid, {"contas": ids, "forma": "DEBITO"})
        self.assertEqual(b["valor"], 23900)
        self.assertEqual(self.saldo(), 38900)
        self.assertEqual([d["venda_id"] for d in self.loja.debitos_cliente(self.cid)], [self.v1["id"]])

    def test_parte_de_uma_compra_escolhida(self):
        ids = [p["id"] for p in self.v1["parcelas"]]
        b = self.loja.receber_conta_cliente(self.cid, {"contas": ids, "valor": "250", "forma": "PIX"})
        self.assertEqual([i["valor"] for i in b["itens"]], [19450, 5550])
        # a compra 2 não foi tocada
        self.assertEqual(self.loja.obter_venda(self.v2["id"])["parcelas"][0]["valor_pago"], 0)
        self.assertEqual(self.saldo(), 62800 - 25000)

    def test_valor_acima_do_escolhido(self):
        ids = [self.v2["parcelas"][0]["id"]]
        with self.assertRaises(LojaError) as ctx:
            self.loja.receber_conta_cliente(self.cid, {"contas": ids, "valor": "239,01", "forma": "PIX"})
        self.assertIn("R$ 239,00", str(ctx.exception))
        self.assertEqual(self.saldo(), 62800)

    def test_parcela_de_outro_cliente_ou_ja_paga(self):
        outro = self.loja.cadastrar_cliente({"nome": "Outro", "limite_credito": "500"})
        vo = self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=outro["id"])
        with self.assertRaises(LojaError):
            self.loja.receber_conta_cliente(self.cid, {"contas": [vo["parcelas"][0]["id"]], "forma": "PIX"})
        pid = self.v2["parcelas"][0]["id"]
        self.loja.receber_conta_cliente(self.cid, {"contas": [pid], "forma": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.receber_conta_cliente(self.cid, {"contas": [pid], "forma": "PIX"})
        for ruim in ["1,2", [None], ["abc"], {"x": 1}]:
            with self.assertRaises(LojaError):
                self.loja.receber_conta_cliente(self.cid, {"contas": ruim, "forma": "PIX"})

    def test_troco_em_dinheiro(self):
        b = self.loja.receber_conta_cliente(self.cid, {"valor": "150", "valor_recebido": "200", "forma": "DINHEIRO"})
        self.assertEqual((b["valor"], b["valor_recebido"], b["troco"]), (15000, 20000, 5000))
        self.assertEqual(self.dinheiro_caixa(), 20000 + 15000)   # no caixa fica só o que abateu da conta
        self.assertEqual(self.saldo(), 62800 - 15000)

    def test_troco_so_em_dinheiro_e_entregue_menor(self):
        with self.assertRaises(LojaError):
            self.loja.receber_conta_cliente(self.cid, {"valor": "150", "valor_recebido": "200", "forma": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.receber_conta_cliente(self.cid, {"valor": "150", "valor_recebido": "100", "forma": "DINHEIRO"})
        self.assertEqual(self.saldo(), 62800)

    def test_valores_invalidos(self):
        for dados in [{"valor": "0"}, {"valor": "-10"}, {"valor": "abc"}, {"forma": "CREDIARIO"}, {"forma": "BOLETO"}]:
            with self.subTest(dados=dados):
                with self.assertRaises(LojaError):
                    self.loja.receber_conta_cliente(self.cid, {"forma": "PIX", **dados})
        self.assertEqual(self.saldo(), 62800)

    def test_exige_caixa_aberto(self):
        self.loja.fechar_caixa("200")
        with self.assertRaises(LojaError):
            self.loja.receber_conta_cliente(self.cid, {"forma": "PIX"})
        self.loja.abrir_caixa("200")
        self.assertEqual(self.saldo(), 62800)

    def test_pagamento_libera_limite_e_desbloqueia_atraso(self):
        self.relogio.avancar(40)
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=self.cid)
        vencidas = [c["id"] for c in self.loja.listar_contas_receber(self.cid, vencidas=True)]
        self.loja.receber_conta_cliente(self.cid, {"contas": vencidas, "forma": "PIX"})
        self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=self.cid)

    def test_historico_e_extrato(self):
        self.loja.receber_conta_cliente(self.cid, {"valor": "100", "forma": "PIX"})
        self.loja.receber_conta_cliente(self.cid, {"valor": "50", "forma": "DINHEIRO", "observacao": "pagou no balcão"})
        baixas = self.loja.listar_baixas(cliente_id=self.cid)
        self.assertEqual([b["valor"] for b in baixas], [5000, 10000])
        self.assertEqual(baixas[0]["observacao"], "pagou no balcão")
        self.assertEqual(len(self.loja.extrato_cliente(self.cid)["baixas"]), 2)
        self.assertEqual(self.loja.relatorio_vendas("2026-03-01", "2026-03-31")["recebimentos_crediario"], 15000)


class TestEstorno(BaseLoja):
    def setUp(self):
        super().setUp()
        self.venda = self.vender([(self.cimento, "10")], [("CREDIARIO", "389")], cliente_id=self.cliente["id"],
                                 crediario={"parcelas": 2})
        self.cid = self.cliente["id"]

    def test_estorno_devolve_a_divida_e_tira_do_caixa(self):
        b = self.loja.receber_conta_cliente(self.cid, {"valor": "300", "forma": "DINHEIRO"})
        self.assertEqual(self.dinheiro_caixa(), 50000)
        e = self.loja.estornar_baixa(b["id"], "lancei no cliente errado")
        self.assertEqual(e["status"], "ESTORNADA")
        self.assertEqual(self.dinheiro_caixa(), 20000)
        self.assertEqual(self.loja.obter_cliente(self.cid)["saldo_devedor"], 38900)
        self.assertTrue(all(p["valor_pago"] == 0 and p["status"] == "ABERTA"
                            for p in self.loja.obter_venda(self.venda["id"])["parcelas"]))
        self.assertEqual(self.loja.relatorio_vendas()["recebimentos_crediario"], 0)
        with self.assertRaises(LojaError):
            self.loja.estornar_baixa(b["id"], "de novo")
        # depois do estorno dá para receber normalmente
        self.loja.receber_conta_cliente(self.cid, {"forma": "PIX"})
        self.assertEqual(self.loja.obter_cliente(self.cid)["saldo_devedor"], 0)

    def test_estorno_pix_nao_mexe_no_dinheiro(self):
        b = self.loja.receber_conta_cliente(self.cid, {"forma": "PIX"})
        self.loja.estornar_baixa(b["id"], "PIX não caiu")
        self.assertEqual(self.dinheiro_caixa(), 20000)
        self.assertEqual(self.loja.caixa_atual()["totais_por_forma"].get("PIX"), 0)

    def test_estorno_exige_motivo_e_dinheiro_no_caixa(self):
        b = self.loja.receber_conta_cliente(self.cid, {"valor": "100", "forma": "DINHEIRO"})
        with self.assertRaises(LojaError):
            self.loja.estornar_baixa(b["id"], "")
        self.loja.sangria("250")
        with self.assertRaises(LojaError):
            self.loja.estornar_baixa(b["id"], "engano")
        self.assertEqual(self.loja.obter_baixa(b["id"])["status"], "ATIVA")
        self.assertEqual(self.loja.obter_cliente(self.cid)["saldo_devedor"], 28900)

    def test_nao_estorna_se_houve_devolucao_depois(self):
        b = self.loja.receber_conta_cliente(self.cid, {"forma": "PIX"})
        self.loja.registrar_devolucao(self.venda["id"], {"itens": [{"item_id": self.venda["itens"][0]["id"],
                                                                    "quantidade": "1"}], "forma_reembolso": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.estornar_baixa(b["id"], "engano")

    def test_venda_com_baixa_estornada_pode_ser_cancelada(self):
        b = self.loja.receber_conta_cliente(self.cid, {"valor": "10", "forma": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.cancelar_venda(self.venda["id"], "x")
        self.loja.estornar_baixa(b["id"], "engano")
        self.loja.cancelar_venda(self.venda["id"], "cliente desistiu")
        self.assertEqual(self.loja.obter_cliente(self.cid)["saldo_devedor"], 0)


class TestMigracao(BaseLoja):
    def test_banco_da_versao_anterior_e_atualizado(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "antigo.db")
            a = Loja(caminho, hoje=self.relogio)
            a.abrir_caixa("0")
            p = a.cadastrar_produto({"nome": "Cal", "unidade": "SC", "preco_venda": "12", "estoque_inicial": "10"})
            c = a.cadastrar_cliente({"nome": "Antigo", "limite_credito": "100"})
            v = a.registrar_venda({"itens": [{"produto_id": p["id"], "quantidade": "2"}], "cliente_id": c["id"],
                                   "pagamentos": [{"forma": "CREDIARIO", "valor": "24"}]})
            a.fechar()
            # volta a tabela de recebimentos ao formato antigo, com um recebimento já lançado
            con = sqlite3.connect(caminho)
            con.executescript(f"""
                DROP TABLE recebimentos;
                CREATE TABLE recebimentos (id INTEGER PRIMARY KEY AUTOINCREMENT, conta_id INTEGER NOT NULL,
                    data TEXT NOT NULL, valor INTEGER NOT NULL CHECK (valor > 0), forma TEXT NOT NULL,
                    caixa_sessao_id INTEGER);
                INSERT INTO recebimentos (conta_id, data, valor, forma, caixa_sessao_id)
                    VALUES ({v['parcelas'][0]['id']}, '2026-03-10 10:00:00', 400, 'PIX', 1);
                UPDATE contas_receber SET valor_pago = 400;
                INSERT INTO caixa_movimentos (sessao_id, data, tipo, forma, valor, referencia)
                    VALUES (1, '2026-03-10 10:00:00', 'RECEBIMENTO', 'PIX', 400, 'conta_receber:{v['parcelas'][0]['id']}');
            """)
            con.close()
            b = Loja(caminho, hoje=self.relogio)
            self.assertEqual(b.verificar_integridade(), [])
            baixa = b.receber_conta_cliente(c["id"], {"forma": "DINHEIRO"})
            self.assertEqual(baixa["valor"], 2000)
            self.assertEqual(b.obter_cliente(c["id"])["saldo_devedor"], 0)
            self.assertEqual(b.verificar_integridade(), [])
            b.fechar()
