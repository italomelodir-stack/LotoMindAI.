"""Simulação de vários dias de loja com operações aleatórias (inclusive erradas de propósito).

Um "livro-caixa paralelo" calculado aqui no teste, de forma independente do sistema,
precisa bater com o sistema depois de cada operação: estoque de cada produto, dinheiro
na gaveta, dívida de cada cliente, contas a pagar e totais das vendas.
"""
import random
import unittest
from decimal import ROUND_HALF_UP, Decimal

from loja import Loja, LojaError
from tests.base import Relogio


def valor_item(preco, qtd):
    return int((Decimal(preco) * qtd / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def reais(c):
    return f"{c // 100},{c % 100:02d}"


def qtd_txt(m):
    return str(Decimal(m) / 1000).replace(".", ",")


class Simulacao(unittest.TestCase):
    OPERACOES = 3000

    SEMENTES = (1, 2, 3)

    def test_simulacao(self):
        for semente in self.SEMENTES:
            with self.subTest(semente=semente):
                self.simular(semente)

    def simular(self, semente):
        rnd = random.Random(semente)
        relogio = Relogio()
        loja = Loja(":memory:", hoje=relogio)
        self.loja = loja
        forn = loja.cadastrar_fornecedor({"nome": "Fornecedor"})

        estoque, produtos = {}, []
        catalogo = [("Cimento", "SC", 3890, 2950), ("Areia", "M3", 14500, 9000), ("Fio 2,5", "M", 239, 110),
                    ("Tijolo", "MIL", 98000, 61000), ("Tinta 18L", "GL", 38990, 24500), ("Prego", "KG", 1890, 1100),
                    ("Tubo PVC 100", "BR", 4590, 2800), ("Piso 60x60", "M2", 5990, 3600), ("Registro", "UN", 3333, 1999)]
        for nome, un, preco, custo in catalogo:
            inicial = rnd.randint(0, 300) * 1000
            p = loja.cadastrar_produto({"nome": nome, "unidade": un, "preco_venda": reais(preco),
                                        "preco_custo": reais(custo), "estoque_inicial": qtd_txt(inicial)})
            produtos.append(p)
            estoque[p["id"]] = inicial
        fracionavel = {p["id"]: p["unidade"] in ("M3", "M", "MIL", "KG", "M2") for p in produtos}

        clientes, divida = [], {}
        for i in range(6):
            c = loja.cadastrar_cliente({"nome": f"Cliente {i}", "limite_credito": reais(rnd.choice([0, 50000, 300000]))})
            clientes.append(c)
            divida[c["id"]] = 0

        estado = {"dinheiro": 0, "caixa_aberto": False, "faturado": 0, "a_pagar": 0}
        vendas = []
        contadores = {"ok": 0, "recusada": 0}

        def abrir():
            fundo = rnd.randint(0, 50000)
            loja.abrir_caixa(reais(fundo))
            estado.update(dinheiro=fundo, caixa_aberto=True)

        abrir()

        def op_venda():
            itens, subtotal, pedido, item_zerado = [], 0, {}, False
            for p in rnd.sample(produtos, rnd.randint(1, 4)):
                q = rnd.randint(1, 40) * 1000
                if fracionavel[p["id"]] and rnd.random() < 0.5:
                    q = rnd.randint(1, 20000)
                itens.append({"produto_id": p["id"], "quantidade": qtd_txt(q)})
                pedido[p["id"]] = pedido.get(p["id"], 0) + q
                subtotal += valor_item(p["preco_venda"], q)
                item_zerado |= valor_item(p["preco_venda"], q) == 0
            desconto = rnd.choice([0, 0, 0, rnd.randint(0, subtotal // 10)])
            total = subtotal - desconto
            cliente = rnd.choice([None] + clientes)
            pagamentos, crediario = [], 0
            tipo = rnd.random()
            if tipo < 0.35:
                entregue = total + rnd.choice([0, rnd.randint(0, 10000)])
                pagamentos = [{"forma": "DINHEIRO", "valor": reais(entregue)}]
            elif tipo < 0.6:
                pagamentos = [{"forma": rnd.choice(["PIX", "DEBITO", "CREDITO"]), "valor": reais(total)}]
            elif tipo < 0.8 and cliente:
                entrada = rnd.randint(0, total // 2)
                crediario = total - entrada
                pagamentos = [{"forma": "CREDIARIO", "valor": reais(crediario)}]
                if entrada:
                    pagamentos.append({"forma": "DINHEIRO", "valor": reais(entrada)})
            else:
                parte = rnd.randint(1, max(1, total - 1))
                pagamentos = [{"forma": "PIX", "valor": reais(parte)}, {"forma": "DINHEIRO", "valor": reais(total - parte)}]
            if rnd.random() < 0.05:  # erro proposital: paga menos
                pagamentos = [{"forma": "PIX", "valor": reais(max(1, total - 1))}]
            dados = {"itens": itens, "pagamentos": pagamentos, "desconto": reais(desconto),
                     "cliente_id": cliente["id"] if cliente else None,
                     "crediario": {"parcelas": rnd.randint(1, 6)}}
            # o que o sistema DEVE decidir, calculado aqui de forma independente
            deve_aceitar = (
                estado["caixa_aberto"] and not item_zerado
                and all(Decimal(x["valor"].replace(",", ".")) > 0 for x in pagamentos)
                and all(estoque[pid] >= q for pid, q in pedido.items())
                and desconto < subtotal
                and sum(int(Decimal(x["valor"].replace(",", ".")) * 100) for x in pagamentos) >= total
                and not any(x["forma"] == "PIX" and len(pagamentos) == 1 and
                            int(Decimal(x["valor"].replace(",", ".")) * 100) < total for x in pagamentos)
            )
            if crediario and cliente:
                vencido = sum(c["valor"] - c["valor_pago"] for c in loja.listar_contas_receber(cliente["id"], vencidas=True))
                if vencido or divida[cliente["id"]] + crediario > cliente["limite_credito"]:
                    deve_aceitar = False
            try:
                v = loja.registrar_venda(dados)
            except LojaError:
                self.assertFalse(deve_aceitar, f"venda válida recusada: {dados}")
                return False
            self.assertTrue(deve_aceitar, f"venda inválida aceita: {dados}")
            self.assertEqual(v["total"], total)
            for pid, q in pedido.items():
                estoque[pid] -= q
            estado["dinheiro"] += sum(int(Decimal(x["valor"].replace(",", ".")) * 100)
                                      for x in pagamentos if x["forma"] == "DINHEIRO") - v["troco"]
            if crediario:
                divida[cliente["id"]] += crediario
                self.assertEqual(sum(p["valor"] for p in v["parcelas"]), crediario)
            estado["faturado"] += total
            vendas.append(v["id"])
            return True

        def op_cancelar():
            if not vendas:
                return False
            v = loja.obter_venda(rnd.choice(vendas))
            try:
                loja.cancelar_venda(v["id"], "simulação")
            except LojaError:
                self.assertTrue(v["status"] != "CONCLUIDA" or v["devolucoes"] or not estado["caixa_aberto"]
                                or any(p["valor_pago"] for p in v["parcelas"])
                                or estado["dinheiro"] < sum(p["valor"] - p["troco"] for p in v["pagamentos"]
                                                            if p["forma"] == "DINHEIRO"))
                return False
            for i in v["itens"]:
                estoque[i["produto_id"]] += i["quantidade"]
            estado["dinheiro"] -= sum(p["valor"] - p["troco"] for p in v["pagamentos"] if p["forma"] == "DINHEIRO")
            if v["cliente_id"]:
                divida[v["cliente_id"]] -= sum(p["valor"] for p in v["parcelas"] if p["status"] == "ABERTA")
            estado["faturado"] -= v["total"]
            return True

        def op_devolucao():
            if not vendas:
                return False
            v = loja.obter_venda(rnd.choice(vendas))
            itens = []
            for i in v["itens"]:
                resta = i["quantidade"] - i["quantidade_devolvida"]
                if resta and rnd.random() < 0.6:
                    q = resta if rnd.random() < 0.4 else max(1, resta // 2)
                    if not fracionavel[i["produto_id"]]:
                        q = max(1000, q // 1000 * 1000)
                    itens.append((i, min(q, resta) if rnd.random() < 0.9 else resta + 1000))
            if not itens:
                return False
            forma = rnd.choice(["DINHEIRO", "PIX"])
            saldo_aberto = sum(p["valor"] - p["valor_pago"] for p in v["parcelas"] if p["status"] == "ABERTA")
            try:
                d = loja.registrar_devolucao(v["id"], {"itens": [{"item_id": i["id"], "quantidade": qtd_txt(q)}
                                                                 for i, q in itens], "forma_reembolso": forma})
            except LojaError:
                self.assertTrue(v["status"] != "CONCLUIDA" or not estado["caixa_aberto"]
                                or any(q > i["quantidade"] - i["quantidade_devolvida"] for i, q in itens)
                                or forma == "DINHEIRO")
                return False
            self.assertEqual(d["valor"], d["valor_abatido"] + d["valor_reembolsado"])
            self.assertEqual(d["valor_abatido"], min(d["valor"], saldo_aberto))
            for i, q in itens:
                estoque[i["produto_id"]] += q
            if forma == "DINHEIRO":
                estado["dinheiro"] -= d["valor_reembolsado"]
            if v["cliente_id"]:
                divida[v["cliente_id"]] -= d["valor_abatido"]
            estado["faturado"] -= d["valor"]
            return True

        def op_receber():
            c = rnd.choice(clientes)
            if not divida[c["id"]]:
                return False
            valor = rnd.randint(1, divida[c["id"]] + 500)
            forma = rnd.choice(["DINHEIRO", "PIX", "DEBITO"])
            try:
                loja.receber_do_cliente(c["id"], reais(valor), forma)
            except LojaError:
                self.assertTrue(valor > divida[c["id"]] or not estado["caixa_aberto"])
                return False
            self.assertLessEqual(valor, divida[c["id"]])
            divida[c["id"]] -= valor
            if forma == "DINHEIRO":
                estado["dinheiro"] += valor
            return True

        def op_compra():
            itens, total = [], 0
            for p in rnd.sample(produtos, rnd.randint(1, 3)):
                q = rnd.randint(1, 100) * 1000
                custo = rnd.randint(50, 100000)
                itens.append({"produto_id": p["id"], "quantidade": qtd_txt(q), "custo_unitario": reais(custo)})
                total += valor_item(custo, q)
                estoque[p["id"]] += q
            c = loja.registrar_compra({"fornecedor_id": forn["id"], "itens": itens, "parcelas": rnd.randint(1, 4)})
            self.assertEqual(c["total"], total)
            estado["a_pagar"] += total
            return True

        def op_pagar_conta():
            contas = loja.listar_contas_pagar(status="ABERTA")
            if not contas:
                return False
            c = rnd.choice(contas)
            valor = rnd.randint(1, c["restante"])
            loja.pagar_conta(c["id"], reais(valor), "PIX")
            estado["a_pagar"] -= valor
            return True

        def op_ajuste():
            p = rnd.choice(produtos)
            contado = rnd.randint(0, 200) * 1000
            try:
                loja.ajustar_estoque(p["id"], qtd_txt(contado), "inventário")
            except LojaError:
                self.assertEqual(contado, estoque[p["id"]])
                return False
            estoque[p["id"]] = contado
            return True

        def op_perda():
            p = rnd.choice(produtos)
            q = rnd.randint(1, 5) * 1000
            try:
                loja.registrar_perda(p["id"], qtd_txt(q), "quebra")
            except LojaError:
                self.assertGreater(q, estoque[p["id"]])
                return False
            estoque[p["id"]] -= q
            return True

        def op_sangria():
            valor = rnd.randint(1, 30000)
            try:
                loja.sangria(reais(valor), "cofre")
            except LojaError:
                self.assertTrue(valor > estado["dinheiro"] or not estado["caixa_aberto"])
                return False
            estado["dinheiro"] -= valor
            return True

        def op_virar_dia():
            if estado["caixa_aberto"]:
                diferenca = rnd.choice([0, 0, -100, 250])
                s = loja.fechar_caixa(reais(max(0, estado["dinheiro"] + diferenca)))
                self.assertEqual(s["valor_esperado"], estado["dinheiro"])
                estado["caixa_aberto"] = False
            relogio.avancar(rnd.choice([1, 1, 2, 7]))
            if rnd.random() < 0.95:
                abrir()
            return True

        operacoes = [(op_venda, 40), (op_cancelar, 4), (op_devolucao, 6), (op_receber, 12), (op_compra, 5),
                     (op_pagar_conta, 5), (op_ajuste, 3), (op_perda, 3), (op_sangria, 4), (op_virar_dia, 4)]
        funcoes = [f for f, _ in operacoes]
        pesos = [w for _, w in operacoes]
        for n in range(self.OPERACOES):
            op = rnd.choices(funcoes, pesos)[0]
            contadores["ok" if op() else "recusada"] += 1
            # confere o livro paralelo depois de cada operação
            for pid, esperado in estoque.items():
                self.assertEqual(loja.obter_produto(pid)["estoque"], esperado, f"estoque do produto {pid} (op {n})")
            if estado["caixa_aberto"]:
                self.assertEqual(loja.caixa_atual()["saldo_dinheiro"], estado["dinheiro"], f"dinheiro (op {n})")
            for cid, esperado in divida.items():
                self.assertEqual(loja.obter_cliente(cid)["saldo_devedor"], esperado, f"dívida do cliente {cid} (op {n})")
            if n % 100 == 0:
                self.assertEqual(loja.verificar_integridade(), [], f"integridade (op {n})")

        self.assertEqual(loja.verificar_integridade(), [])
        total_pagar = sum(c["restante"] for c in loja.listar_contas_pagar(status="ABERTA"))
        self.assertEqual(total_pagar, estado["a_pagar"])
        r = loja.relatorio_vendas("2000-01-01", "2100-01-01")
        self.assertEqual(r["liquido"], estado["faturado"])
        self.assertGreater(contadores["ok"], self.OPERACOES // 2)
        self.assertGreater(len(vendas), 300)
        loja.fechar()


if __name__ == "__main__":
    unittest.main()
