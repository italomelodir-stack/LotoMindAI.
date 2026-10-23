from loja.valores import LojaError
from tests.base import BaseLoja


class TestValoresDaVenda(BaseLoja):
    def test_totais(self):
        v = self.vender([(self.cimento, "3"), (self.fio, "10")], [("DINHEIRO", "140,60")])
        self.assertEqual(v["subtotal"], 3 * 3890 + 2390)
        self.assertEqual(v["total"], 14060)
        self.assertEqual(v["troco"], 0)
        self.assertEqual([i["total"] for i in v["itens"]], [11670, 2390])

    def test_troco(self):
        v = self.vender([(self.cimento, "3")], [("DINHEIRO", "150")])
        self.assertEqual(v["total"], 11670)
        self.assertEqual(v["troco"], 3330)
        # no caixa entra só o valor da venda, não o que o cliente entregou
        self.assertEqual(self.dinheiro_caixa(), 20000 + 11670)

    def test_desconto_em_valor_rateado_nos_itens(self):
        v = self.vender([(self.cimento, "3"), (self.fio, "10")], [("PIX", "130,60")], desconto="10")
        self.assertEqual(v["desconto"], 1000)
        self.assertEqual(v["total"], 13060)
        self.assertEqual(sum(i["total_liquido"] for i in v["itens"]), 13060)

    def test_desconto_percentual(self):
        v = self.vender([(self.cimento, "10")], [("PIX", "369,55")], desconto_percentual="5")
        self.assertEqual(v["desconto"], 1945)
        self.assertEqual(v["total"], 36955)

    def test_desconto_invalido(self):
        for extra in [{"desconto": "116,70"}, {"desconto": "200"}, {"desconto_percentual": "100"},
                      {"desconto_percentual": "150"}, {"desconto": "1", "desconto_percentual": "1"},
                      {"desconto": "-5"}]:
            with self.subTest(extra=extra):
                with self.assertRaises(LojaError):
                    self.vender([(self.cimento, "3")], [("DINHEIRO", "200")], **extra)
        self.assertEqual(self.estoque(self.cimento), 100000)

    def test_pagamento_misto(self):
        v = self.vender([(self.cimento, "10")], [("PIX", "100"), ("DEBITO", "200"), ("DINHEIRO", "100")])
        self.assertEqual(v["total"], 38900)
        self.assertEqual(v["troco"], 1100)
        caixa = self.loja.caixa_atual()
        self.assertEqual(caixa["totais_por_forma"], {"PIX": 10000, "DEBITO": 20000, "DINHEIRO": 8900})

    def test_pagamento_insuficiente(self):
        with self.assertRaises(LojaError) as ctx:
            self.vender([(self.cimento, "3")], [("DINHEIRO", "100")])
        self.assertIn("faltam R$ 16,70", str(ctx.exception))
        self.assertEqual(self.estoque(self.cimento), 100000)

    def test_cartao_acima_do_total_nao_tem_troco(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CREDITO", "50")])
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("PIX", "38,90"), ("DINHEIRO", "10")])

    def test_forma_e_valor_invalidos(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CHEQUE", "38,90")])
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("PIX", "0")])
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [])
        with self.assertRaises(LojaError):
            self.vender([], [("PIX", "1")])

    def test_dados_malformados_sao_recusados_sem_quebrar(self):
        pid = self.cimento["id"]
        ruins = [
            {"itens": "lixo", "pagamentos": [{"forma": "PIX", "valor": "1"}]},
            {"itens": [1, 2], "pagamentos": [{"forma": "PIX", "valor": "1"}]},
            {"itens": [{"produto_id": "abc", "quantidade": "1"}], "pagamentos": [{"forma": "PIX", "valor": "1"}]},
            {"itens": [{"produto_id": pid}], "pagamentos": [{"forma": "PIX", "valor": "38,90"}]},
            {"itens": [{"produto_id": pid, "quantidade": "1"}], "pagamentos": "PIX"},
            {"itens": [{"produto_id": pid, "quantidade": "1"}], "pagamentos": [{"forma": "PIX"}]},
            {"itens": [{"produto_id": pid, "quantidade": "1"}], "pagamentos": [{"forma": "CREDIARIO", "valor": "38,90"}],
             "cliente_id": self.cliente["id"], "crediario": "3x"},
            {"itens": [{"produto_id": pid, "quantidade": "1"}], "pagamentos": [{"forma": "PIX", "valor": "38,90"}],
             "cliente_id": "xyz"},
        ]
        for dados in ruins:
            with self.subTest(dados=dados):
                with self.assertRaises(LojaError):
                    self.loja.registrar_venda(dados)
        self.assertEqual(self.estoque(self.cimento), 100000)
        v = self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        for ruim in ["x", [1], [{"item_id": v["itens"][0]["id"]}], [{"item_id": "a", "quantidade": "1"}]]:
            with self.assertRaises(LojaError):
                self.loja.registrar_devolucao(v["id"], {"itens": ruim})

    def test_caixa_fechado_bloqueia_venda(self):
        self.loja.fechar_caixa("200")
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        self.assertEqual(self.estoque(self.cimento), 100000)
        self.loja.abrir_caixa("0")

    def test_preco_na_venda_fica_registrado(self):
        v = self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        self.loja.atualizar_produto(self.cimento["id"], {"preco_venda": "45"})
        self.assertEqual(self.loja.obter_venda(v["id"])["itens"][0]["preco_unitario"], 3890)


