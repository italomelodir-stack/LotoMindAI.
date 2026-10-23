from loja.valores import LojaError
from tests.base import BaseLoja


class TestContasReceber(BaseLoja):
    def setUp(self):
        super().setUp()
        self.venda = self.vender([(self.cimento, "10")], [("CREDIARIO", "389")], cliente_id=self.cliente["id"],
                                 crediario={"parcelas": 3})
        self.parcelas = self.venda["parcelas"]

    def test_valores_das_parcelas(self):
        self.assertEqual([p["valor"] for p in self.parcelas], [12967, 12967, 12966])

    def test_pagamento_parcial_e_total(self):
        p = self.parcelas[0]
        r = self.loja.receber_parcela(p["id"], "50", "DINHEIRO")
        self.assertEqual((r["valor_pago"], r["restante"], r["status"]), (5000, 7967, "ABERTA"))
        r = self.loja.receber_parcela(p["id"], "79,67", "PIX")
        self.assertEqual((r["valor_pago"], r["restante"], r["status"]), (12967, 0, "PAGA"))
        self.assertEqual(self.dinheiro_caixa(), 20000 + 5000)
        self.assertEqual(self.loja.caixa_atual()["totais_por_forma"]["PIX"], 7967)
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["saldo_devedor"], 25933)

    def test_nao_recebe_mais_que_o_devido(self):
        p = self.parcelas[0]
        with self.assertRaises(LojaError):
            self.loja.receber_parcela(p["id"], "129,68", "PIX")
        self.loja.receber_parcela(p["id"], "129,67", "PIX")
        with self.assertRaises(LojaError):
            self.loja.receber_parcela(p["id"], "0,01", "PIX")

    def test_forma_invalida_e_valor_zero(self):
        with self.assertRaises(LojaError):
            self.loja.receber_parcela(self.parcelas[0]["id"], "10", "CREDIARIO")
        with self.assertRaises(LojaError):
            self.loja.receber_parcela(self.parcelas[0]["id"], "0", "PIX")

    def test_receber_do_cliente_quita_mais_antigas(self):
        r = self.loja.receber_do_cliente(self.cliente["id"], "200", "DINHEIRO")
        self.assertEqual(r["recebido"], 20000)
        contas = self.loja.listar_contas_receber(self.cliente["id"])
        self.assertEqual([(c["valor_pago"], c["status"]) for c in contas],
                         [(12967, "PAGA"), (7033, "ABERTA"), (0, "ABERTA")])
        self.assertEqual(r["cliente"]["saldo_devedor"], 18900)
        with self.assertRaises(LojaError):
            self.loja.receber_do_cliente(self.cliente["id"], "189,01", "DINHEIRO")
        self.loja.receber_do_cliente(self.cliente["id"], "189,00", "DEBITO")
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["saldo_devedor"], 0)

    def test_vencidas(self):
        self.assertEqual(self.loja.listar_contas_receber(vencidas=True), [])
        self.relogio.avancar(65)
        vencidas = self.loja.listar_contas_receber(vencidas=True)
        self.assertEqual([c["parcela"] for c in vencidas], [1, 2])
        self.assertEqual(self.loja.painel()["receber_vencido"], 25934)

    def test_recebimento_exige_caixa_aberto(self):
        self.loja.fechar_caixa("200")
        with self.assertRaises(LojaError):
            self.loja.receber_parcela(self.parcelas[0]["id"], "10", "PIX")
        self.assertEqual(self.loja.listar_contas_receber(self.cliente["id"])[0]["valor_pago"], 0)
        self.loja.abrir_caixa("0")


class TestContasPagar(BaseLoja):
    def test_lancar_pagar_parcial_e_total(self):
        c = self.loja.lancar_conta_pagar({"descricao": "Energia", "valor": "350,40", "vencimento": "2026-03-15"})
        r = self.loja.pagar_conta(c["id"], "100", "PIX")
        self.assertEqual((r["restante"], r["status"]), (25040, "ABERTA"))
        r = self.loja.pagar_conta(c["id"], "250,40", "BOLETO")
        self.assertEqual(r["status"], "PAGA")
        with self.assertRaises(LojaError):
            self.loja.pagar_conta(c["id"], "1", "PIX")

    def test_pagar_com_dinheiro_do_caixa(self):
        c = self.loja.lancar_conta_pagar({"descricao": "Frete", "valor": "80", "vencimento": "2026-03-10"})
        self.loja.pagar_conta(c["id"], "80", "DINHEIRO_CAIXA")
        self.assertEqual(self.dinheiro_caixa(), 12000)
        c2 = self.loja.lancar_conta_pagar({"descricao": "Grande", "valor": "500", "vencimento": "2026-03-10"})
        with self.assertRaises(LojaError):
            self.loja.pagar_conta(c2["id"], "500", "DINHEIRO_CAIXA")
        self.assertEqual(self.dinheiro_caixa(), 12000)

    def test_cancelar(self):
        c = self.loja.lancar_conta_pagar({"descricao": "Aluguel", "valor": "1500", "vencimento": "2026-04-05"})
        self.loja.cancelar_conta_pagar(c["id"])
        with self.assertRaises(LojaError):
            self.loja.pagar_conta(c["id"], "1", "PIX")
        c2 = self.loja.lancar_conta_pagar({"descricao": "Água", "valor": "90", "vencimento": "2026-04-05"})
        self.loja.pagar_conta(c2["id"], "10", "PIX")
        with self.assertRaises(LojaError):
            self.loja.cancelar_conta_pagar(c2["id"])

    def test_validacoes(self):
        for dados in [{"descricao": "", "valor": "1", "vencimento": "2026-04-05"},
                      {"descricao": "x", "valor": "0", "vencimento": "2026-04-05"},
                      {"descricao": "x", "valor": "1", "vencimento": "05/04/2026"}]:
            with self.assertRaises(LojaError):
                self.loja.lancar_conta_pagar(dados)


class TestCaixa(BaseLoja):
    def test_um_caixa_por_vez(self):
        with self.assertRaises(LojaError):
            self.loja.abrir_caixa("0")

    def test_fechamento_confere(self):
        self.vender([(self.cimento, "3")], [("DINHEIRO", "150")])          # +116,70
        self.vender([(self.cimento, "1")], [("PIX", "38,90")])             # não é dinheiro
        self.loja.suprimento("50", "troco")                                # +50
        self.loja.sangria("100", "cofre")                                  # -100
        s = self.loja.fechar_caixa("266,70")
        self.assertEqual(s["valor_esperado"], 20000 + 11670 + 5000 - 10000)
        self.assertEqual(s["diferenca"], 0)
        self.assertEqual(s["status"], "FECHADO")
        self.loja.abrir_caixa("0")

    def test_fechamento_com_falta(self):
        s = self.loja.fechar_caixa("190")
        self.assertEqual(s["diferenca"], -1000)
        s2 = self.loja.abrir_caixa("100")
        self.assertNotEqual(s2["id"], s["id"])

    def test_sangria_maior_que_saldo(self):
        with self.assertRaises(LojaError):
            self.loja.sangria("200,01")
        self.loja.sangria("200")
        self.assertEqual(self.dinheiro_caixa(), 0)

    def test_troco_precisa_de_dinheiro_mas_nao_bloqueia_a_venda(self):
        # o troco sai do dinheiro que o próprio cliente entregou
        self.loja.sangria("200")
        v = self.vender([(self.cimento, "1")], [("DINHEIRO", "50")])
        self.assertEqual(v["troco"], 1110)
        self.assertEqual(self.dinheiro_caixa(), 3890)
