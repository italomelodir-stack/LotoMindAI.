"""Servidor web do sistema: API JSON em /api/... e a interface em /."""
import json
import os
import re
import socket
import socketserver
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import VERSAO
from .sistema import (FORMAS_PAGAMENTO, FORMAS_PAGAMENTO_CONTA, FORMAS_RECEBIMENTO, FORMAS_REEMBOLSO,
                      UNIDADES, FRACIONAVEIS, Loja)
from .valores import LojaError, NaoEncontrado

ESTATICOS = Path(__file__).parent / "static"
# tipos fixos: no Windows o mimetypes lê o registro, que às vezes tem valores errados para .js e .css
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
ROTAS = []


def rota(metodo, padrao, com_servidor=False):
    """com_servidor=True: a função recebe o manipulador da requisição (acesso aos backups e ao desligamento)."""
    def registrar(func):
        ROTAS.append((metodo, re.compile(f"^{padrao}$"), func, com_servidor))
        return func
    return registrar


def _bool(q, chave):
    return q.get(chave, "") in ("1", "true", "sim")


# ------------------------------------------------------------------- rotas
@rota("GET", "/api/config", com_servidor=True)
def config(h, q, corpo):
    loja = h.loja
    return {"unidades": UNIDADES, "fracionaveis": sorted(FRACIONAVEIS), "formas_pagamento": FORMAS_PAGAMENTO,
            "formas_recebimento": FORMAS_RECEBIMENTO, "formas_reembolso": FORMAS_REEMBOLSO,
            "formas_pagamento_conta": FORMAS_PAGAMENTO_CONTA, "hoje": loja.hoje().isoformat(),
            "primeira_venda": loja.primeira_venda().isoformat(), "versao": VERSAO,
            "loja": loja.obter_configuracoes(), "nome_loja": loja.obter_configuracoes()["nome_loja"],
            "backup": h.backups.ultimo() if h.backups else None, "pode_desligar": h.ao_desligar is not None}


@rota("GET", "/api/configuracoes")
def configuracoes(loja, q, corpo):
    return loja.obter_configuracoes()


@rota("PUT", "/api/configuracoes")
def salvar_configuracoes(loja, q, corpo):
    return loja.salvar_configuracoes(corpo)


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
    return loja.listar_clientes(q.get("busca", ""), _bool(q, "ativos"), _bool(q, "devendo"))


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


@rota("GET", r"/api/clientes/(?P<cid>\d+)/debitos")
def debitos(loja, q, corpo, cid):
    return {"cliente": loja.obter_cliente(int(cid)), "compras": loja.debitos_cliente(int(cid))}


@rota("GET", r"/api/clientes/(?P<cid>\d+)/historico")
def historico(loja, q, corpo, cid):
    return loja.historico_cliente(int(cid), q.get("inicio") or None, q.get("fim") or None)


@rota("POST", r"/api/clientes/(?P<cid>\d+)/baixa")
def baixa(loja, q, corpo, cid):
    return loja.receber_conta_cliente(int(cid), corpo)


@rota("GET", "/api/baixas")
def baixas(loja, q, corpo):
    return loja.listar_baixas(q.get("cliente_id") or None, q.get("inicio") or None, q.get("fim") or None)


@rota("GET", r"/api/baixas/(?P<bid>\d+)")
def obter_baixa(loja, q, corpo, bid):
    return loja.obter_baixa(int(bid))


@rota("POST", r"/api/baixas/(?P<bid>\d+)/estornar")
def estornar_baixa(loja, q, corpo, bid):
    return loja.estornar_baixa(int(bid), corpo.get("motivo"))


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


@rota("POST", "/api/caixa/fechar", com_servidor=True)
def fechar_caixa(h, q, corpo):
    sessao = h.loja.fechar_caixa(corpo.get("valor_contado"), corpo.get("observacao"))
    if h.backups:
        try:
            sessao["backup"] = h.backups.fazer("fechamento do caixa")
        except Exception:   # o caixa já foi fechado; a falha do backup fica registrada e aparece no painel
            traceback.print_exc()
    return sessao


@rota("POST", "/api/caixa/sangria")
def sangria(loja, q, corpo):
    return loja.sangria(corpo.get("valor"), corpo.get("motivo"))


@rota("POST", "/api/caixa/suprimento")
def suprimento(loja, q, corpo):
    return loja.suprimento(corpo.get("valor"), corpo.get("motivo"))