class TestCrediario(BaseLoja):
    def test_parcelas(self):
        v = self.vender([(self.cimento, "10")], [("DINHEIRO", "89"), ("CREDIARIO", "300")],
                        cliente_id=self.cliente["id"], crediario={"parcelas": 3})
        parcelas = v["parcelas"]
        self.assertEqual([p["valor"] for p in parcelas], [10000, 10000, 10000])
        self.assertEqual([p["vencimento"] for p in parcelas], ["2026-04-10", "2026-05-10", "2026-06-10"])
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["saldo_devedor"], 30000)
        self.assertEqual(self.dinheiro_caixa(), 20000 + 8900)

    def test_parcelas_com_centavos_somam_exato(self):
        v = self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")],
                        cliente_id=self.cliente["id"], crediario={"parcelas": 7, "primeiro_vencimento": "2026-03-31"})
        valores = [p["valor"] for p in v["parcelas"]]
        self.assertEqual(sum(valores), 3890)
        self.assertEqual(max(valores) - min(valores), 1)
        self.assertEqual(v["parcelas"][1]["vencimento"], "2026-04-30")

    def test_exige_cliente(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")])

    def test_limite_de_credito(self):
        self.vender([(self.cimento, "50")], [("CREDIARIO", "1945")], cliente_id=self.cliente["id"])
        with self.assertRaises(LojaError) as ctx:
            self.vender([(self.cimento, "2")], [("CREDIARIO", "77,80")], cliente_id=self.cliente["id"])
        self.assertIn("Limite de crédito insuficiente", str(ctx.exception))
        self.assertEqual(self.estoque(self.cimento), 50000)
        # pagando, o limite volta
        conta = self.loja.listar_contas_receber(self.cliente["id"])[0]
        self.loja.receber_parcela(conta["id"], "100", "PIX")
        self.vender([(self.cimento, "2")], [("CREDIARIO", "77,80")], cliente_id=self.cliente["id"])

    def test_cliente_sem_limite(self):
        c = self.loja.cadastrar_cliente({"nome": "Sem crédito"})
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=c["id"])

    def test_cliente_em_atraso_nao_compra_fiado(self):
        self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=self.cliente["id"])
        self.relogio.avancar(40)
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["valor_vencido"], 3890)
        with self.assertRaises(LojaError) as ctx:
            self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=self.cliente["id"])
        self.assertIn("atraso", str(ctx.exception))
        # à vista continua podendo
        self.vender([(self.cimento, "1")], [("PIX", "38,90")], cliente_id=self.cliente["id"])

    def test_vencimento_no_passado(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=self.cliente["id"],
                        crediario={"primeiro_vencimento": "2026-03-01"})

    def test_limite_de_parcelas(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1")], [("CREDIARIO", "38,90")], cliente_id=self.cliente["id"],
                        crediario={"parcelas": 25})


