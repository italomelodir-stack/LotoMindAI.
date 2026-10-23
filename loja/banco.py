"""Estrutura do banco de dados (SQLite).

As restrições CHECK são uma segunda linha de defesa: mesmo que alguma regra
falhe no código, o banco recusa estoque negativo, pagamentos acima do devido etc.
"""

ESQUEMA = """
CREATE TABLE IF NOT EXISTS fornecedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    documento TEXT UNIQUE,
    telefone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    endereco TEXT NOT NULL DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    codigo_barras TEXT UNIQUE,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT '',
    unidade TEXT NOT NULL,
    preco_custo INTEGER NOT NULL DEFAULT 0 CHECK (preco_custo >= 0),
    preco_venda INTEGER NOT NULL CHECK (preco_venda > 0),
    estoque INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
    estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    localizacao TEXT NOT NULL DEFAULT '',
    fornecedor_id INTEGER REFERENCES fornecedores(id),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movimentos_estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    data TEXT NOT NULL,
    tipo TEXT NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade <> 0),
    saldo_apos INTEGER NOT NULL CHECK (saldo_apos >= 0),
    custo_unitario INTEGER,
    referencia TEXT NOT NULL DEFAULT '',
    observacao TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_mov_produto ON movimentos_estoque(produto_id);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    documento TEXT UNIQUE,
    telefone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    endereco TEXT NOT NULL DEFAULT '',
    limite_credito INTEGER NOT NULL DEFAULT 0 CHECK (limite_credito >= 0),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS caixa_sessoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abertura TEXT NOT NULL,
    fechamento TEXT,
    operador TEXT NOT NULL DEFAULT '',
    valor_inicial INTEGER NOT NULL CHECK (valor_inicial >= 0),
    valor_esperado INTEGER,
    valor_contado INTEGER,
    diferenca INTEGER,
    status TEXT NOT NULL CHECK (status IN ('ABERTO', 'FECHADO')),
    observacao TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_um_caixa_aberto ON caixa_sessoes(status) WHERE status = 'ABERTO';

CREATE TABLE IF NOT EXISTS caixa_movimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id INTEGER NOT NULL REFERENCES caixa_sessoes(id),
    data TEXT NOT NULL,
    tipo TEXT NOT NULL,
    forma TEXT NOT NULL,
    valor INTEGER NOT NULL CHECK (valor <> 0),
    descricao TEXT NOT NULL DEFAULT '',
    referencia TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_caixa_mov_sessao ON caixa_movimentos(sessao_id);

CREATE TABLE IF NOT EXISTS orcamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    validade TEXT NOT NULL,
    cliente_id INTEGER REFERENCES clientes(id),
    nome_cliente TEXT NOT NULL DEFAULT '',
    subtotal INTEGER NOT NULL CHECK (subtotal > 0),
    desconto INTEGER NOT NULL DEFAULT 0 CHECK (desconto >= 0),
    total INTEGER NOT NULL CHECK (total > 0),
    status TEXT NOT NULL CHECK (status IN ('ABERTO', 'CONVERTIDO', 'CANCELADO')),
    venda_id INTEGER,
    observacao TEXT NOT NULL DEFAULT '',
    CHECK (total = subtotal - desconto)
);

CREATE TABLE IF NOT EXISTS orcamento_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcamento_id INTEGER NOT NULL REFERENCES orcamentos(id),
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    descricao TEXT NOT NULL,
    unidade TEXT NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario INTEGER NOT NULL CHECK (preco_unitario > 0),
    total INTEGER NOT NULL CHECK (total > 0)
);

CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    cliente_id INTEGER REFERENCES clientes(id),
    caixa_sessao_id INTEGER REFERENCES caixa_sessoes(id),
    orcamento_id INTEGER REFERENCES orcamentos(id),
    subtotal INTEGER NOT NULL CHECK (subtotal > 0),
    desconto INTEGER NOT NULL DEFAULT 0 CHECK (desconto >= 0),
    total INTEGER NOT NULL CHECK (total > 0),
    status TEXT NOT NULL CHECK (status IN ('CONCLUIDA', 'CANCELADA')),
    observacao TEXT NOT NULL DEFAULT '',
    cancelada_em TEXT,
    motivo_cancelamento TEXT NOT NULL DEFAULT '',
    CHECK (total = subtotal - desconto)
);
CREATE INDEX IF NOT EXISTS ix_vendas_data ON vendas(data);

CREATE TABLE IF NOT EXISTS venda_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER NOT NULL REFERENCES vendas(id),
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    descricao TEXT NOT NULL,
    unidade TEXT NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario INTEGER NOT NULL CHECK (preco_unitario > 0),
    custo_unitario INTEGER NOT NULL CHECK (custo_unitario >= 0),
    total INTEGER NOT NULL CHECK (total > 0),
    total_liquido INTEGER NOT NULL CHECK (total_liquido >= 0),
    quantidade_devolvida INTEGER NOT NULL DEFAULT 0,
    valor_devolvido INTEGER NOT NULL DEFAULT 0,
    CHECK (quantidade_devolvida BETWEEN 0 AND quantidade),
    CHECK (valor_devolvido BETWEEN 0 AND total_liquido)
);

CREATE TABLE IF NOT EXISTS venda_pagamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER NOT NULL REFERENCES vendas(id),
    forma TEXT NOT NULL CHECK (forma IN ('DINHEIRO', 'PIX', 'DEBITO', 'CREDITO', 'CREDIARIO')),
    valor INTEGER NOT NULL CHECK (valor > 0),
    troco INTEGER NOT NULL DEFAULT 0 CHECK (troco >= 0 AND troco < valor)
);

CREATE TABLE IF NOT EXISTS contas_receber (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER REFERENCES vendas(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    parcela INTEGER NOT NULL,
    total_parcelas INTEGER NOT NULL,
    emissao TEXT NOT NULL,
    vencimento TEXT NOT NULL,
    valor_original INTEGER NOT NULL CHECK (valor_original > 0),
    valor INTEGER NOT NULL CHECK (valor >= 0 AND valor <= valor_original),
    valor_pago INTEGER NOT NULL DEFAULT 0 CHECK (valor_pago >= 0 AND valor_pago <= valor),
    status TEXT NOT NULL CHECK (status IN ('ABERTA', 'PAGA', 'CANCELADA'))
);
CREATE INDEX IF NOT EXISTS ix_receber_cliente ON contas_receber(cliente_id);

CREATE TABLE IF NOT EXISTS recebimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id INTEGER NOT NULL REFERENCES contas_receber(id),
    data TEXT NOT NULL,
    valor INTEGER NOT NULL CHECK (valor > 0),
    forma TEXT NOT NULL,
    caixa_sessao_id INTEGER REFERENCES caixa_sessoes(id)
);

CREATE TABLE IF NOT EXISTS devolucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER NOT NULL REFERENCES vendas(id),
    data TEXT NOT NULL,
    valor INTEGER NOT NULL CHECK (valor >= 0),
    valor_abatido INTEGER NOT NULL CHECK (valor_abatido >= 0),
    valor_reembolsado INTEGER NOT NULL CHECK (valor_reembolsado >= 0),
    forma_reembolso TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    CHECK (valor = valor_abatido + valor_reembolsado)
);

CREATE TABLE IF NOT EXISTS devolucao_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    devolucao_id INTEGER NOT NULL REFERENCES devolucoes(id),
    venda_item_id INTEGER NOT NULL REFERENCES venda_itens(id),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    valor INTEGER NOT NULL CHECK (valor >= 0)
);

CREATE TABLE IF NOT EXISTS compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    fornecedor_id INTEGER NOT NULL REFERENCES fornecedores(id),
    nota_fiscal TEXT NOT NULL DEFAULT '',
    total INTEGER NOT NULL CHECK (total >= 0),
    observacao TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS compra_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id INTEGER NOT NULL REFERENCES compras(id),
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    custo_unitario INTEGER NOT NULL CHECK (custo_unitario >= 0),
    total INTEGER NOT NULL CHECK (total >= 0)
);

CREATE TABLE IF NOT EXISTS contas_pagar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id INTEGER REFERENCES compras(id),
    fornecedor_id INTEGER REFERENCES fornecedores(id),
    descricao TEXT NOT NULL,
    parcela INTEGER NOT NULL DEFAULT 1,
    total_parcelas INTEGER NOT NULL DEFAULT 1,
    emissao TEXT NOT NULL,
    vencimento TEXT NOT NULL,
    valor INTEGER NOT NULL CHECK (valor > 0),
    valor_pago INTEGER NOT NULL DEFAULT 0 CHECK (valor_pago >= 0 AND valor_pago <= valor),
    status TEXT NOT NULL CHECK (status IN ('ABERTA', 'PAGA', 'CANCELADA'))
);

CREATE TABLE IF NOT EXISTS pagamentos_contas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id INTEGER NOT NULL REFERENCES contas_pagar(id),
    data TEXT NOT NULL,
    valor INTEGER NOT NULL CHECK (valor > 0),
    forma TEXT NOT NULL
);
"""


def criar_esquema(conn):
    conn.executescript(ESQUEMA)
