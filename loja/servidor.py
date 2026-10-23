"""Servidor web do sistema: API JSON em /api/... e a interface em /."""
import datetime
import json
import mimetypes
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .sistema import (FORMAS_PAGAMENTO, FORMAS_PAGAMENTO_CONTA, FORMAS_RECEBIMENTO, FORMAS_REEMBOLSO,
                      UNIDADES, FRACIONAVEIS, Loja)
from .valores import LojaError, NaoEncontrado

ESTATICOS = Path(__file__).parent / "static"
ROTAS = []


def rota(metodo, padrao):
    def registrar(func):
        ROTAS.append((metodo, re.compile(f"^{padrao}$"), func))
        return func
    return registrar


def _bool(q, chave):
    return q.get(chave, "") in ("1", "true", "sim")


# ------------------------------------------------------------------- rotas
@rota("GET", "/api/config")
def config(loja, q, corpo):
    return {"unidades": UNIDADES, "fracionaveis": sorted(FRACIONAVEIS), "formas_pagamento": FORMAS_PAGAMENTO,
            "formas_recebimento": FORMAS_RECEBIMENTO, "formas_reembolso": FORMAS_REEMBOLSO,
            "formas_pagamento_conta": FORMAS_PAGAMENTO_CONTA, "hoje": loja.hoje().isoformat(),
            "nome_loja": os.environ.get("LOJA_NOME", "Loja de Materiais de Construção")}


@rota("GET", "/api/painel")
def painel(loja, q, corpo):
    return loja.painel()


@rota("GET", "/api/produtos")
def produtos(loja, q, corpo):
    return loja.listar_produtos(q.get("busca", ""), q.get("categoria", ""), _bool(q, "ativos"),
                                _bool(q, "estoque_baixo"))


@rota("POST", "/api/produtos")
def novo_produto(loja, q, corpo):
    return loja.cadastrar_produto(corpo)


@rota("GET", "/api/produtos/categorias")
def categorias(loja, q, corpo):
    return loja.listar_categorias()


@rota("GET", r"/api/produtos/codigo/(?P<codigo>[^/]+)")
def produto_codigo(loja, q, corpo, codigo):
    return loja.buscar_produto_por_codigo(codigo)


@rota("GET", r"/api/produtos/(?P<pid>\d+)")
def produto(loja, q, corpo, pid):
    return loja.obter_produto(int(pid))


@rota("PUT", r"/api/produtos/(?P<pid>\d+)")
def editar_produto(loja, q, corpo, pid):
    return loja.atualizar_produto(int(pid), corpo)


@rota("POST", r"/api/produtos/(?P<pid>\d+)/ajuste")
def ajuste(loja, q, corpo, pid):
    return loja.ajustar_estoque(int(pid), corpo.get("quantidade"), corpo.get("motivo"))


@rota("POST", r"/api/produtos/(?P<pid>\d+)/perda")
def perda(loja, q, corpo, pid):
    return loja.registrar_perda(int(pid), corpo.get("quantidade"), corpo.get("motivo"))


@rota("GET", "/api/movimentos")
def movimentos(loja, q, corpo):
    return loja.listar_movimentos(q.get("produto_id") or None, q.get("limite", 300))


@rota("GET", "/api/fornecedores")
def fornecedores(loja, q, corpo):
    return loja.listar_fornecedores(q.get("busca", ""), _bool(q, "ativos"))


@rota("POST", "/api/fornecedores")
def novo_fornecedor(loja, q, corpo):
    return loja.cadastrar_fornecedor(corpo)


@rota("PUT", r"/api/fornecedores/(?P<fid>\d+)")
def editar_fornecedor(loja, q, corpo, fid):
    return loja.atualizar_fornecedor(int(fid), corpo)


@rota("GET", "/api/compras")
def compras(loja, q, corpo):
    return loja.listar_compras()


@rota("POST", "/api/compras")
def nova_compra(loja, q, corpo):
    return loja.registrar_compra(corpo)


@rota("GET", r"/api/compras/(?P<cid>\d+)")
def compra(loja, q, corpo, cid):
    return loja.obter_compra(int(cid))


@rota("GET", "/api/clientes")
def clientes(loja, q, corpo):
    return loja.listar_clientes(q.get("busca", ""), _bool(q, "ativos"))


@rota("POST", "/api/clientes")
def novo_cliente(loja, q, corpo):
    return loja.cadastrar_cliente(corpo)