class TestCancelamento(BaseLoja):
    def test_cancelar_devolve_estoque_e_tira_do_caixa(self):
        v = self.vender([(self.cimento, "5"), (self.areia, "2,5")], [("DINHEIRO", "600")])
        self.assertEqual(self.dinheiro_caixa(), 20000 + v["total"])
        self.loja.cancelar_venda(v["id"], "Cliente desistiu")
        self.assertEqual(self.estoque(self.cimento), 100000)
        self.assertEqual(self.estoque(self.areia), 30500)
        self.assertEqual(self.dinheiro_caixa(), 20000)
        self.assertEqual(self.loja.obter_venda(v["id"])["status"], "CANCELADA")
        with self.assertRaises(LojaError):
            self.loja.cancelar_venda(v["id"], "de novo")

    def test_cancelar_crediario_cancela_parcelas(self):
        v = self.vender([(self.cimento, "5")], [("CREDIARIO", "194,50")], cliente_id=self.cliente["id"],
                        crediario={"parcelas": 2})
        self.loja.cancelar_venda(v["id"], "erro de digitação")
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["saldo_devedor"], 0)
        self.assertTrue(all(p["status"] == "CANCELADA" for p in self.loja.obter_venda(v["id"])["parcelas"]))

    def test_nao_cancela_com_parcela_paga(self):
        v = self.vender([(self.cimento, "5")], [("CREDIARIO", "194,50")], cliente_id=self.cliente["id"],
                        crediario={"parcelas": 2})
        self.loja.receber_parcela(v["parcelas"][0]["id"], "10", "DINHEIRO")
        with self.assertRaises(LojaError):
            self.loja.cancelar_venda(v["id"], "x")
        self.assertEqual(self.estoque(self.cimento), 95000)

    def test_exige_motivo(self):
        v = self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        with self.assertRaises(LojaError):
            self.loja.cancelar_venda(v["id"], "")

    def test_cancelada_fora_do_relatorio(self):
        v = self.vender([(self.cimento, "1")], [("PIX", "38,90")])
        self.vender([(self.cimento, "2")], [("PIX", "77,80")])
        self.loja.cancelar_venda(v["id"], "teste")
        r = self.loja.relatorio_vendas()
        self.assertEqual((r["quantidade"], r["total"], r["canceladas"]), (1, 7780, 1))


