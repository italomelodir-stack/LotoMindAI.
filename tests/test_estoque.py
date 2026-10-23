from loja.valores import LojaError, NaoEncontrado
from tests.base import BaseLoja


class TestProdutos(BaseLoja):
    def test_cadastro_com_estoque_inicial(self):
        self.assertEqual(self.cimento["estoque"], 100000)
        self.assertEqual(self.cimento["preco_venda"], 3890)
        self.assertEqual(self.areia["estoque"], 30500)
        movs = self.loja.listar_movimentos(self.cimento["id"])
        self.assertEqual(len(movs), 1)
        self.assertEqual(movs[0]["tipo"], "ESTOQUE_INICIAL")

    def test_codigo_automatico_e_duplicado(self):
        p = self.loja.cadastrar_produto({"nome": "Prego 17x21", "unidade": "KG", "preco_venda": "18"})
        self.assertTrue(p["codigo"].startswith("P"))
        with self.assertRaises(LojaError):
            self.loja.cadastrar_produto({"codigo": "CIM50", "nome": "x", "unidade": "UN", "preco_venda": "1"})
        with self.assertRaises(LojaError):
            self.loja.cadastrar_produto({"nome": "x", "unidade": "UN", "preco_venda": "1",
                                         "codigo_barras": "7891234567890"})

    def test_validacoes(self):
        base = {"nome": "Tijolo", "unidade": "UN", "preco_venda": "1,20"}
        for ruim in [{"nome": ""}, {"unidade": "XX"}, {"preco_venda": "0"}, {"preco_venda": "-3"},
                     {"estoque_inicial": "2,5"}, {"preco_custo": "abc"}]:
            with self.subTest(ruim=ruim):
                with self.assertRaises(LojaError):
                    self.loja.cadastrar_produto({**base, **ruim})

    def test_busca_por_codigo_e_barras(self):
        self.assertEqual(self.loja.buscar_produto_por_codigo("CIM50")["id"], self.cimento["id"])
        self.assertEqual(self.loja.buscar_produto_por_codigo("7891234567890")["id"], self.cimento["id"])
        with self.assertRaises(NaoEncontrado):
            self.loja.buscar_produto_por_codigo("nada")
        self.assertEqual(len(self.loja.listar_produtos("cimento")), 1)

    def test_editar_nao_altera_estoque(self):
        with self.assertRaises(LojaError):
            self.loja.atualizar_produto(self.cimento["id"], {"estoque": 999})
        p = self.loja.atualizar_produto(self.cimento["id"], {"preco_venda": "41,00", "nome": "Cimento CP-II"})
        self.assertEqual(p["preco_venda"], 4100)
        self.assertEqual(p["estoque"], 100000)

    def test_nao_muda_unidade_inteira_com_estoque_fracionado(self):
        with self.assertRaises(LojaError):
            self.loja.atualizar_produto(self.areia["id"], {"unidade": "UN"})

    def test_produto_inativo_nao_vende(self):
        self.loja.atualizar_produto(self.fio["id"], {"ativo": False})
        with self.assertRaises(LojaError):
            self.vender([(self.fio, "1")], [("DINHEIRO", "10")])