@rota("GET", r"/api/clientes/(?P<cid>\d+)")
def cliente(loja, q, corpo, cid):
    return loja.extrato_cliente(int(cid))


@rota("PUT", r"/api/clientes/(?P<cid>\d+)")
def editar_cliente(loja, q, corpo, cid):
    return loja.atualizar_cliente(int(cid), corpo)


@rota("POST", r"/api/clientes/(?P<cid>\d+)/receber")
def receber_cliente(loja, q, corpo, cid):
    return loja.receber_do_cliente(int(cid), corpo.get("valor"), corpo.get("forma"))


@rota("GET", "/api/vendas")
def vendas(loja, q, corpo):
    return loja.listar_vendas(q.get("inicio") or None, q.get("fim") or None, q.get("cliente_id") or None,
                              q.get("status") or None)


@rota("POST", "/api/vendas")
def nova_venda(loja, q, corpo):
    return loja.registrar_venda(corpo)


@rota("GET", r"/api/vendas/(?P<vid>\d+)")
def venda(loja, q, corpo, vid):
    return loja.obter_venda(int(vid))


@rota("POST", r"/api/vendas/(?P<vid>\d+)/cancelar")
def cancelar_venda(loja, q, corpo, vid):
    return loja.cancelar_venda(int(vid), corpo.get("motivo"))


@rota("POST", r"/api/vendas/(?P<vid>\d+)/devolucao")
def devolucao(loja, q, corpo, vid):
    return loja.registrar_devolucao(int(vid), corpo)


@rota("GET", "/api/orcamentos")
def orcamentos(loja, q, corpo):
    return loja.listar_orcamentos(q.get("status") or None)


@rota("POST", "/api/orcamentos")
def novo_orcamento(loja, q, corpo):
    return loja.criar_orcamento(corpo)


@rota("GET", r"/api/orcamentos/(?P<oid>\d+)")
def orcamento(loja, q, corpo, oid):
    return loja.obter_orcamento(int(oid))


@rota("POST", r"/api/orcamentos/(?P<oid>\d+)/converter")
def converter(loja, q, corpo, oid):
    return loja.converter_orcamento(int(oid), corpo)


@rota("POST", r"/api/orcamentos/(?P<oid>\d+)/cancelar")
def cancelar_orcamento(loja, q, corpo, oid):
    return loja.cancelar_orcamento(int(oid))


@rota("GET", "/api/contas-receber")
def contas_receber(loja, q, corpo):
    return loja.listar_contas_receber(q.get("cliente_id") or None, q.get("status") or None, _bool(q, "vencidas"))


@rota("POST", r"/api/contas-receber/(?P<cid>\d+)/receber")
def receber(loja, q, corpo, cid):
    return loja.receber_parcela(int(cid), corpo.get("valor"), corpo.get("forma"))


@rota("GET", "/api/contas-pagar")
def contas_pagar(loja, q, corpo):
    return loja.listar_contas_pagar(q.get("status") or None, _bool(q, "vencidas"))


@rota("POST", "/api/contas-pagar")
def nova_conta(loja, q, corpo):
    return loja.lancar_conta_pagar(corpo)


@rota("POST", r"/api/contas-pagar/(?P<cid>\d+)/pagar")
def pagar(loja, q, corpo, cid):
    return loja.pagar_conta(int(cid), corpo.get("valor"), corpo.get("forma"))


@rota("POST", r"/api/contas-pagar/(?P<cid>\d+)/cancelar")
def cancelar_conta(loja, q, corpo, cid):
    return loja.cancelar_conta_pagar(int(cid))


@rota("GET", "/api/caixa")
def caixa(loja, q, corpo):
    return {"caixa": loja.caixa_atual(), "sessoes": loja.listar_sessoes_caixa()}


@rota("GET", r"/api/caixa/(?P<sid>\d+)")
def sessao_caixa(loja, q, corpo, sid):
    return loja.obter_caixa(int(sid))


@rota("POST", "/api/caixa/abrir")
def abrir_caixa(loja, q, corpo):
    return loja.abrir_caixa(corpo.get("valor_inicial"), corpo.get("operador"))


@rota("POST", "/api/caixa/fechar")
def fechar_caixa(loja, q, corpo):
    return loja.fechar_caixa(corpo.get("valor_contado"), corpo.get("observacao"))


@rota("POST", "/api/caixa/sangria")
def sangria(loja, q, corpo):
    return loja.sangria(corpo.get("valor"), corpo.get("motivo"))