class TestDevolucao(BaseLoja):
    def test_devolucao_parcial_com_reembolso(self):
        v = self.vender([(self.cimento, "10")], [("DINHEIRO", "389")])
        item = v["itens"][0]
        d = self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": item["id"], "quantidade": "3"}],
                                                    "motivo": "Sobrou na obra"})
        self.assertEqual(d["valor"], 11670)
        self.assertEqual(d["valor_reembolsado"], 11670)
        self.assertEqual(self.estoque(self.cimento), 93000)
        self.assertEqual(self.dinheiro_caixa(), 20000 + 38900 - 11670)

    def test_nao_devolve_mais_que_comprou(self):
        v = self.vender([(self.cimento, "2")], [("PIX", "77,80")])
        item = v["itens"][0]
        self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": item["id"], "quantidade": "1"}],
                                                "forma_reembolso": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": item["id"], "quantidade": "2"}],
                                                    "forma_reembolso": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": 9999, "quantidade": "1"}]})
        self.assertEqual(self.estoque(self.cimento), 99000)

    def test_devolucoes_parciais_com_desconto_fecham_exato(self):
        # 3 sacos com desconto de 10,00: 106,70 líquido. Devolvendo 1 por vez, a soma tem que dar 106,70.
        v = self.vender([(self.cimento, "3")], [("PIX", "106,70")], desconto="10")
        item = v["itens"][0]
        valores = []
        for _ in range(3):
            d = self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": item["id"], "quantidade": "1"}],
                                                        "forma_reembolso": "PIX"})
            valores.append(d["valor"])
        self.assertEqual(sum(valores), 10670)
        self.assertEqual(valores, [3557, 3557, 3556])
        self.assertEqual(self.estoque(self.cimento), 100000)
        r = self.loja.relatorio_vendas()
        self.assertEqual(r["liquido"], 0)
        self.assertEqual(r["custo_mercadorias"], 0)

    def test_devolucao_abate_crediario_antes_de_reembolsar(self):
        v = self.vender([(self.cimento, "10")], [("DINHEIRO", "89"), ("CREDIARIO", "300")],
                        cliente_id=self.cliente["id"], crediario={"parcelas": 3})
        item = v["itens"][0]
        d = self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": item["id"], "quantidade": "4"}]})
        self.assertEqual(d["valor"], 15560)
        self.assertEqual(d["valor_abatido"], 15560)
        self.assertEqual(d["valor_reembolsado"], 0)
        self.assertEqual(self.dinheiro_caixa(), 20000 + 8900)
        parcelas = self.loja.obter_venda(v["id"])["parcelas"]
        self.assertEqual([p["valor"] for p in parcelas], [10000, 4440, 0])
        self.assertEqual([p["status"] for p in parcelas], ["ABERTA", "ABERTA", "CANCELADA"])
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["saldo_devedor"], 14440)

    def test_devolucao_com_parcela_paga_parcialmente(self):
        v = self.vender([(self.cimento, "5")], [("CREDIARIO", "194,50")], cliente_id=self.cliente["id"])
        conta = v["parcelas"][0]
        self.loja.receber_parcela(conta["id"], "150", "DINHEIRO")
        item = v["itens"][0]
        # devolve tudo: 194,50; a dívida restante (44,50) é abatida e 150,00 voltam ao cliente
        d = self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": item["id"], "quantidade": "5"}]})
        self.assertEqual((d["valor_abatido"], d["valor_reembolsado"]), (4450, 15000))
        conta = self.loja.obter_venda(v["id"])["parcelas"][0]
        self.assertEqual((conta["valor"], conta["valor_pago"], conta["status"]), (15000, 15000, "PAGA"))
        self.assertEqual(self.loja.obter_cliente(self.cliente["id"])["saldo_devedor"], 0)
        self.assertEqual(self.dinheiro_caixa(), 20000)

    def test_reembolso_em_dinheiro_exige_dinheiro_no_caixa(self):
        v = self.vender([(self.cimento, "10")], [("PIX", "389")])
        self.loja.sangria("200", "depósito")
        with self.assertRaises(LojaError) as ctx:
            self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": v["itens"][0]["id"], "quantidade": "1"}]})
        self.assertIn("Dinheiro insuficiente", str(ctx.exception))
        self.assertEqual(self.estoque(self.cimento), 90000)
        d = self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": v["itens"][0]["id"], "quantidade": "1"}],
                                                    "forma_reembolso": "PIX"})
        self.assertEqual(d["valor_reembolsado"], 3890)

    def test_venda_com_devolucao_nao_pode_ser_cancelada(self):
        v = self.vender([(self.cimento, "2")], [("PIX", "77,80")])
        self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": v["itens"][0]["id"], "quantidade": "1"}],
                                                "forma_reembolso": "PIX"})
        with self.assertRaises(LojaError):
            self.loja.cancelar_venda(v["id"], "x")

    def test_devolucao_fracionada(self):
        v = self.vender([(self.areia, "2,5")], [("PIX", "362,50")])
        d = self.loja.registrar_devolucao(v["id"], {"itens": [{"item_id": v["itens"][0]["id"], "quantidade": "0,75"}],
                                                    "forma_reembolso": "PIX"})
        self.assertEqual(d["valor"], 10875)
        self.assertEqual(self.estoque(self.areia), 30500 - 2500 + 750)
