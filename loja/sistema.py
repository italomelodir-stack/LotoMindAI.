"""Regras de negócio da loja de material de construção.

Todas as operações que alteram dados rodam numa transação única: ou tudo é
gravado (venda, baixa de estoque, caixa, parcelas), ou nada é.
"""
import datetime
import sqlite3
import threading
from contextlib import contextmanager
from decimal import Decimal

from . import valores as v
from .banco import criar_esquema
from .valores import LojaError, NaoEncontrado

UNIDADES = {
    "UN": "Unidade", "PC": "Peça", "CX": "Caixa", "SC": "Saco", "BR": "Barra",
    "RL": "Rolo", "GL": "Galão", "LT": "Lata", "PCT": "Pacote", "PAR": "Par",
    "M": "Metro", "M2": "Metro quadrado", "M3": "Metro cúbico", "KG": "Quilo",
    "L": "Litro", "MIL": "Milheiro",
}
# Unidades que podem ser vendidas em quantidade quebrada (2,5 m; 0,75 m³...)
FRACIONAVEIS = {"M", "M2", "M3", "KG", "L", "MIL"}

FORMAS_PAGAMENTO = ("DINHEIRO", "PIX", "DEBITO", "CREDITO", "CREDIARIO")
FORMAS_RECEBIMENTO = ("DINHEIRO", "PIX", "DEBITO", "CREDITO")
FORMAS_REEMBOLSO = ("DINHEIRO", "PIX", "DEBITO", "CREDITO")
FORMAS_PAGAMENTO_CONTA = ("DINHEIRO_CAIXA", "PIX", "TRANSFERENCIA", "BOLETO", "CHEQUE")
MAX_PARCELAS = 24


def _txt(dados, chave, obrigatorio=False, nome=None, padrao=""):
    valor = dados.get(chave)
    valor = padrao if valor is None else str(valor).strip()
    if obrigatorio and not valor:
        raise LojaError(f"{nome or chave}: campo obrigatório")
    return valor


def _int(valor, campo, minimo=None, maximo=None):
    try:
        if isinstance(valor, bool):
            raise ValueError
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        raise LojaError(f"{campo}: número inteiro inválido") from None
    if minimo is not None and n < minimo:
        raise LojaError(f"{campo}: mínimo {minimo}")
    if maximo is not None and n > maximo:
        raise LojaError(f"{campo}: máximo {maximo}")
    return n


def _lista(valor, campo):
    """Garante uma lista de objetos (dicts) vinda da interface."""
    if valor in (None, ""):
        return []
    if not isinstance(valor, list) or not all(isinstance(x, dict) for x in valor):
        raise LojaError(f"{campo}: formato inválido")
    return valor


def _objeto(valor, campo):
    if valor in (None, ""):
        return {}
    if not isinstance(valor, dict):
        raise LojaError(f"{campo}: formato inválido")
    return valor


def _opcional_id(valor, campo):
    if valor in (None, "", 0, "0"):
        return None
    return _int(valor, campo, minimo=1)


