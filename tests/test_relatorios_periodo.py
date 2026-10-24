"""Relatórios por período: mês a mês, por categoria, por cliente e histórico de cada cliente."""
import datetime

from loja.valores import LojaError
from tests.base import BaseLoja


class TestRelatoriosPeriodo(BaseLoja):
    def setUp(self):
        super().setUp()
        L = self.loja
        self.registro = L.cadastrar_produto({"codigo": "REG", "nome": "Registro 3/4", "categoria": "Hidráulica", "unidade": "UN",
                                             "preco_custo": "20", "preco_venda": "33,33", "estoque_inicial": "50"})
        self.avulso = L.cadastrar_produto({"codigo": "AVU", "nome": "Item avulso", "unidade": "UN",
                                           "preco_custo": "5", "preco_venda": "12", "estoque_inicial": "50"})
        self.maria = L.cadastrar_cliente({"nome": "Maria Souza", "limite_credito": "500"})
        jose = self.cliente["id"]
        # março (10/03)
        self.v1 = self.vender([(self.cimento, "10")], [("PIX", "389")], cliente_id=jose)                    # 389,00 Cimento
        self.v2 = self.vender([(self.fio, "100")], [("DINHEIRO", "239")])                                   # 239,00 Elétrica, sem cliente
        self.v3 = self.vender([(self.registro, "2")], [("CREDIARIO", "66,66")], cliente_id=jose)            # 66,66 Hidráulica
        # abril (10/04)
        self.relogio.avancar(31)
        self.v4 = self.vender([(self.areia, "2")], [("DEBITO", "280")], cliente_id=self.maria["id"], desconto="10")  # 280,00
        self.v5 = self.vender([(self.fio, "50"), (self.cimento, "1")], [("PIX", "158,40")], cliente_id=jose)  # 119,50 + 38,90
        fio_v5 = self.v5["itens"][0]
        self.loja.registrar_devolucao(self.v5["id"], {"itens": [{"item_id": fio_v5["id"], "quantidade": "10"}],
                                                      "forma_reembolso": "PIX"})                               # -23,90 Elétrica
        self.loja.receber_conta_cliente(jose, {"valor": "30", "forma": "PIX"})
        # maio: nada  |  junho (15/06)
        self.relogio.data = datetime.date(2026, 6, 15)
        self.v6 = self.vender([(self.avulso, "3")], [("PIX", "36")])                                         # 36,00 sem categoria
        self.v7 = self.vender([(self.cimento, "5")], [("PIX", "194,50")], cliente_id=jose)
        self.loja.cancelar_venda(self.v7["id"], "desistiu")
        self.jose = jose

    def test_mes_a_mes(self):
        meses = self.loja.vendas_por_mes("2026-03-01", "2026-06-30")
        self.assertEqual([m["mes"] for m in meses], ["2026-03", "2026-04", "2026-05", "2026-06"])
        self.assertEqual([m["liquido"] for m in meses], [38900 + 23900 + 6666, 28000 + 15840 - 2390, 0, 3600])
        self.assertEqual([m["quantidade"] for m in meses], [3, 2, 0, 1])
        self.assertEqual(meses[1]["descontos"], 1000)
        self.assertEqual(meses[1]["devolucoes"], 2390)
        total = self.loja.relatorio_vendas("2026-03-01", "2026-06-30")
        self.assertEqual(sum(m["liquido"] for m in meses), total["liquido"])
        self.assertEqual(sum(m["lucro_bruto"] for m in meses), total["lucro_bruto"])

    def test_mes_parcial_respeita_as_datas(self):
        meses = self.loja.vendas_por_mes("2026-03-15", "2026-04-10")
        self.assertEqual([m["mes"] for m in meses], ["2026-03", "2026-04"])
        self.assertEqual(meses[0]["liquido"], 0)               # as vendas de março foram no dia 10
        self.assertEqual(meses[1]["liquido"], 41450)

    def test_mes_a_mes_sem_inicio_comeca_na_primeira_venda(self):
        meses = self.loja.vendas_por_mes()
        self.assertEqual(meses[0]["mes"], "2026-03")
        self.assertEqual(meses[-1]["mes"], "2026-06")

    def test_por_categoria(self):
        cats = {c["categoria"]: c for c in self.loja.vendas_por_categoria("2026-03-01", "2026-06-30")}
        self.assertEqual({k: c["valor"] for k, c in cats.items()},
                         {"Cimento": 38900 + 3890, "Elétrica": 23900 + 11950 - 2390, "Hidráulica": 6666,
                          "Agregados": 28000, "Sem categoria": 3600})
        self.assertEqual(list(cats)[0], "Cimento")              # ordenado do maior para o menor
        eletrica = cats["Elétrica"]
        self.assertEqual(eletrica["vendas"], 2)
        self.assertEqual(eletrica["produtos"][0]["quantidade"], 140000)   # 100 + 50 - 10 devolvidos
        self.assertEqual(eletrica["custo"], 140 * 110)
        self.assertEqual(eletrica["lucro"], eletrica["valor"] - eletrica["custo"])
        total = self.loja.relatorio_vendas("2026-03-01", "2026-06-30")
        self.assertEqual(sum(c["valor"] for c in cats.values()), total["liquido"])
        self.assertEqual(sum(c["custo"] for c in cats.values()), total["custo_mercadorias"])

    def test_categoria_de_um_mes(self):
        cats = self.loja.vendas_por_categoria("2026-06-01", "2026-06-30")
        self.assertEqual([(c["categoria"], c["valor"]) for c in cats], [("Sem categoria", 3600)])

    def test_por_cliente(self):
        clientes = self.loja.vendas_por_cliente("2026-03-01", "2026-06-30")
        resumo = [(c["nome"], c["compras"], c["liquido"]) for c in clientes]
        self.assertEqual(resumo, [("José da Obra", 3, 38900 + 6666 + 15840 - 2390), ("Maria Souza", 1, 28000),
                                  ("Consumidor (venda sem cliente)", 2, 23900 + 3600)])
        jose = clientes[0]
        self.assertEqual(jose["devolvido"], 2390)
        self.assertEqual(jose["saldo_devedor"], 6666 - 3000)
        self.assertEqual(jose["ultima"][:10], "2026-04-10")    # a venda cancelada de junho não conta
        total = self.loja.relatorio_vendas("2026-03-01", "2026-06-30")
        self.assertEqual(sum(c["liquido"] for c in clientes), total["liquido"])

    def test_por_cliente_em_um_mes(self):
        abril = self.loja.vendas_por_cliente("2026-04-01", "2026-04-30")
        self.assertEqual([(c["nome"], c["liquido"]) for c in abril], [("Maria Souza", 28000), ("José da Obra", 13450)])

    def test_historico_do_cliente_todo_periodo(self):
        h = self.loja.historico_cliente(self.jose)
        self.assertEqual((h["inicio"], h["fim"]), ("2026-03-10", "2026-06-15"))
        self.assertEqual(h["resumo"]["liquido"], 59016)
        self.assertEqual(h["resumo"]["quantidade"], 3)
        self.assertEqual(h["pago_crediario"], 3000)
        self.assertEqual([m["liquido"] for m in h["por_mes"]], [45566, 13450, 0, 0])
        self.assertEqual({c["categoria"]: c["valor"] for c in h["por_categoria"]},
                         {"Cimento": 42790, "Elétrica": 9560, "Hidráulica": 6666})
        # a lista de compras mostra também a cancelada, com os itens
        self.assertEqual([(c["id"], c["status"]) for c in h["compras"]],
                         [(self.v7["id"], "CANCELADA"), (self.v5["id"], "CONCLUIDA"), (self.v3["id"], "CONCLUIDA"),
                          (self.v1["id"], "CONCLUIDA")])
        self.assertEqual([i["descricao"] for i in h["compras"][1]["itens"]], ["Fio flexível 2,5mm", "Cimento CP-II 50kg"])
        self.assertEqual(len(h["baixas"]), 1)

    def test_historico_do_cliente_periodo_escolhido(self):
        h = self.loja.historico_cliente(self.jose, "2026-03-01", "2026-03-31")
        self.assertEqual(h["resumo"]["liquido"], 45566)
        self.assertEqual(len(h["compras"]), 2)
        self.assertEqual(h["pago_crediario"], 0)
        h = self.loja.historico_cliente(self.maria["id"], "2026-05-01", "2026-05-31")
        self.assertEqual((h["resumo"]["liquido"], h["compras"], h["por_categoria"]), (0, [], []))

    def test_cliente_sem_compras(self):
        novo = self.loja.cadastrar_cliente({"nome": "Novo"})
        h = self.loja.historico_cliente(novo["id"])
        self.assertEqual(h["resumo"]["quantidade"], 0)
        self.assertEqual(len(h["por_mes"]), 1)

    def test_periodo_invalido(self):
        with self.assertRaises(LojaError):
            self.loja.vendas_por_mes("2026-05-01", "2026-04-01")
        with self.assertRaises(LojaError):
            self.loja.vendas_por_categoria("2026-13-01", "2026-04-01")
        with self.assertRaises(LojaError):
            self.loja.historico_cliente(self.jose, "2026-05-01", "2026-04-01")
        with self.assertRaises(LojaError):
            self.loja.vendas_por_mes("1900-01-01", "2026-04-01")
        # o total de um período longo continua funcionando
        self.assertEqual(self.loja.relatorio_vendas("1900-01-01", "2100-12-31")["quantidade"], 6)

    def test_painel_mostra_o_mes(self):
        self.assertEqual(self.loja.painel()["vendas_mes"]["liquido"], 3600)