class TestMovimentacao(BaseLoja):
    def test_venda_baixa_estoque(self):
        self.vender([(self.cimento, "3"), (self.areia, "1,5")], [("PIX", "334,20")])
        self.assertEqual(self.estoque(self.cimento), 97000)
        self.assertEqual(self.estoque(self.areia), 29000)

    def test_nao_vende_mais_que_o_estoque(self):
        with self.assertRaises(LojaError) as ctx:
            self.vender([(self.cimento, "101")], [("PIX", "3928,90")])
        self.assertIn("Estoque insuficiente", str(ctx.exception))
        self.assertEqual(self.estoque(self.cimento), 100000)

    def test_falha_no_segundo_item_desfaz_tudo(self):
        caixa_antes = self.loja.caixa_atual()["movimentos"]
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "10"), (self.areia, "31")], [("DINHEIRO", "9999")])
        self.assertEqual(self.estoque(self.cimento), 100000)
        self.assertEqual(self.estoque(self.areia), 30500)
        self.assertEqual(self.loja.listar_vendas(), [])
        self.assertEqual(self.loja.caixa_atual()["movimentos"], caixa_antes)

    def test_mesmo_produto_em_duas_linhas_soma_no_estoque(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "60"), (self.cimento, "50")], [("PIX", "4279")])
        self.assertEqual(self.estoque(self.cimento), 100000)
        self.vender([(self.cimento, "60"), (self.cimento, "40")], [("PIX", "3890")])
        self.assertEqual(self.estoque(self.cimento), 0)

    def test_vende_todo_o_estoque_e_zera(self):
        self.vender([(self.areia, "30,5")], [("PIX", "4422,50")])
        self.assertEqual(self.estoque(self.areia), 0)
        with self.assertRaises(LojaError):
            self.vender([(self.areia, "0,001")], [("PIX", "0,15")])

    def test_unidade_inteira_nao_aceita_fracao(self):
        with self.assertRaises(LojaError):
            self.vender([(self.cimento, "1,5")], [("PIX", "58,35")])

    def test_quantidade_fracionada(self):
        v = self.vender([(self.fio, "12,5")], [("PIX", "29,88")])
        self.assertEqual(v["total"], 2988)   # 12,5 x 2,39 = 29,875 -> 29,88
        self.assertEqual(self.estoque(self.fio), 487500)

    def test_ajuste_de_inventario(self):
        p = self.loja.ajustar_estoque(self.cimento["id"], "97", "Contagem mensal")
        self.assertEqual(p["estoque"], 97000)
        p = self.loja.ajustar_estoque(self.cimento["id"], "105", "Achado no depósito")
        self.assertEqual(p["estoque"], 105000)
        movs = self.loja.listar_movimentos(self.cimento["id"])
        self.assertEqual([m["quantidade"] for m in movs[:2]], [8000, -3000])
        with self.assertRaises(LojaError):
            self.loja.ajustar_estoque(self.cimento["id"], "105", "igual")
        with self.assertRaises(LojaError):
            self.loja.ajustar_estoque(self.cimento["id"], "-1", "negativo")
        with self.assertRaises(LojaError):
            self.loja.ajustar_estoque(self.cimento["id"], "10", "")

    def test_perda(self):
        self.loja.registrar_perda(self.cimento["id"], "2", "Saco rasgado")
        self.assertEqual(self.estoque(self.cimento), 98000)
        with self.assertRaises(LojaError):
            self.loja.registrar_perda(self.cimento["id"], "99", "demais")
        self.assertEqual(self.estoque(self.cimento), 98000)

    def test_estoque_baixo(self):
        self.assertEqual(self.loja.listar_produtos(estoque_baixo=True), [])
        self.vender([(self.cimento, "80")], [("PIX", "3112")])
        baixo = self.loja.listar_produtos(estoque_baixo=True)
        self.assertEqual([p["id"] for p in baixo], [self.cimento["id"]])


class TestCompras(BaseLoja):
    def setUp(self):
        super().setUp()
        self.forn = self.loja.cadastrar_fornecedor({"nome": "Votorantim Distribuidora", "documento": "11.222.333/0001-81"})

    def test_entrada_soma_estoque_e_custo_medio(self):
        # 100 sacos a 29,50 + 100 sacos a 31,50 => custo médio 30,50
        c = self.loja.registrar_compra({"fornecedor_id": self.forn["id"], "nota_fiscal": "123",
                                        "itens": [{"produto_id": self.cimento["id"], "quantidade": "100",
                                                   "custo_unitario": "31,50"}]})
        self.assertEqual(c["total"], 315000)
        p = self.loja.obter_produto(self.cimento["id"])
        self.assertEqual(p["estoque"], 200000)
        self.assertEqual(p["preco_custo"], 3050)

    def test_entrada_gera_contas_a_pagar_parceladas(self):
        c = self.loja.registrar_compra({"fornecedor_id": self.forn["id"], "parcelas": 3,
                                        "primeiro_vencimento": "2026-04-10",
                                        "itens": [{"produto_id": self.fio["id"], "quantidade": "100",
                                                   "custo_unitario": "1,00"}]})
        contas = c["contas"]
        self.assertEqual([x["valor"] for x in contas], [3334, 3333, 3333])
        self.assertEqual(sum(x["valor"] for x in contas), c["total"])
        self.assertEqual([x["vencimento"] for x in contas], ["2026-04-10", "2026-05-10", "2026-06-10"])

    def test_entrada_com_produto_zerado_usa_custo_novo(self):
        self.vender([(self.areia, "30,5")], [("PIX", "4422,50")])
        self.loja.registrar_compra({"fornecedor_id": self.forn["id"], "itens": [
            {"produto_id": self.areia["id"], "quantidade": "10", "custo_unitario": "100"}]})
        self.assertEqual(self.loja.obter_produto(self.areia["id"])["preco_custo"], 10000)

    def test_compra_invalida_nao_grava_nada(self):
        with self.assertRaises(LojaError):
            self.loja.registrar_compra({"fornecedor_id": self.forn["id"], "itens": [
                {"produto_id": self.cimento["id"], "quantidade": "10", "custo_unitario": "30"},
                {"produto_id": self.cimento["id"], "quantidade": "1,5", "custo_unitario": "30"}]})
        self.assertEqual(self.estoque(self.cimento), 100000)
        self.assertEqual(self.loja.listar_compras(), [])
        self.assertEqual(self.loja.listar_contas_pagar(), [])