@rota("GET", "/api/relatorios/vendas")
def rel_vendas(loja, q, corpo):
    return loja.relatorio_vendas(q.get("inicio") or None, q.get("fim") or None)


@rota("GET", "/api/relatorios/vendas-por-dia")
def rel_vendas_dia(loja, q, corpo):
    return loja.vendas_por_dia(q.get("dias", 14))


@rota("GET", "/api/relatorios/por-mes")
def rel_por_mes(loja, q, corpo):
    return loja.vendas_por_mes(q.get("inicio") or None, q.get("fim") or None)


@rota("GET", "/api/relatorios/por-categoria")
def rel_por_categoria(loja, q, corpo):
    return loja.vendas_por_categoria(q.get("inicio") or None, q.get("fim") or None)


@rota("GET", "/api/relatorios/por-cliente")
def rel_por_cliente(loja, q, corpo):
    return loja.vendas_por_cliente(q.get("inicio") or None, q.get("fim") or None)


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


def _backups(h):
    if not h.backups:
        raise LojaError("Backup não está disponível neste modo")
    return h.backups


@rota("GET", "/api/backups", com_servidor=True)
def listar_backups(h, q, corpo):
    b = _backups(h)
    return {"pasta": str(b.pasta), "ultimo": b.ultimo(), "lista": b.listar()}


@rota("POST", "/api/backups", com_servidor=True)
def fazer_backup(h, q, corpo):
    return _backups(h).fazer("manual")


@rota("POST", "/api/backups/restaurar", com_servidor=True)
def restaurar_backup(h, q, corpo):
    return _backups(h).restaurar(corpo.get("nome"))


@rota("POST", "/api/desligar", com_servidor=True)
def desligar(h, q, corpo):
    if not h.ao_desligar:
        raise LojaError("Não é possível fechar o sistema por aqui")
    threading.Timer(0.3, h.ao_desligar).start()   # responde antes de desligar
    return {"ok": True}


# ------------------------------------------------------------------ servidor
class Manipulador(BaseHTTPRequestHandler):
    loja: Loja = None
    backups = None
    ao_desligar = None
    silencioso = False
    hosts_permitidos = None   # None = qualquer um (modo rede)

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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(corpo)

    def _origem_confiavel(self, metodo):
        """Só aceita comandos da própria tela do sistema: bloqueia sites de fora que tentem usar o
        navegador do usuário para mandar pedidos ao sistema (CSRF e DNS rebinding)."""
        host = (self.headers.get("Host") or "").lower()
        if self.hosts_permitidos is not None and host not in self.hosts_permitidos:
            return False
        origem = self.headers.get("Origin")
        if origem and urlparse(origem).netloc.lower() != host:
            return False
        if metodo in ("POST", "PUT"):
            tipo = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if tipo != "application/json":
                return False
        return True

    def _api(self, metodo):
        url = urlparse(self.path)
        q = {k: vs[-1] for k, vs in parse_qs(url.query).items()}
        if not self._origem_confiavel(metodo):
            return self._responder(403, {"erro": "Pedido recusado: origem não autorizada"})
        for m, padrao, func, com_servidor in ROTAS:
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
            resultado = func(self if com_servidor else self.loja, q, corpo, **achou.groupdict())
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
        tipo = TIPOS.get(arquivo.suffix.lower(), "application/octet-stream")
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


class Servidor(ThreadingHTTPServer):
    # vários caixas e telas abertas ao mesmo tempo: a fila padrão (5 conexões) recusaria pedidos em picos
    request_queue_size = 128
    daemon_threads = True
    # no Windows, "reusar endereço" deixaria duas cópias do sistema abrirem na mesma porta
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # o HTTPServer padrão consulta o nome do computador na rede, o que pode demorar segundos no Windows
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def criar_servidor(loja, host="127.0.0.1", porta=8080, silencioso=False, backups=None, ao_desligar=None):
    atributos = {"loja": loja, "silencioso": silencioso, "backups": backups,
                 "ao_desligar": staticmethod(ao_desligar) if ao_desligar else None}
    servidor = Servidor((host, porta), type("ManipuladorLoja", (Manipulador,), atributos))
    if host in ("127.0.0.1", "localhost"):
        p = servidor.server_address[1]
        servidor.RequestHandlerClass.hosts_permitidos = {f"127.0.0.1:{p}", f"localhost:{p}"}
    return servidor


def main():
    from .aplicativo import main as principal
    principal()


if __name__ == "__main__":
    main()
