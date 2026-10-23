import datetime
import unittest

from loja import Loja


class Relogio:
    """Data controlável, para testar vencimentos e atrasos."""

    def __init__(self, data=datetime.date(2026, 3, 10)):
        self.data = data

    def __call__(self):
        return self.data

    def avancar(self, dias):
        self.data += datetime.timedelta(days=dias)


class BaseLoja(unittest.TestCase):
    def setUp(self):
        self.relogio = Relogio()
        self.loja = Loja(":memory:", hoje=self.relogio)
        self.loja.abrir_caixa("200,00", "Teste")
        self.cimento = self.loja.cadastrar_produto({
            "codigo": "CIM50", "codigo_barras": "7891234567890", "nome": "Cimento CP-II 50kg",
            "categoria": "Cimento", "unidade": "SC", "preco_custo": "29,50", "preco_venda": "38,90",
            "estoque_inicial": "100", "estoque_minimo": "20"})
        self.areia = self.loja.cadastrar_produto({
            "codigo": "AREIA", "nome": "Areia média", "categoria": "Agregados", "unidade": "M3",
            "preco_custo": "90", "preco_venda": "145,00", "estoque_inicial": "30,5"})
        self.fio = self.loja.cadastrar_produto({
            "codigo": "FIO25", "nome": "Fio flexível 2,5mm", "categoria": "Elétrica", "unidade": "M",
            "preco_custo": "1,10", "preco_venda": "2,39", "estoque_inicial": "500"})
        self.cliente = self.loja.cadastrar_cliente({
            "nome": "José da Obra", "documento": "529.982.247-25", "telefone": "(11) 99999-0000",
            "limite_credito": "2.000,00"})

    def tearDown(self):
        problemas = self.loja.verificar_integridade()
        self.loja.fechar()
        self.assertEqual(problemas, [], "Inconsistência nos dados ao final do teste")

    def estoque(self, produto):
        return self.loja.obter_produto(produto["id"])["estoque"]

    def dinheiro_caixa(self):
        return self.loja.caixa_atual()["saldo_dinheiro"]

    def vender(self, itens, pagamentos, **extra):
        dados = {"itens": [{"produto_id": p["id"], "quantidade": q} for p, q in itens],
                 "pagamentos": [{"forma": f, "valor": v} for f, v in pagamentos]}
        dados.update(extra)
        return self.loja.registrar_venda(dados)