@rota("POST", "/api/caixa/suprimento")
def suprimento(loja, q, corpo):
    return loja.suprimento(corpo.get("valor"), corpo.get("motivo"))


@rota("GET", "/api/relatorios/vendas")
def rel_vendas(loja, q, corpo):
    return loja.relatorio_vendas(q.get("inicio") or None, q.get("fim") or None)


@rota("GET", "/api/relatorios/mais-vendidos")
def rel_mais_vendidos(loja, q, corpo):
    return loja.mais_vendidos(q.get("inicio") or None, q.get("fim") or None)


@rota("GET", "/api/relatorios/estoque")
def rel_estoque(loja, q, corpo):
    return loja.relatorio_estoque()


@rota("GET", "/api/integridade")
def integridade(loja, q, corpo):
    problemas = loja.verificar_integridade()
    return {"ok": not problemas, "problemas": problemas}


@rota("POST", "/api/backup")
def backup(loja, q, corpo):
    if loja.caminho == ":memory:":
        raise LojaError("Banco em memória não tem backup")
    pasta = Path(loja.caminho).resolve().parent / "backups"
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"loja-{datetime.datetime.now():%Y%m%d-%H%M%S}.db"
    loja.backup(str(destino))
    return {"arquivo": str(destino)}


# ------------------------------------------------------------------ servidor
class Manipulador(BaseHTTPRequestHandler):
    loja: Loja = None
    silencioso = False

    def log_message(self, formato, *args):
        if not self.silencioso:
            super().log_message(formato, *args)

    def _responder(self, status, dados=None, corpo=None, tipo="application/json; charset=utf-8"):
        if corpo is None:
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _api(self, metodo):
        url = urlparse(self.path)
        q = {k: vs[-1] for k, vs in parse_qs(url.query).items()}
        for m, padrao, func in ROTAS:
            achou = padrao.match(url.path)
            if m == metodo and achou:
                break
        else:
            return self._responder(404, {"erro": "Endereço não encontrado"})
        try:
            corpo = {}
            if metodo in ("POST", "PUT"):
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho:
                    corpo = json.loads(self.rfile.read(tamanho).decode("utf-8"))
                if not isinstance(corpo, dict):
                    raise LojaError("Corpo da requisição inválido")
            resultado = func(self.loja, q, corpo, **achou.groupdict())
            self._responder(200, resultado)
        except NaoEncontrado as e:
            self._responder(404, {"erro": str(e)})
        except LojaError as e:
            self._responder(400, {"erro": str(e)})
        except json.JSONDecodeError:
            self._responder(400, {"erro": "JSON inválido"})
        except Exception as e:  # erro inesperado: registra e avisa sem derrubar o servidor
            traceback.print_exc()
            self._responder(500, {"erro": f"Erro interno: {e}"})

    def _estatico(self):
        caminho = urlparse(self.path).path
        if caminho in ("/", ""):
            caminho = "/index.html"
        arquivo = (ESTATICOS / caminho.lstrip("/")).resolve()
        if ESTATICOS.resolve() not in arquivo.parents or not arquivo.is_file():
            return self._responder(404, {"erro": "Arquivo não encontrado"})
        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo.endswith("javascript"):
            tipo += "; charset=utf-8"
        self._responder(200, corpo=arquivo.read_bytes(), tipo=tipo)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._api("GET")
        else:
            self._estatico()

    def do_POST(self):
        self._api("POST")

    def do_PUT(self):
        self._api("PUT")


def criar_servidor(loja, host="127.0.0.1", porta=8080, silencioso=False):
    manipulador = type("ManipuladorLoja", (Manipulador,), {"loja": loja, "silencioso": silencioso})
    return ThreadingHTTPServer((host, porta), manipulador)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sistema para loja de material de construção")
    parser.add_argument("--banco", default=os.environ.get("LOJA_BANCO", "loja.db"),
                        help="arquivo do banco de dados (padrão: loja.db)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="use 0.0.0.0 para acessar de outros computadores da rede")
    parser.add_argument("--porta", type=int, default=8080)
    args = parser.parse_args()
    loja = Loja(args.banco)
    servidor = criar_servidor(loja, args.host, args.porta)
    print(f"Sistema da loja rodando em http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}"
          f":{args.porta}  (banco: {os.path.abspath(args.banco)})")
    print("Para encerrar, pressione Ctrl+C.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        servidor.server_close()
        loja.fechar()


if __name__ == "__main__":
    main()
