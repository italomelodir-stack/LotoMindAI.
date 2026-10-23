"""Testa o servidor web de verdade, via HTTP, como a interface faz."""
import json
import threading
import unittest
import urllib.error
import urllib.request

from loja import Loja
from loja.servidor import criar_servidor
from tests.base import Relogio


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loja = Loja(":memory:", hoje=Relogio())
        cls.servidor = criar_servidor(cls.loja, porta=0, silencioso=True)
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.loja.fechar()

    def chamar(self, metodo, caminho, corpo=None, esperado=200):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(self.url + caminho, data=dados, method=metodo,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                status, texto = r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            status, texto = e.code, e.read().decode()
        self.assertEqual(status, esperado, texto)
        return json.loads(texto)

    def test_fluxo_completo(self):
        c = self.chamar
        c("POST", "/api/caixa/abrir", {"valor_inicial": "100,00", "operador": "Ana"})
        forn = c("POST", "/api/fornecedores", {"nome": "Distribuidora"})
        p = c("POST", "/api/produtos", {"nome": "Argamassa AC-II 20kg", "unidade": "SC", "preco_venda": "24,90",
                                        "preco_custo": "15", "estoque_inicial": "40", "categoria": "Argamassa"})
        cli = c("POST", "/api/clientes", {"nome": "Construtora X", "documento": "11.222.333/0001-81",
                                          "limite_credito": "1000"})
        self.assertEqual(c("GET", f"/api/produtos/codigo/{p['codigo']}")["id"], p["id"])
        self.assertIn("Argamassa", c("GET", "/api/produtos/categorias"))

        v = c("POST", "/api/vendas", {"itens": [{"produto_id": p["id"], "quantidade": "4"}],
                                      "pagamentos": [{"forma": "DINHEIRO", "valor": "100"}]})
        self.assertEqual((v["total"], v["troco"]), (9960, 40))

        v2 = c("POST", "/api/vendas", {"itens": [{"produto_id": p["id"], "quantidade": "10"}], "cliente_id": cli["id"],
                                       "pagamentos": [{"forma": "CREDIARIO", "valor": "249"}],
                                       "crediario": {"parcelas": 2}})
        self.assertEqual(len(v2["parcelas"]), 2)
        conta = v2["parcelas"][0]
        r = c("POST", f"/api/contas-receber/{conta['id']}/receber", {"valor": "124,50", "forma": "PIX"})
        self.assertEqual(r["status"], "PAGA")
        self.assertEqual(c("GET", f"/api/clientes/{cli['id']}")["saldo_devedor"], 12450)
        c("POST", f"/api/clientes/{cli['id']}/receber", {"valor": "124,50", "forma": "DINHEIRO"})

        # baixa parcial escolhendo a parcela, com troco, e estorno
        v4 = c("POST", "/api/vendas", {"itens": [{"produto_id": p["id"], "quantidade": "4"}], "cliente_id": cli["id"],
                                       "pagamentos": [{"forma": "CREDIARIO", "valor": "99,60"}],
                                       "crediario": {"parcelas": 2}})
        deb = c("GET", f"/api/clientes/{cli['id']}/debitos")
        self.assertEqual(deb["cliente"]["saldo_devedor"], 9960)
        self.assertEqual(deb["compras"][0]["produtos"][0]["quantidade"], 4000)
        b = c("POST", f"/api/clientes/{cli['id']}/baixa", {"contas": [v4["parcelas"][1]["id"]], "valor": "30",
                                                           "valor_recebido": "50", "forma": "DINHEIRO"})
        self.assertEqual((b["valor"], b["troco"], b["saldo_apos"]), (3000, 2000, 6960))
        self.assertEqual(c("GET", f"/api/baixas/{b['id']}")["itens"][0]["conta_id"], v4["parcelas"][1]["id"])
        r = c("POST", f"/api/clientes/{cli['id']}/baixa", {"valor": "999", "forma": "PIX"}, esperado=400)
        self.assertIn("maior que o total", r["erro"])
        c("POST", f"/api/baixas/{b['id']}/estornar", {"motivo": "teste"})
        self.assertEqual(c("GET", f"/api/clientes/{cli['id']}")["saldo_devedor"], 9960)
        self.assertEqual(len(c("GET", f"/api/baixas?cliente_id={cli['id']}")), 3)
        c("POST", f"/api/vendas/{v4['id']}/cancelar", {"motivo": "teste"})
        self.assertEqual(len(c("GET", "/api/relatorios/vendas-por-dia?dias=7")), 7)

        d = c("POST", f"/api/vendas/{v['id']}/devolucao",
              {"itens": [{"item_id": v["itens"][0]["id"], "quantidade": "1"}], "forma_reembolso": "DINHEIRO"})
        self.assertEqual(d["valor"], 2490)

        compra = c("POST", "/api/compras", {"fornecedor_id": forn["id"], "parcelas": 2,
                                            "itens": [{"produto_id": p["id"], "quantidade": "20", "custo_unitario": "16"}]})
        self.assertEqual(compra["total"], 32000)
        self.assertEqual(c("GET", f"/api/produtos/{p['id']}")["estoque"], 47000)
        contas = c("GET", "/api/contas-pagar?status=ABERTA")
        c("POST", f"/api/contas-pagar/{contas[0]['id']}/pagar", {"valor": "160", "forma": "PIX"})

        o = c("POST", "/api/orcamentos", {"itens": [{"produto_id": p["id"], "quantidade": "2"}], "nome_cliente": "Zé"})
        v3 = c("POST", f"/api/orcamentos/{o['id']}/converter", {"pagamentos": [{"forma": "DEBITO", "valor": "49,80"}]})
        self.assertEqual(v3["total"], 4980)

        caixa = c("GET", "/api/caixa")["caixa"]
        esperado = 10000 + 9960 + 12450 - 2490
        self.assertEqual(caixa["saldo_dinheiro"], esperado)
        fechado = c("POST", "/api/caixa/fechar", {"valor_contado": f"{esperado // 100},{esperado % 100:02d}"})
        self.assertEqual(fechado["diferenca"], 0)

        rel = c("GET", "/api/relatorios/vendas")
        self.assertEqual(rel["quantidade"], 3)
        self.assertEqual(rel["liquido"], 9960 + 24900 + 4980 - 2490)
        self.assertTrue(c("GET", "/api/integridade")["ok"])
        for caminho in ["/api/painel", "/api/config", "/api/vendas", "/api/orcamentos", "/api/movimentos",
                        "/api/contas-receber?vencidas=1", "/api/relatorios/mais-vendidos", "/api/relatorios/estoque",
                        "/api/compras", "/api/fornecedores", "/api/clientes?busca=constr", f"/api/caixa/{fechado['id']}"]:
            with self.subTest(caminho=caminho):
                c("GET", caminho)

    def test_erros_viram_mensagens(self):
        r = self.chamar("POST", "/api/produtos", {"nome": "", "unidade": "UN", "preco_venda": "1"}, esperado=400)
        self.assertIn("obrigatório", r["erro"])
        r = self.chamar("POST", "/api/clientes", {"nome": "X", "documento": "123.456.789-00"}, esperado=400)
        self.assertIn("CPF/CNPJ inválido", r["erro"])
        self.chamar("GET", "/api/produtos/99999", esperado=404)
        self.chamar("GET", "/api/nao-existe", esperado=404)
        self.chamar("POST", "/api/vendas", {"itens": "lixo"}, esperado=400)

    def test_json_invalido(self):
        req = urllib.request.Request(self.url + "/api/produtos", data=b"{nada", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_paginas_estaticas(self):
        for caminho, tipo in [("/", "text/html"), ("/app.js", "javascript"), ("/style.css", "text/css")]:
            with urllib.request.urlopen(self.url + caminho) as r:
                self.assertIn(tipo, r.headers["Content-Type"])
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.url + "/../sistema.py")
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.url + "/%2e%2e/sistema.py")

    def test_vendas_simultaneas_nao_vendem_alem_do_estoque(self):
        """40 pedidos ao mesmo tempo disputando as últimas 5 unidades: só pode vender o que existe."""
        try:
            self.chamar("POST", "/api/caixa/abrir", {"valor_inicial": "0"})
        except AssertionError:
            pass
        p = self.chamar("POST", "/api/produtos", {"nome": "Caixa d'água 1000L", "unidade": "UN",
                                                  "preco_venda": "450", "estoque_inicial": "5"})
        resultados = []

        def comprar():
            req = urllib.request.Request(
                self.url + "/api/vendas", method="POST", headers={"Content-Type": "application/json"},
                data=json.dumps({"itens": [{"produto_id": p["id"], "quantidade": "1"}],
                                 "pagamentos": [{"forma": "PIX", "valor": "450"}]}).encode())
            try:
                with urllib.request.urlopen(req) as r:
                    resultados.append(r.status)
            except urllib.error.HTTPError as e:
                resultados.append(e.code)
            except OSError as e:  # conexão recusada/derrubada
                resultados.append(repr(e))

        threads = [threading.Thread(target=comprar) for _ in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(resultados), 40)
        self.assertEqual(resultados.count(200), 5)
        self.assertEqual(resultados.count(400), 35)
        self.assertEqual(self.chamar("GET", f"/api/produtos/{p['id']}")["estoque"], 0)
        self.assertTrue(self.chamar("GET", "/api/integridade")["ok"])


if __name__ == "__main__":
    unittest.main()