class Loja:
    def __init__(self, caminho=":memory:", hoje=None):
        self.caminho = caminho
        self.conn = sqlite3.connect(caminho, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if caminho != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        criar_esquema(self.conn)
        self._lock = threading.RLock()
        self._em_transacao = False
        self._hoje = hoje or datetime.date.today

    # ------------------------------------------------------------------ base
    def hoje(self):
        return self._hoje()

    def agora(self):
        return f"{self.hoje().isoformat()} {datetime.datetime.now().strftime('%H:%M:%S')}"

    @contextmanager
    def _transacao(self):
        with self._lock:
            if self._em_transacao:
                yield
                return
            self.conn.execute("BEGIN IMMEDIATE")
            self._em_transacao = True
            try:
                yield
            except sqlite3.IntegrityError as e:
                self.conn.execute("ROLLBACK")
                raise LojaError(f"Operação recusada pelo banco de dados: {e}") from e
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")
            finally:
                self._em_transacao = False

    def _um(self, sql, *args):
        with self._lock:
            r = self.conn.execute(sql, args).fetchone()
        return dict(r) if r else None

    def _todos(self, sql, *args):
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _escalar(self, sql, *args):
        with self._lock:
            r = self.conn.execute(sql, args).fetchone()
        return r[0] if r and r[0] is not None else 0

    def _inserir(self, sql, *args):
        return self.conn.execute(sql, args).lastrowid

    def fechar(self):
        self.conn.close()

    def backup(self, destino):
        with self._lock:
            alvo = sqlite3.connect(destino)
            try:
                self.conn.backup(alvo)
            finally:
                alvo.close()
        return destino

    # ----------------------------------------------------------- fornecedores
    def cadastrar_fornecedor(self, dados):
        nome = _txt(dados, "nome", True, "Nome")
        doc = v.documento(dados.get("documento"))
        with self._transacao():
            if doc and self._um("SELECT id FROM fornecedores WHERE documento = ?", doc):
                raise LojaError("Já existe fornecedor com este CPF/CNPJ")
            fid = self._inserir(
                "INSERT INTO fornecedores (nome, documento, telefone, email, endereco, criado_em)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                nome, doc, _txt(dados, "telefone"), _txt(dados, "email"),
                _txt(dados, "endereco"), self.agora())
        return self.obter_fornecedor(fid)

    def atualizar_fornecedor(self, fid, dados):
        atual = self.obter_fornecedor(fid)
        nome = _txt(dados, "nome", True, "Nome") if "nome" in dados else atual["nome"]
        doc = v.documento(dados["documento"]) if "documento" in dados else atual["documento"]
        with self._transacao():
            if doc and self._um("SELECT id FROM fornecedores WHERE documento = ? AND id <> ?", doc, fid):
                raise LojaError("Já existe fornecedor com este CPF/CNPJ")
            self.conn.execute(
                "UPDATE fornecedores SET nome=?, documento=?, telefone=?, email=?, endereco=?, ativo=?"
                " WHERE id=?",
                (nome, doc,
                 _txt(dados, "telefone", padrao=atual["telefone"]),
                 _txt(dados, "email", padrao=atual["email"]),
                 _txt(dados, "endereco", padrao=atual["endereco"]),
                 1 if dados.get("ativo", atual["ativo"]) not in (False, 0, "0") else 0,
                 fid))
        return self.obter_fornecedor(fid)

    def obter_fornecedor(self, fid):
        f = self._um("SELECT * FROM fornecedores WHERE id = ?", fid)
        if not f:
            raise NaoEncontrado(f"Fornecedor {fid} não encontrado")
        return f

    def listar_fornecedores(self, busca="", apenas_ativos=False):
        sql = "SELECT * FROM fornecedores WHERE (nome LIKE ? OR IFNULL(documento,'') LIKE ?)"
        if apenas_ativos:
            sql += " AND ativo = 1"
        termo = f"%{busca.strip()}%"
        return self._todos(sql + " ORDER BY nome", termo, termo)

    # --------------------------------------------------------------- produtos
    def _validar_unidade(self, unidade):
        u = str(unidade or "").strip().upper()
        if u not in UNIDADES:
            raise LojaError(f"Unidade inválida: {unidade}. Use: {', '.join(UNIDADES)}")
        return u

    def _quantidade(self, valor, unidade, campo="Quantidade", positivo=True):
        q = v.milesimos(valor, campo, positivo=positivo)
        if unidade not in FRACIONAVEIS and q % 1000:
            raise LojaError(f"{campo}: produto vendido em {UNIDADES[unidade]} aceita apenas quantidade inteira")
        return q

    def cadastrar_produto(self, dados):
        nome = _txt(dados, "nome", True, "Nome")
        unidade = self._validar_unidade(dados.get("unidade", "UN"))
        preco_venda = v.centavos(dados.get("preco_venda"), "Preço de venda", positivo=True)
        preco_custo = v.centavos(dados.get("preco_custo") or 0, "Preço de custo")
        minimo = self._quantidade(dados.get("estoque_minimo") or 0, unidade, "Estoque mínimo", positivo=False)
        inicial = self._quantidade(dados.get("estoque_inicial") or 0, unidade, "Estoque inicial", positivo=False)
        barras = _txt(dados, "codigo_barras") or None
        fornecedor_id = _opcional_id(dados.get("fornecedor_id"), "Fornecedor")
        with self._transacao():
            if fornecedor_id:
                self.obter_fornecedor(fornecedor_id)
            codigo = _txt(dados, "codigo")
            if not codigo:
                proximo = self._escalar("SELECT IFNULL(MAX(id), 0) + 1 FROM produtos")
                codigo = f"P{proximo:05d}"
                while self._um("SELECT id FROM produtos WHERE codigo = ?", codigo):
                    proximo += 1
                    codigo = f"P{proximo:05d}"
            if self._um("SELECT id FROM produtos WHERE codigo = ?", codigo):
                raise LojaError(f"Já existe produto com o código {codigo}")
            if barras and self._um("SELECT id FROM produtos WHERE codigo_barras = ?", barras):
                raise LojaError(f"Já existe produto com o código de barras {barras}")
            pid = self._inserir(
                "INSERT INTO produtos (codigo, codigo_barras, nome, categoria, unidade, preco_custo,"
                " preco_venda, estoque_minimo, localizacao, fornecedor_id, criado_em)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                codigo, barras, nome, _txt(dados, "categoria"), unidade, preco_custo,
                preco_venda, minimo, _txt(dados, "localizacao"), fornecedor_id, self.agora())
            if inicial:
                self._movimentar(pid, inicial, "ESTOQUE_INICIAL", "Cadastro", "", preco_custo)
        return self.obter_produto(pid)

    def atualizar_produto(self, pid, dados):
        with self._transacao():
            p = self.obter_produto(pid)
            if "estoque" in dados:
                raise LojaError("O estoque não é alterado no cadastro: use entrada de compra, ajuste ou perda")
            nome = _txt(dados, "nome", True, "Nome") if "nome" in dados else p["nome"]
            unidade = self._validar_unidade(dados["unidade"]) if "unidade" in dados else p["unidade"]
            if unidade not in FRACIONAVEIS and (p["estoque"] % 1000):
                raise LojaError("Não é possível mudar para unidade inteira com estoque fracionado")
            preco_venda = (v.centavos(dados["preco_venda"], "Preço de venda", positivo=True)
                           if "preco_venda" in dados else p["preco_venda"])
            preco_custo = (v.centavos(dados["preco_custo"] or 0, "Preço de custo")
                           if "preco_custo" in dados else p["preco_custo"])
            minimo = (self._quantidade(dados["estoque_minimo"] or 0, unidade, "Estoque mínimo", positivo=False)
                      if "estoque_minimo" in dados else p["estoque_minimo"])
            codigo = _txt(dados, "codigo", True, "Código") if "codigo" in dados else p["codigo"]
            barras = (_txt(dados, "codigo_barras") or None) if "codigo_barras" in dados else p["codigo_barras"]
            fornecedor_id = (_opcional_id(dados["fornecedor_id"], "Fornecedor")
                             if "fornecedor_id" in dados else p["fornecedor_id"])
            if fornecedor_id:
                self.obter_fornecedor(fornecedor_id)
            if self._um("SELECT id FROM produtos WHERE codigo = ? AND id <> ?", codigo, pid):
                raise LojaError(f"Já existe produto com o código {codigo}")
            if barras and self._um("SELECT id FROM produtos WHERE codigo_barras = ? AND id <> ?", barras, pid):
                raise LojaError(f"Já existe produto com o código de barras {barras}")
            ativo = 1 if dados.get("ativo", p["ativo"]) not in (False, 0, "0") else 0
            self.conn.execute(
                "UPDATE produtos SET codigo=?, codigo_barras=?, nome=?, categoria=?, unidade=?,"
                " preco_custo=?, preco_venda=?, estoque_minimo=?, localizacao=?, fornecedor_id=?, ativo=?"
                " WHERE id=?",
                (codigo, barras, nome, _txt(dados, "categoria", padrao=p["categoria"]), unidade,
                 preco_custo, preco_venda, minimo, _txt(dados, "localizacao", padrao=p["localizacao"]),
                 fornecedor_id, ativo, pid))
        return self.obter_produto(pid)

    def obter_produto(self, pid):
        p = self._um("SELECT * FROM produtos WHERE id = ?", pid)
        if not p:
            raise NaoEncontrado(f"Produto {pid} não encontrado")
        return p

    def buscar_produto_por_codigo(self, codigo):
        codigo = str(codigo).strip()
        p = self._um("SELECT * FROM produtos WHERE codigo = ? OR codigo_barras = ?", codigo, codigo)
        if not p:
            raise NaoEncontrado(f"Nenhum produto com o código {codigo}")
        return p

    def listar_produtos(self, busca="", categoria="", apenas_ativos=False, estoque_baixo=False):
        sql = ("SELECT * FROM produtos WHERE (nome LIKE ? OR codigo LIKE ? OR IFNULL(codigo_barras,'') LIKE ?)")
        termo = f"%{busca.strip()}%"
        args = [termo, termo, termo]
        if categoria:
            sql += " AND categoria = ?"
            args.append(categoria)
        if apenas_ativos:
            sql += " AND ativo = 1"
        if estoque_baixo:
            sql += " AND ativo = 1 AND estoque <= estoque_minimo"
        return self._todos(sql + " ORDER BY nome", *args)

    def listar_categorias(self):
        return [r["categoria"] for r in self._todos(
            "SELECT DISTINCT categoria FROM produtos WHERE categoria <> '' ORDER BY categoria")]

    # ---------------------------------------------------------------- estoque
    def _movimentar(self, pid, quantidade, tipo, referencia="", observacao="", custo=None):
        p = self.obter_produto(pid)
        novo = p["estoque"] + quantidade
        if novo < 0:
            raise LojaError(
                f"Estoque insuficiente de '{p['nome']}': disponível {v.formatar_quantidade(p['estoque'])} "
                f"{p['unidade']}, solicitado {v.formatar_quantidade(-quantidade)} {p['unidade']}")
        self.conn.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (novo, pid))
        self._inserir(
            "INSERT INTO movimentos_estoque (produto_id, data, tipo, quantidade, saldo_apos,"
            " custo_unitario, referencia, observacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            pid, self.agora(), tipo, quantidade, novo, custo, referencia, observacao)
        return novo

    def ajustar_estoque(self, pid, quantidade_contada, motivo):
        """Inventário: informa a quantidade contada e o sistema lança a diferença."""
        motivo = str(motivo or "").strip()
        if not motivo:
            raise LojaError("Informe o motivo do ajuste")
        with self._transacao():
            p = self.obter_produto(pid)
            contada = self._quantidade(quantidade_contada, p["unidade"], "Quantidade contada", positivo=False)
            diferenca = contada - p["estoque"]
            if diferenca == 0:
                raise LojaError("A quantidade contada é igual ao estoque atual; nada a ajustar")
            self._movimentar(pid, diferenca, "AJUSTE", "Inventário", motivo)
        return self.obter_produto(pid)

    def registrar_perda(self, pid, quantidade, motivo):
        """Quebra, avaria, vencimento (cimento empedrado, piso quebrado...)."""
        motivo = str(motivo or "").strip()
        if not motivo:
            raise LojaError("Informe o motivo da perda")
        with self._transacao():
            p = self.obter_produto(pid)
            q = self._quantidade(quantidade, p["unidade"])
            self._movimentar(pid, -q, "PERDA", "Perda/avaria", motivo, p["preco_custo"])
        return self.obter_produto(pid)

    def listar_movimentos(self, produto_id=None, limite=200):
        sql = ("SELECT m.*, p.nome AS produto, p.codigo, p.unidade FROM movimentos_estoque m"
               " JOIN produtos p ON p.id = m.produto_id")
        args = []
        if produto_id:
            sql += " WHERE m.produto_id = ?"
            args.append(produto_id)
        sql += " ORDER BY m.id DESC LIMIT ?"
        args.append(_int(limite, "Limite", 1, 10000))
        return self._todos(sql, *args)

    # ---------------------------------------------------------------- compras
    def registrar_compra(self, dados):
        """Entrada de mercadoria: soma estoque, atualiza custo médio e gera contas a pagar."""
        fornecedor_id = _int(dados.get("fornecedor_id"), "Fornecedor", 1)
        itens = _lista(dados.get("itens"), "Itens")
        if not itens:
            raise LojaError("Informe ao menos um item na compra")
        parcelas = _int(dados.get("parcelas") or 1, "Parcelas", 1, MAX_PARCELAS)
        primeiro_venc = (v.data_iso(dados["primeiro_vencimento"], "Primeiro vencimento")
                         if dados.get("primeiro_vencimento") else v.somar_meses(self.hoje(), 1))
        with self._transacao():
            fornecedor = self.obter_fornecedor(fornecedor_id)
            linhas = []
            for i, item in enumerate(itens, 1):
                p = self.obter_produto(_int(item.get("produto_id"), f"Item {i}: produto", 1))
                q = self._quantidade(item.get("quantidade"), p["unidade"], f"Item {i}: quantidade")
                custo = v.centavos(item.get("custo_unitario"), f"Item {i}: custo unitário")
                linhas.append((p, q, custo, v.multiplicar(custo, q)))
            total = sum(t for *_, t in linhas)
            nf = _txt(dados, "nota_fiscal")
            cid = self._inserir(
                "INSERT INTO compras (data, fornecedor_id, nota_fiscal, total, observacao) VALUES (?, ?, ?, ?, ?)",
                self.agora(), fornecedor_id, nf, total, _txt(dados, "observacao"))
            for p, q, custo, t in linhas:
                self._inserir(
                    "INSERT INTO compra_itens (compra_id, produto_id, quantidade, custo_unitario, total)"
                    " VALUES (?, ?, ?, ?, ?)", cid, p["id"], q, custo, t)
                atual = self.obter_produto(p["id"])
                # custo médio ponderado
                if atual["estoque"] > 0:
                    valor_atual = v.multiplicar(atual["preco_custo"], atual["estoque"])
                    novo_custo = v.proporcao(valor_atual + t, 1000, atual["estoque"] + q)
                else:
                    novo_custo = custo
                self.conn.execute("UPDATE produtos SET preco_custo = ? WHERE id = ?", (novo_custo, p["id"]))
                self._movimentar(p["id"], q, "COMPRA", f"Compra #{cid}", f"NF {nf}" if nf else "", custo)
            if total > 0:
                for n, valor in enumerate(v.ratear(total, [1] * parcelas), 1):
                    self._inserir(
                        "INSERT INTO contas_pagar (compra_id, fornecedor_id, descricao, parcela, total_parcelas,"
                        " emissao, vencimento, valor, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ABERTA')",
                        cid, fornecedor_id,
                        f"Compra #{cid} - {fornecedor['nome']}" + (f" - NF {nf}" if nf else ""),
                        n, parcelas, self.hoje().isoformat(),
                        v.somar_meses(primeiro_venc, n - 1).isoformat(), valor)
        return self.obter_compra(cid)

    def obter_compra(self, cid):
        c = self._um("SELECT c.*, f.nome AS fornecedor FROM compras c JOIN fornecedores f"
                     " ON f.id = c.fornecedor_id WHERE c.id = ?", cid)
        if not c:
            raise NaoEncontrado(f"Compra {cid} não encontrada")
        c["itens"] = self._todos(
            "SELECT i.*, p.nome AS produto, p.unidade FROM compra_itens i JOIN produtos p"
            " ON p.id = i.produto_id WHERE compra_id = ? ORDER BY i.id", cid)
        c["contas"] = self._todos("SELECT * FROM contas_pagar WHERE compra_id = ? ORDER BY parcela", cid)
        return c

    def listar_compras(self, limite=200):
        return self._todos(
            "SELECT c.*, f.nome AS fornecedor FROM compras c JOIN fornecedores f ON f.id = c.fornecedor_id"
            " ORDER BY c.id DESC LIMIT ?", _int(limite, "Limite", 1, 10000))

    # --------------------------------------------------------------- clientes
    def cadastrar_cliente(self, dados):
        nome = _txt(dados, "nome", True, "Nome")
        doc = v.documento(dados.get("documento"))
        limite = v.centavos(dados.get("limite_credito") or 0, "Limite de crédito")
        with self._transacao():
            if doc and self._um("SELECT id FROM clientes WHERE documento = ?", doc):
                raise LojaError("Já existe cliente com este CPF/CNPJ")
            cid = self._inserir(
                "INSERT INTO clientes (nome, documento, telefone, email, endereco, limite_credito, criado_em)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                nome, doc, _txt(dados, "telefone"), _txt(dados, "email"), _txt(dados, "endereco"),
                limite, self.agora())
        return self.obter_cliente(cid)

    def atualizar_cliente(self, cid, dados):
        with self._transacao():
            c = self.obter_cliente(cid)
            nome = _txt(dados, "nome", True, "Nome") if "nome" in dados else c["nome"]
            doc = v.documento(dados["documento"]) if "documento" in dados else c["documento"]
            limite = (v.centavos(dados["limite_credito"] or 0, "Limite de crédito")
                      if "limite_credito" in dados else c["limite_credito"])
            if doc and self._um("SELECT id FROM clientes WHERE documento = ? AND id <> ?", doc, cid):
                raise LojaError("Já existe cliente com este CPF/CNPJ")
            ativo = 1 if dados.get("ativo", c["ativo"]) not in (False, 0, "0") else 0
            self.conn.execute(
                "UPDATE clientes SET nome=?, documento=?, telefone=?, email=?, endereco=?, limite_credito=?,"
                " ativo=? WHERE id=?",
                (nome, doc, _txt(dados, "telefone", padrao=c["telefone"]),
                 _txt(dados, "email", padrao=c["email"]), _txt(dados, "endereco", padrao=c["endereco"]),
                 limite, ativo, cid))
        return self.obter_cliente(cid)

    def _saldo_devedor(self, cid):
        return self._escalar(
            "SELECT SUM(valor - valor_pago) FROM contas_receber WHERE cliente_id = ? AND status = 'ABERTA'", cid)

    def _vencido(self, cid):
        return self._escalar(
            "SELECT SUM(valor - valor_pago) FROM contas_receber WHERE cliente_id = ? AND status = 'ABERTA'"
            " AND vencimento < ?", cid, self.hoje().isoformat())

    def obter_cliente(self, cid):
        c = self._um("SELECT * FROM clientes WHERE id = ?", cid)
        if not c:
            raise NaoEncontrado(f"Cliente {cid} não encontrado")
        c["saldo_devedor"] = self._saldo_devedor(cid)
        c["valor_vencido"] = self._vencido(cid)
        c["credito_disponivel"] = max(0, c["limite_credito"] - c["saldo_devedor"])
        return c

    def listar_clientes(self, busca="", apenas_ativos=False):
        termo = f"%{busca.strip()}%"
        sql = ("SELECT c.*, IFNULL((SELECT SUM(valor - valor_pago) FROM contas_receber r"
               " WHERE r.cliente_id = c.id AND r.status = 'ABERTA'), 0) AS saldo_devedor"
               " FROM clientes c WHERE (c.nome LIKE ? OR IFNULL(c.documento,'') LIKE ? OR c.telefone LIKE ?)")
        if apenas_ativos:
            sql += " AND c.ativo = 1"
        return self._todos(sql + " ORDER BY c.nome", termo, termo, termo)

    def extrato_cliente(self, cid):
        c = self.obter_cliente(cid)
        c["vendas"] = self._todos(
            "SELECT id, data, total, status FROM vendas WHERE cliente_id = ? ORDER BY id DESC", cid)
        c["parcelas"] = self.listar_contas_receber(cliente_id=cid)
        c["recebimentos"] = self._todos(
            "SELECT r.*, c.parcela, c.total_parcelas, c.venda_id FROM recebimentos r"
            " JOIN contas_receber c ON c.id = r.conta_id WHERE c.cliente_id = ? ORDER BY r.id DESC", cid)
        return c

    # ------------------------------------------------------------------ caixa
    def _sessao_aberta(self, obrigatoria=True):
        s = self._um("SELECT * FROM caixa_sessoes WHERE status = 'ABERTO'")
        if not s and obrigatoria:
            raise LojaError("O caixa está fechado. Abra o caixa antes de continuar.")
        return s

    def _saldo_dinheiro(self, sessao):
        return sessao["valor_inicial"] + self._escalar(
            "SELECT SUM(valor) FROM caixa_movimentos WHERE sessao_id = ? AND forma = 'DINHEIRO'", sessao["id"])

    def _lancar_caixa(self, tipo, forma, valor, descricao, referencia=""):
        sessao = self._sessao_aberta()
        if valor < 0 and forma == "DINHEIRO":
            saldo = self._saldo_dinheiro(sessao)
            if saldo + valor < 0:
                raise LojaError(
                    f"Dinheiro insuficiente no caixa: saldo {v.formatar_reais(saldo)}, "
                    f"saída de {v.formatar_reais(-valor)}")
        self._inserir(
            "INSERT INTO caixa_movimentos (sessao_id, data, tipo, forma, valor, descricao, referencia)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)", sessao["id"], self.agora(), tipo, forma, valor, descricao, referencia)
        return sessao["id"]

    def abrir_caixa(self, valor_inicial=0, operador=""):
        valor = v.centavos(valor_inicial or 0, "Valor inicial (fundo de troco)")
        with self._transacao():
            if self._sessao_aberta(obrigatoria=False):
                raise LojaError("Já existe um caixa aberto")
            sid = self._inserir(
                "INSERT INTO caixa_sessoes (abertura, operador, valor_inicial, status) VALUES (?, ?, ?, 'ABERTO')",
                self.agora(), str(operador or "").strip(), valor)
        return self.obter_caixa(sid)

    def sangria(self, valor, motivo=""):
        valor = v.centavos(valor, "Valor da sangria", positivo=True)
        with self._transacao():
            self._lancar_caixa("SANGRIA", "DINHEIRO", -valor, str(motivo or "Sangria").strip())
        return self.caixa_atual()

    def suprimento(self, valor, motivo=""):
        valor = v.centavos(valor, "Valor do suprimento", positivo=True)
        with self._transacao():
            self._lancar_caixa("SUPRIMENTO", "DINHEIRO", valor, str(motivo or "Suprimento").strip())
        return self.caixa_atual()

    def obter_caixa(self, sid):
        s = self._um("SELECT * FROM caixa_sessoes WHERE id = ?", sid)
        if not s:
            raise NaoEncontrado(f"Sessão de caixa {sid} não encontrada")
        s["movimentos"] = self._todos("SELECT * FROM caixa_movimentos WHERE sessao_id = ? ORDER BY id", sid)
        totais = {}
        for m in s["movimentos"]:
            totais[m["forma"]] = totais.get(m["forma"], 0) + m["valor"]
        s["totais_por_forma"] = totais
        s["saldo_dinheiro"] = self._saldo_dinheiro(s)
        return s

    def caixa_atual(self):
        s = self._sessao_aberta(obrigatoria=False)
        return self.obter_caixa(s["id"]) if s else None

    def fechar_caixa(self, valor_contado, observacao=""):
        contado = v.centavos(valor_contado, "Valor contado em dinheiro")
        with self._transacao():
            s = self._sessao_aberta()
            esperado = self._saldo_dinheiro(s)
            self.conn.execute(
                "UPDATE caixa_sessoes SET status='FECHADO', fechamento=?, valor_esperado=?, valor_contado=?,"
                " diferenca=?, observacao=? WHERE id=?",
                (self.agora(), esperado, contado, contado - esperado, str(observacao or "").strip(), s["id"]))
        return self.obter_caixa(s["id"])

    def listar_sessoes_caixa(self, limite=60):
        return self._todos("SELECT * FROM caixa_sessoes ORDER BY id DESC LIMIT ?", _int(limite, "Limite", 1, 10000))

    # ------------------------------------------------------------------ vendas
    def _montar_itens(self, itens, precos_fixos=None):
        itens = _lista(itens, "Itens")
        if not itens:
            raise LojaError("Adicione ao menos um produto")
        linhas = []
        for i, item in enumerate(itens, 1):
            p = self.obter_produto(_int(item.get("produto_id"), f"Item {i}: produto", 1))
            if not p["ativo"]:
                raise LojaError(f"O produto '{p['nome']}' está inativo")
            q = self._quantidade(item.get("quantidade"), p["unidade"], f"Item {i} ({p['nome']}): quantidade")
            preco = precos_fixos[i - 1] if precos_fixos else p["preco_venda"]
            total = v.multiplicar(preco, q)
            if total <= 0:
                raise LojaError(f"Item {i} ({p['nome']}): quantidade pequena demais")
            linhas.append({"produto": p, "quantidade": q, "preco": preco, "total": total})
        return linhas

    def _desconto(self, dados, subtotal):
        desconto = v.centavos(dados.get("desconto") or 0, "Desconto")
        if dados.get("desconto_percentual") not in (None, "", 0, "0"):
            if desconto:
                raise LojaError("Informe desconto em valor OU em percentual, não os dois")
            pct = v.centavos(dados["desconto_percentual"], "Desconto (%)")  # em centésimos de %
            if pct > 10000:
                raise LojaError("Desconto (%): máximo 100%")
            desconto = v.proporcao(subtotal, pct, 10000)
        if desconto >= subtotal:
            raise LojaError("O desconto não pode ser igual ou maior que o valor da compra")
        return desconto

    def _validar_pagamentos(self, pagamentos, total):
        pagamentos = _lista(pagamentos, "Pagamentos")
        if not pagamentos:
            raise LojaError("Informe a forma de pagamento")
        por_forma = {}
        for i, pg in enumerate(pagamentos, 1):
            forma = str(pg.get("forma", "")).strip().upper()
            if forma not in FORMAS_PAGAMENTO:
                raise LojaError(f"Pagamento {i}: forma inválida '{pg.get('forma')}'")
            valor = v.centavos(pg.get("valor"), f"Pagamento {i} ({forma})", positivo=True)
            por_forma[forma] = por_forma.get(forma, 0) + valor
        dinheiro = por_forma.get("DINHEIRO", 0)
        outros = sum(val for f, val in por_forma.items() if f != "DINHEIRO")
        if outros > total:
            raise LojaError("Pagamentos em PIX/cartão/crediário passam do total da venda; "
                            "troco só é possível em dinheiro")
        falta = total - outros
        if dinheiro < falta:
            raise LojaError(f"Pagamento insuficiente: faltam {v.formatar_reais(falta - dinheiro)}")
        troco = dinheiro - falta
        if dinheiro and troco >= dinheiro:
            raise LojaError("Pagamento em dinheiro desnecessário: os outros pagamentos já cobrem o total")
        return por_forma, troco

    def _verificar_crediario(self, cliente, valor):
        if not cliente:
            raise LojaError("Venda no crediário exige um cliente cadastrado")
        if not cliente["ativo"]:
            raise LojaError("Cliente inativo não pode comprar no crediário")
        vencido = self._vencido(cliente["id"])
        if vencido > 0:
            raise LojaError(f"Cliente com parcelas em atraso ({v.formatar_reais(vencido)}). "
                            "Regularize antes de vender no crediário.")
        disponivel = cliente["limite_credito"] - self._saldo_devedor(cliente["id"])
        if valor > disponivel:
            raise LojaError(f"Limite de crédito insuficiente: disponível {v.formatar_reais(max(0, disponivel))}, "
                            f"solicitado {v.formatar_reais(valor)}")

    def registrar_venda(self, dados, _precos_fixos=None, _orcamento_id=None):
        """dados: itens [{produto_id, quantidade}], pagamentos [{forma, valor}],
        cliente_id, desconto | desconto_percentual, crediario {parcelas, primeiro_vencimento}."""
        with self._transacao():
            sessao = self._sessao_aberta()
            cliente_id = _opcional_id(dados.get("cliente_id"), "Cliente")
            cliente = self.obter_cliente(cliente_id) if cliente_id else None
            linhas = self._montar_itens(dados.get("itens"), _precos_fixos)
            subtotal = sum(l["total"] for l in linhas)
            desconto = self._desconto(dados, subtotal)
            total = subtotal - desconto
            por_forma, troco = self._validar_pagamentos(dados.get("pagamentos"), total)

            valor_crediario = por_forma.get("CREDIARIO", 0)
            if valor_crediario:
                self._verificar_crediario(cliente, valor_crediario)
                cred = _objeto(dados.get("crediario"), "Crediário")
                n_parcelas = _int(cred.get("parcelas") or 1, "Número de parcelas", 1, MAX_PARCELAS)
                primeiro = (v.data_iso(cred["primeiro_vencimento"], "Primeiro vencimento")
                            if cred.get("primeiro_vencimento") else v.somar_meses(self.hoje(), 1))
                if primeiro < self.hoje():
                    raise LojaError("O primeiro vencimento não pode ser no passado")

            vid = self._inserir(
                "INSERT INTO vendas (data, cliente_id, caixa_sessao_id, orcamento_id, subtotal, desconto, total,"
                " status, observacao) VALUES (?, ?, ?, ?, ?, ?, ?, 'CONCLUIDA', ?)",
                self.agora(), cliente_id, sessao["id"], _orcamento_id, subtotal, desconto, total,
                _txt(dados, "observacao"))
            liquidos = v.ratear(total, [l["total"] for l in linhas])
            for l, liquido in zip(linhas, liquidos):
                p = l["produto"]
                self._inserir(
                    "INSERT INTO venda_itens (venda_id, produto_id, descricao, unidade, quantidade, preco_unitario,"
                    " custo_unitario, total, total_liquido) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    vid, p["id"], p["nome"], p["unidade"], l["quantidade"], l["preco"], p["preco_custo"],
                    l["total"], liquido)
                self._movimentar(p["id"], -l["quantidade"], "VENDA", f"Venda #{vid}")

            for forma, valor in por_forma.items():
                t = troco if forma == "DINHEIRO" else 0
                self._inserir("INSERT INTO venda_pagamentos (venda_id, forma, valor, troco) VALUES (?, ?, ?, ?)",
                              vid, forma, valor, t)
                if forma != "CREDIARIO":
                    self._lancar_caixa("VENDA", forma, valor - t, f"Venda #{vid}", f"venda:{vid}")

            if valor_crediario:
                for n, valor in enumerate(v.ratear(valor_crediario, [1] * n_parcelas), 1):
                    self._inserir(
                        "INSERT INTO contas_receber (venda_id, cliente_id, parcela, total_parcelas, emissao,"
                        " vencimento, valor_original, valor, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ABERTA')",
                        vid, cliente_id, n, n_parcelas, self.hoje().isoformat(),
                        v.somar_meses(primeiro, n - 1).isoformat(), valor, valor)
        return self.obter_venda(vid)

    def obter_venda(self, vid):
        venda = self._um(
            "SELECT v.*, c.nome AS cliente, c.documento AS cliente_documento FROM vendas v"
            " LEFT JOIN clientes c ON c.id = v.cliente_id WHERE v.id = ?", vid)
        if not venda:
            raise NaoEncontrado(f"Venda {vid} não encontrada")
        venda["itens"] = self._todos("SELECT * FROM venda_itens WHERE venda_id = ? ORDER BY id", vid)
        venda["pagamentos"] = self._todos("SELECT * FROM venda_pagamentos WHERE venda_id = ? ORDER BY id", vid)
        venda["troco"] = sum(p["troco"] for p in venda["pagamentos"])
        venda["parcelas"] = self._todos("SELECT * FROM contas_receber WHERE venda_id = ? ORDER BY parcela", vid)
        venda["devolucoes"] = self._todos("SELECT * FROM devolucoes WHERE venda_id = ? ORDER BY id", vid)
        venda["total_devolvido"] = sum(d["valor"] for d in venda["devolucoes"])
        return venda

    def listar_vendas(self, inicio=None, fim=None, cliente_id=None, status=None, limite=500):
        sql = ("SELECT v.*, c.nome AS cliente, IFNULL((SELECT SUM(valor) FROM devolucoes d"
               " WHERE d.venda_id = v.id), 0) AS total_devolvido,"
               " (SELECT GROUP_CONCAT(forma, ', ') FROM venda_pagamentos p WHERE p.venda_id = v.id) AS formas"
               " FROM vendas v LEFT JOIN clientes c ON c.id = v.cliente_id WHERE 1=1")
        args = []
        if inicio:
            sql += " AND date(v.data) >= ?"
            args.append(v.data_iso(inicio).isoformat())
        if fim:
            sql += " AND date(v.data) <= ?"
            args.append(v.data_iso(fim).isoformat())
        if cliente_id:
            sql += " AND v.cliente_id = ?"
            args.append(cliente_id)
        if status:
            sql += " AND v.status = ?"
            args.append(status)
        sql += " ORDER BY v.id DESC LIMIT ?"
        args.append(_int(limite, "Limite", 1, 100000))
        return self._todos(sql, *args)

    def cancelar_venda(self, vid, motivo):
        motivo = str(motivo or "").strip()
        if not motivo:
            raise LojaError("Informe o motivo do cancelamento")
        with self._transacao():
            venda = self.obter_venda(vid)
            if venda["status"] != "CONCLUIDA":
                raise LojaError("Esta venda já está cancelada")
            if venda["devolucoes"]:
                raise LojaError("Venda com devolução registrada não pode ser cancelada; use devolução dos itens restantes")
            if any(p["valor_pago"] for p in venda["parcelas"]):
                raise LojaError("Venda com parcelas já pagas não pode ser cancelada; use devolução")
            self._sessao_aberta()
            for item in venda["itens"]:
                self._movimentar(item["produto_id"], item["quantidade"], "CANCELAMENTO_VENDA",
                                 f"Venda #{vid}", motivo)
            for pg in venda["pagamentos"]:
                if pg["forma"] != "CREDIARIO":
                    self._lancar_caixa("ESTORNO_VENDA", pg["forma"], -(pg["valor"] - pg["troco"]),
                                       f"Cancelamento da venda #{vid}", f"venda:{vid}")
            self.conn.execute(
                "UPDATE contas_receber SET status = 'CANCELADA' WHERE venda_id = ? AND status = 'ABERTA'", (vid,))
            self.conn.execute(
                "UPDATE vendas SET status = 'CANCELADA', cancelada_em = ?, motivo_cancelamento = ? WHERE id = ?",
                (self.agora(), motivo, vid))
        return self.obter_venda(vid)

    def registrar_devolucao(self, vid, dados):
        """dados: itens [{item_id, quantidade}], motivo, forma_reembolso.
        O valor devolvido primeiro abate o que o cliente ainda deve no crediário desta venda;
        o que sobrar é reembolsado."""
        forma = str(dados.get("forma_reembolso") or "DINHEIRO").strip().upper()
        if forma not in FORMAS_REEMBOLSO:
            raise LojaError(f"Forma de reembolso inválida: {forma}")
        itens = _lista(dados.get("itens"), "Itens")
        if not itens:
            raise LojaError("Informe os itens devolvidos")
        with self._transacao():
            venda = self.obter_venda(vid)
            if venda["status"] != "CONCLUIDA":
                raise LojaError("Venda cancelada não aceita devolução")
            self._sessao_aberta()
            por_id = {i["id"]: i for i in venda["itens"]}
            pedidos = {}
            for n, it in enumerate(itens, 1):
                item_id = _int(it.get("item_id"), f"Item {n}", 1)
                if item_id not in por_id:
                    raise LojaError(f"Item {item_id} não pertence à venda #{vid}")
                q = self._quantidade(it.get("quantidade"), por_id[item_id]["unidade"], f"Item {n}: quantidade")
                pedidos[item_id] = pedidos.get(item_id, 0) + q
            linhas = []
            for item_id, q in pedidos.items():
                item = por_id[item_id]
                restante = item["quantidade"] - item["quantidade_devolvida"]
                if q > restante:
                    raise LojaError(
                        f"'{item['descricao']}': só restam {v.formatar_quantidade(restante)} {item['unidade']} "
                        "para devolver")
                if q == restante:
                    valor = item["total_liquido"] - item["valor_devolvido"]
                else:
                    valor = min(v.proporcao(item["total_liquido"], q, item["quantidade"]),
                                item["total_liquido"] - item["valor_devolvido"])
                linhas.append((item, q, valor))
            valor_total = sum(l[2] for l in linhas)

            # abate do saldo em aberto do crediário desta venda (das últimas parcelas para as primeiras)
            abatido = 0
            restante_abater = valor_total
            abertas = [p for p in venda["parcelas"] if p["status"] == "ABERTA"]
            for p in sorted(abertas, key=lambda x: x["parcela"], reverse=True):
                if restante_abater <= 0:
                    break
                reducao = min(restante_abater, p["valor"] - p["valor_pago"])
                novo_valor = p["valor"] - reducao
                if novo_valor == p["valor_pago"]:
                    status = "PAGA" if p["valor_pago"] > 0 else "CANCELADA"
                else:
                    status = "ABERTA"
                self.conn.execute("UPDATE contas_receber SET valor = ?, status = ? WHERE id = ?",
                                  (novo_valor, status, p["id"]))
                abatido += reducao
                restante_abater -= reducao
            reembolso = valor_total - abatido

            did = self._inserir(
                "INSERT INTO devolucoes (venda_id, data, valor, valor_abatido, valor_reembolsado, forma_reembolso,"
                " motivo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                vid, self.agora(), valor_total, abatido, reembolso, forma, _txt(dados, "motivo"))
            for item, q, valor in linhas:
                self._inserir(
                    "INSERT INTO devolucao_itens (devolucao_id, venda_item_id, quantidade, valor) VALUES (?, ?, ?, ?)",
                    did, item["id"], q, valor)
                self.conn.execute(
                    "UPDATE venda_itens SET quantidade_devolvida = quantidade_devolvida + ?,"
                    " valor_devolvido = valor_devolvido + ? WHERE id = ?", (q, valor, item["id"]))
                self._movimentar(item["produto_id"], q, "DEVOLUCAO", f"Venda #{vid} / Devolução #{did}",
                                 _txt(dados, "motivo"))
            if reembolso > 0:
                self._lancar_caixa("REEMBOLSO", forma, -reembolso, f"Devolução #{did} da venda #{vid}",
                                   f"devolucao:{did}")
        resultado = self._um("SELECT * FROM devolucoes WHERE id = ?", did)
        resultado["itens"] = self._todos("SELECT * FROM devolucao_itens WHERE devolucao_id = ?", did)
        return resultado

    # -------------------------------------------------------------- orçamentos
    def criar_orcamento(self, dados):
        validade_dias = _int(dados.get("validade_dias") or 10, "Validade (dias)", 1, 365)
        with self._transacao():
            cliente_id = _opcional_id(dados.get("cliente_id"), "Cliente")
            if cliente_id:
                self.obter_cliente(cliente_id)
            linhas = self._montar_itens(dados.get("itens"))
            subtotal = sum(l["total"] for l in linhas)
            desconto = self._desconto(dados, subtotal)
            oid = self._inserir(
                "INSERT INTO orcamentos (data, validade, cliente_id, nome_cliente, subtotal, desconto, total,"
                " status, observacao) VALUES (?, ?, ?, ?, ?, ?, ?, 'ABERTO', ?)",
                self.agora(), (self.hoje() + datetime.timedelta(days=validade_dias)).isoformat(),
                cliente_id, _txt(dados, "nome_cliente"), subtotal, desconto, subtotal - desconto,
                _txt(dados, "observacao"))
            for l in linhas:
                p = l["produto"]
                self._inserir(
                    "INSERT INTO orcamento_itens (orcamento_id, produto_id, descricao, unidade, quantidade,"
                    " preco_unitario, total) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    oid, p["id"], p["nome"], p["unidade"], l["quantidade"], l["preco"], l["total"])
        return self.obter_orcamento(oid)

    def obter_orcamento(self, oid):
        o = self._um("SELECT o.*, c.nome AS cliente FROM orcamentos o LEFT JOIN clientes c"
                     " ON c.id = o.cliente_id WHERE o.id = ?", oid)
        if not o:
            raise NaoEncontrado(f"Orçamento {oid} não encontrado")
        o["itens"] = self._todos(
            "SELECT i.*, p.estoque FROM orcamento_itens i JOIN produtos p ON p.id = i.produto_id"
            " WHERE orcamento_id = ? ORDER BY i.id", oid)
        o["vencido"] = o["status"] == "ABERTO" and o["validade"] < self.hoje().isoformat()
        return o

    def listar_orcamentos(self, status=None, limite=300):
        sql = ("SELECT o.*, c.nome AS cliente FROM orcamentos o LEFT JOIN clientes c ON c.id = o.cliente_id")
        args = []
        if status:
            sql += " WHERE o.status = ?"
            args.append(status)
        sql += " ORDER BY o.id DESC LIMIT ?"
        args.append(_int(limite, "Limite", 1, 100000))
        return self._todos(sql, *args)

    def cancelar_orcamento(self, oid):
        with self._transacao():
            o = self.obter_orcamento(oid)
            if o["status"] != "ABERTO":
                raise LojaError("Só orçamentos em aberto podem ser cancelados")
            self.conn.execute("UPDATE orcamentos SET status = 'CANCELADO' WHERE id = ?", (oid,))
        return self.obter_orcamento(oid)

    def converter_orcamento(self, oid, dados):
        """Transforma o orçamento em venda, mantendo os preços e o desconto combinados."""
        with self._transacao():
            o = self.obter_orcamento(oid)
            if o["status"] != "ABERTO":
                raise LojaError("Este orçamento não está em aberto")
            if o["vencido"]:
                raise LojaError("Orçamento vencido: faça um novo orçamento com os preços atuais")
            venda_dados = {
                "itens": [{"produto_id": i["produto_id"], "quantidade": Decimal(i["quantidade"]) / 1000}
                          for i in o["itens"]],
                "desconto": Decimal(o["desconto"]) / 100,
                "cliente_id": dados.get("cliente_id") or o["cliente_id"],
                "pagamentos": dados.get("pagamentos"),
                "crediario": dados.get("crediario"),
                "observacao": dados.get("observacao") or f"Orçamento #{oid}",
            }
            venda = self.registrar_venda(venda_dados, _precos_fixos=[i["preco_unitario"] for i in o["itens"]],
                                         _orcamento_id=oid)
            self.conn.execute("UPDATE orcamentos SET status = 'CONVERTIDO', venda_id = ? WHERE id = ?",
                              (venda["id"], oid))
        return self.obter_venda(venda["id"])

    # ------------------------------------------------------- contas a receber
    def listar_contas_receber(self, cliente_id=None, status=None, vencidas=False):
        sql = ("SELECT r.*, c.nome AS cliente, r.valor - r.valor_pago AS restante FROM contas_receber r"
               " JOIN clientes c ON c.id = r.cliente_id WHERE 1=1")
        args = []
        if cliente_id:
            sql += " AND r.cliente_id = ?"
            args.append(cliente_id)
        if status:
            sql += " AND r.status = ?"
            args.append(status)
        if vencidas:
            sql += " AND r.status = 'ABERTA' AND r.vencimento < ?"
            args.append(self.hoje().isoformat())
        contas = self._todos(sql + " ORDER BY r.vencimento, r.id", *args)
        hoje = self.hoje().isoformat()
        for c in contas:
            c["vencida"] = c["status"] == "ABERTA" and c["vencimento"] < hoje
        return contas

    def receber_parcela(self, conta_id, valor, forma="DINHEIRO"):
        forma = str(forma or "").strip().upper()
        if forma not in FORMAS_RECEBIMENTO:
            raise LojaError(f"Forma de recebimento inválida: {forma}")
        valor = v.centavos(valor, "Valor recebido", positivo=True)
        with self._transacao():
            conta = self._um("SELECT * FROM contas_receber WHERE id = ?", conta_id)
            if not conta:
                raise NaoEncontrado(f"Parcela {conta_id} não encontrada")
            if conta["status"] != "ABERTA":
                raise LojaError("Esta parcela não está em aberto")
            restante = conta["valor"] - conta["valor_pago"]
            if valor > restante:
                raise LojaError(f"Valor maior que o saldo da parcela ({v.formatar_reais(restante)})")
            sid = self._lancar_caixa(
                "RECEBIMENTO", forma, valor,
                f"Parcela {conta['parcela']}/{conta['total_parcelas']} da venda #{conta['venda_id']}",
                f"conta_receber:{conta_id}")
            self._inserir("INSERT INTO recebimentos (conta_id, data, valor, forma, caixa_sessao_id)"
                          " VALUES (?, ?, ?, ?, ?)", conta_id, self.agora(), valor, forma, sid)
            pago = conta["valor_pago"] + valor
            self.conn.execute("UPDATE contas_receber SET valor_pago = ?, status = ? WHERE id = ?",
                              (pago, "PAGA" if pago == conta["valor"] else "ABERTA", conta_id))
        return self._um("SELECT *, valor - valor_pago AS restante FROM contas_receber WHERE id = ?", conta_id)

    def receber_do_cliente(self, cliente_id, valor, forma="DINHEIRO"):
        """Recebe um valor do cliente e quita as parcelas mais antigas primeiro."""
        valor = v.centavos(valor, "Valor recebido", positivo=True)
        with self._transacao():
            self.obter_cliente(cliente_id)
            divida = self._saldo_devedor(cliente_id)
            if valor > divida:
                raise LojaError(f"Valor maior que o saldo devedor do cliente ({v.formatar_reais(divida)})")
            restante = valor
            quitadas = []
            for conta in self._todos(
                    "SELECT * FROM contas_receber WHERE cliente_id = ? AND status = 'ABERTA'"
                    " ORDER BY vencimento, id", cliente_id):
                if restante <= 0:
                    break
                parte = min(restante, conta["valor"] - conta["valor_pago"])
                self.receber_parcela(conta["id"], Decimal(parte) / 100, forma)
                quitadas.append({"conta_id": conta["id"], "valor": parte})
                restante -= parte
        return {"recebido": valor, "parcelas": quitadas, "cliente": self.obter_cliente(cliente_id)}

    # --------------------------------------------------------- contas a pagar
    def lancar_conta_pagar(self, dados):
        descricao = _txt(dados, "descricao", True, "Descrição")
        valor = v.centavos(dados.get("valor"), "Valor", positivo=True)
        vencimento = v.data_iso(dados.get("vencimento"), "Vencimento")
        with self._transacao():
            fid = _opcional_id(dados.get("fornecedor_id"), "Fornecedor")
            if fid:
                self.obter_fornecedor(fid)
            cid = self._inserir(
                "INSERT INTO contas_pagar (fornecedor_id, descricao, emissao, vencimento, valor, status)"
                " VALUES (?, ?, ?, ?, ?, 'ABERTA')", fid, descricao, self.hoje().isoformat(),
                vencimento.isoformat(), valor)
        return self._um("SELECT * FROM contas_pagar WHERE id = ?", cid)

    def pagar_conta(self, conta_id, valor, forma="PIX"):
        forma = str(forma or "").strip().upper()
        if forma not in FORMAS_PAGAMENTO_CONTA:
            raise LojaError(f"Forma de pagamento inválida: {forma}")
        valor = v.centavos(valor, "Valor pago", positivo=True)
        with self._transacao():
            conta = self._um("SELECT * FROM contas_pagar WHERE id = ?", conta_id)
            if not conta:
                raise NaoEncontrado(f"Conta {conta_id} não encontrada")
            if conta["status"] != "ABERTA":
                raise LojaError("Esta conta não está em aberto")
            restante = conta["valor"] - conta["valor_pago"]
            if valor > restante:
                raise LojaError(f"Valor maior que o saldo da conta ({v.formatar_reais(restante)})")
            if forma == "DINHEIRO_CAIXA":
                self._lancar_caixa("PAGAMENTO_CONTA", "DINHEIRO", -valor, conta["descricao"],
                                   f"conta_pagar:{conta_id}")
            self._inserir("INSERT INTO pagamentos_contas (conta_id, data, valor, forma) VALUES (?, ?, ?, ?)",
                          conta_id, self.agora(), valor, forma)
            pago = conta["valor_pago"] + valor
            self.conn.execute("UPDATE contas_pagar SET valor_pago = ?, status = ? WHERE id = ?",
                              (pago, "PAGA" if pago == conta["valor"] else "ABERTA", conta_id))
        return self._um("SELECT *, valor - valor_pago AS restante FROM contas_pagar WHERE id = ?", conta_id)

    def cancelar_conta_pagar(self, conta_id):
        with self._transacao():
            conta = self._um("SELECT * FROM contas_pagar WHERE id = ?", conta_id)
            if not conta:
                raise NaoEncontrado(f"Conta {conta_id} não encontrada")
            if conta["status"] != "ABERTA" or conta["valor_pago"]:
                raise LojaError("Só contas em aberto e sem pagamentos podem ser canceladas")
            self.conn.execute("UPDATE contas_pagar SET status = 'CANCELADA' WHERE id = ?", (conta_id,))
        return self._um("SELECT * FROM contas_pagar WHERE id = ?", conta_id)

    def listar_contas_pagar(self, status=None, vencidas=False):
        sql = ("SELECT p.*, f.nome AS fornecedor, p.valor - p.valor_pago AS restante FROM contas_pagar p"
               " LEFT JOIN fornecedores f ON f.id = p.fornecedor_id WHERE 1=1")
        args = []
        if status:
            sql += " AND p.status = ?"
            args.append(status)
        if vencidas:
            sql += " AND p.status = 'ABERTA' AND p.vencimento < ?"
            args.append(self.hoje().isoformat())
        contas = self._todos(sql + " ORDER BY p.vencimento, p.id", *args)
        hoje = self.hoje().isoformat()
        for c in contas:
            c["vencida"] = c["status"] == "ABERTA" and c["vencimento"] < hoje
        return contas

    # ------------------------------------------------------------- relatórios
    def relatorio_vendas(self, inicio=None, fim=None):
        inicio = v.data_iso(inicio or self.hoje())
        fim = v.data_iso(fim or self.hoje())
        if fim < inicio:
            raise LojaError("A data final é anterior à inicial")
        periodo = (inicio.isoformat(), fim.isoformat())
        filtro = "date(v.data) BETWEEN ? AND ? AND v.status = 'CONCLUIDA'"
        r = self._um(
            f"SELECT COUNT(*) AS quantidade, IFNULL(SUM(subtotal), 0) AS bruto, IFNULL(SUM(desconto), 0)"
            f" AS descontos, IFNULL(SUM(total), 0) AS total FROM vendas v WHERE {filtro}", *periodo)
        r["inicio"], r["fim"] = periodo
        r["devolucoes"] = self._escalar(
            f"SELECT SUM(d.valor) FROM devolucoes d JOIN vendas v ON v.id = d.venda_id WHERE {filtro}", *periodo)
        r["liquido"] = r["total"] - r["devolucoes"]
        itens = self._todos(
            f"SELECT i.custo_unitario, i.quantidade - i.quantidade_devolvida AS qtd FROM venda_itens i"
            f" JOIN vendas v ON v.id = i.venda_id WHERE {filtro}", *periodo)
        r["custo_mercadorias"] = sum(v.multiplicar(i["custo_unitario"], i["qtd"]) for i in itens)
        r["lucro_bruto"] = r["liquido"] - r["custo_mercadorias"]
        r["ticket_medio"] = r["total"] // r["quantidade"] if r["quantidade"] else 0
        r["canceladas"] = self._escalar(
            "SELECT COUNT(*) FROM vendas v WHERE date(v.data) BETWEEN ? AND ? AND v.status = 'CANCELADA'", *periodo)
        r["por_forma"] = {
            f["forma"]: f["valor"] for f in self._todos(
                f"SELECT p.forma, SUM(p.valor - p.troco) AS valor FROM venda_pagamentos p"
                f" JOIN vendas v ON v.id = p.venda_id WHERE {filtro} GROUP BY p.forma ORDER BY p.forma", *periodo)}
        r["recebimentos_crediario"] = self._escalar(
            "SELECT SUM(valor) FROM recebimentos WHERE date(data) BETWEEN ? AND ?", *periodo)
        return r

    def mais_vendidos(self, inicio=None, fim=None, limite=20):
        inicio = v.data_iso(inicio or self.hoje() - datetime.timedelta(days=30))
        fim = v.data_iso(fim or self.hoje())
        return self._todos(
            "SELECT i.produto_id, p.codigo, p.nome, p.unidade,"
            " SUM(i.quantidade - i.quantidade_devolvida) AS quantidade,"
            " SUM(i.total_liquido - i.valor_devolvido) AS valor"
            " FROM venda_itens i JOIN vendas v ON v.id = i.venda_id JOIN produtos p ON p.id = i.produto_id"
            " WHERE v.status = 'CONCLUIDA' AND date(v.data) BETWEEN ? AND ?"
            " GROUP BY i.produto_id HAVING quantidade > 0 ORDER BY valor DESC LIMIT ?",
            inicio.isoformat(), fim.isoformat(), _int(limite, "Limite", 1, 1000))

    def relatorio_estoque(self):
        produtos = self.listar_produtos(apenas_ativos=True)
        return {
            "produtos": len(produtos),
            "valor_custo": sum(v.multiplicar(p["preco_custo"], p["estoque"]) for p in produtos),
            "valor_venda": sum(v.multiplicar(p["preco_venda"], p["estoque"]) for p in produtos),
            "estoque_baixo": self.listar_produtos(estoque_baixo=True),
            "sem_estoque": [p for p in produtos if p["estoque"] == 0],
        }

    def painel(self):
        hoje = self.hoje().isoformat()
        caixa = self.caixa_atual()
        return {
            "data": hoje,
            "vendas_hoje": self.relatorio_vendas(hoje, hoje),
            "caixa": None if not caixa else {
                "id": caixa["id"], "abertura": caixa["abertura"], "saldo_dinheiro": caixa["saldo_dinheiro"],
                "totais_por_forma": caixa["totais_por_forma"]},
            "estoque_baixo": len(self.listar_produtos(estoque_baixo=True)),
            "receber_vencido": self._escalar(
                "SELECT SUM(valor - valor_pago) FROM contas_receber WHERE status = 'ABERTA' AND vencimento < ?", hoje),
            "receber_aberto": self._escalar(
                "SELECT SUM(valor - valor_pago) FROM contas_receber WHERE status = 'ABERTA'"),
            "pagar_7_dias": self._escalar(
                "SELECT SUM(valor - valor_pago) FROM contas_pagar WHERE status = 'ABERTA' AND vencimento <= ?",
                (self.hoje() + datetime.timedelta(days=7)).isoformat()),
            "orcamentos_abertos": self._escalar(
                "SELECT COUNT(*) FROM orcamentos WHERE status = 'ABERTO' AND validade >= ?", hoje),
        }

    # ------------------------------------------------------------- auditoria
    def verificar_integridade(self):
        """Confere se estoque, vendas, pagamentos, parcelas e caixa batem entre si.
        Retorna a lista de problemas encontrados (vazia = tudo certo)."""
        problemas = []
        q = self._todos
        for p in q("SELECT p.id, p.nome, p.estoque, IFNULL(SUM(m.quantidade), 0) AS soma,"
                   " (SELECT saldo_apos FROM movimentos_estoque WHERE produto_id = p.id ORDER BY id DESC LIMIT 1)"
                   " AS ultimo FROM produtos p LEFT JOIN movimentos_estoque m ON m.produto_id = p.id GROUP BY p.id"):
            if p["estoque"] != p["soma"] or (p["ultimo"] is not None and p["ultimo"] != p["estoque"]):
                problemas.append(f"Produto {p['id']} ({p['nome']}): estoque {p['estoque']} não bate com "
                                 f"movimentos ({p['soma']})")
        for p in q("SELECT p.id, p.nome,"
                   " -IFNULL((SELECT SUM(quantidade) FROM movimentos_estoque WHERE produto_id = p.id"
                   "  AND tipo = 'VENDA'), 0) AS mov_venda,"
                   " IFNULL((SELECT SUM(quantidade) FROM venda_itens WHERE produto_id = p.id), 0) AS vendido,"
                   " IFNULL((SELECT SUM(quantidade) FROM movimentos_estoque WHERE produto_id = p.id"
                   "  AND tipo = 'DEVOLUCAO'), 0) AS mov_dev,"
                   " IFNULL((SELECT SUM(quantidade_devolvida) FROM venda_itens WHERE produto_id = p.id), 0) AS dev,"
                   " IFNULL((SELECT SUM(quantidade) FROM movimentos_estoque WHERE produto_id = p.id"
                   "  AND tipo = 'CANCELAMENTO_VENDA'), 0) AS mov_canc,"
                   " IFNULL((SELECT SUM(i.quantidade) FROM venda_itens i JOIN vendas v ON v.id = i.venda_id"
                   "  WHERE i.produto_id = p.id AND v.status = 'CANCELADA'), 0) AS canc"
                   " FROM produtos p"):
            if (p["mov_venda"], p["mov_dev"], p["mov_canc"]) != (p["vendido"], p["dev"], p["canc"]):
                problemas.append(f"Produto {p['id']} ({p['nome']}): movimentos de venda/devolução/cancelamento "
                                 "não batem com as vendas")
        for venda in q("SELECT * FROM vendas"):
            vid = venda["id"]
            itens = q("SELECT * FROM venda_itens WHERE venda_id = ?", vid)
            if sum(i["total"] for i in itens) != venda["subtotal"]:
                problemas.append(f"Venda {vid}: soma dos itens difere do subtotal")
            if sum(i["total_liquido"] for i in itens) != venda["total"]:
                problemas.append(f"Venda {vid}: rateio do desconto não fecha com o total")
            for i in itens:
                if i["total"] != v.multiplicar(i["preco_unitario"], i["quantidade"]):
                    problemas.append(f"Venda {vid}: item {i['id']} com total diferente de preço x quantidade")
            pags = q("SELECT * FROM venda_pagamentos WHERE venda_id = ?", vid)
            if sum(p["valor"] - p["troco"] for p in pags) != venda["total"]:
                problemas.append(f"Venda {vid}: pagamentos não fecham com o total")
            cred = sum(p["valor"] for p in pags if p["forma"] == "CREDIARIO")
            parcelas = q("SELECT * FROM contas_receber WHERE venda_id = ?", vid)
            if sum(p["valor_original"] for p in parcelas) != cred:
                problemas.append(f"Venda {vid}: parcelas do crediário não somam o valor do crediário")
            abatido = self._escalar("SELECT SUM(valor_abatido) FROM devolucoes WHERE venda_id = ?", vid)
            if venda["status"] == "CONCLUIDA" and sum(p["valor"] for p in parcelas) != cred - abatido:
                problemas.append(f"Venda {vid}: saldo do crediário não confere com as devoluções")
            if venda["status"] == "CANCELADA" and any(p["status"] == "ABERTA" for p in parcelas):
                problemas.append(f"Venda {vid}: cancelada, mas com parcela em aberto")
            caixa = self._escalar("SELECT SUM(valor) FROM caixa_movimentos WHERE referencia = ?", f"venda:{vid}")
            esperado = 0 if venda["status"] == "CANCELADA" else venda["total"] - cred
            if caixa != esperado:
                problemas.append(f"Venda {vid}: lançamentos de caixa ({caixa}) diferentes do esperado ({esperado})")
        for d in q("SELECT d.*, IFNULL((SELECT SUM(valor) FROM devolucao_itens WHERE devolucao_id = d.id), 0)"
                   " AS soma FROM devolucoes d"):
            if d["soma"] != d["valor"]:
                problemas.append(f"Devolução {d['id']}: itens não somam o valor da devolução")
        for i in q("SELECT i.id, i.quantidade_devolvida, i.valor_devolvido,"
                   " IFNULL(SUM(d.quantidade), 0) AS q, IFNULL(SUM(d.valor), 0) AS val FROM venda_itens i"
                   " LEFT JOIN devolucao_itens d ON d.venda_item_id = i.id GROUP BY i.id"):
            if (i["q"], i["val"]) != (i["quantidade_devolvida"], i["valor_devolvido"]):
                problemas.append(f"Item de venda {i['id']}: devolução registrada não confere")
        for c in q("SELECT c.*, IFNULL((SELECT SUM(valor) FROM recebimentos WHERE conta_id = c.id), 0) AS soma"
                   " FROM contas_receber c"):
            if c["soma"] != c["valor_pago"]:
                problemas.append(f"Conta a receber {c['id']}: valor pago não bate com os recebimentos")
            if c["status"] == "ABERTA" and c["valor_pago"] >= c["valor"]:
                problemas.append(f"Conta a receber {c['id']}: quitada mas marcada como aberta")
            if c["status"] == "PAGA" and c["valor_pago"] != c["valor"]:
                problemas.append(f"Conta a receber {c['id']}: marcada como paga sem quitação")
        for c in q("SELECT c.*, IFNULL((SELECT SUM(valor) FROM pagamentos_contas WHERE conta_id = c.id), 0) AS soma"
                   " FROM contas_pagar c"):
            if c["soma"] != c["valor_pago"]:
                problemas.append(f"Conta a pagar {c['id']}: valor pago não bate com os pagamentos")
            if c["status"] == "PAGA" and c["valor_pago"] != c["valor"]:
                problemas.append(f"Conta a pagar {c['id']}: marcada como paga sem quitação")
        for compra in q("SELECT c.*, IFNULL((SELECT SUM(total) FROM compra_itens WHERE compra_id = c.id), 0) AS itens,"
                        " IFNULL((SELECT SUM(valor) FROM contas_pagar WHERE compra_id = c.id), 0) AS contas"
                        " FROM compras c"):
            if compra["itens"] != compra["total"] or compra["contas"] != compra["total"]:
                problemas.append(f"Compra {compra['id']}: itens/contas a pagar não fecham com o total")
        for s in q("SELECT * FROM caixa_sessoes WHERE status = 'FECHADO'"):
            if s["valor_esperado"] != self._saldo_dinheiro(s):
                problemas.append(f"Caixa {s['id']}: valor esperado no fechamento não confere com os movimentos")
        for s in q("SELECT * FROM caixa_sessoes"):
            if self._saldo_dinheiro(s) < 0:
                problemas.append(f"Caixa {s['id']}: saldo em dinheiro negativo")
        for r in q("SELECT r.id, r.valor, r.conta_id, IFNULL((SELECT SUM(valor) FROM caixa_movimentos"
                   " WHERE referencia = 'conta_receber:' || r.conta_id), 0) AS caixa,"
                   " (SELECT SUM(valor) FROM recebimentos WHERE conta_id = r.conta_id) AS total FROM recebimentos r"):
            if r["caixa"] != r["total"]:
                problemas.append(f"Recebimento da conta {r['conta_id']}: valor não entrou corretamente no caixa")
        return problemas
