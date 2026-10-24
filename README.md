# Sistema para Loja de Material de Construção

Sistema completo de vendas, estoque, caixa e financeiro para loja de material de construção.
Roda no navegador, guarda tudo num arquivo local (`loja.db`) e **não precisa instalar nada além do Python 3.9+**.

## Como usar

1. Instale o [Python](https://www.python.org/downloads/) (no Windows, marque "Add Python to PATH").
2. Inicie o sistema:
   - **Windows:** dê dois cliques em `iniciar.bat`
   - **Linux/Mac:** `./iniciar.sh` (ou `python3 -m loja`)
3. Abra **http://localhost:8080** no navegador.

Opções:

```
python -m loja --porta 8080 --banco loja.db     # arquivo do banco e porta
python -m loja --host 0.0.0.0                   # libera acesso de outros computadores da rede (ex.: 2º caixa)
```

O nome que aparece no topo e nos comprovantes é definido pela variável de ambiente `LOJA_NOME`
(ex.: `set LOJA_NOME=Casa do Construtor` no Windows antes de iniciar).

**Primeiro dia:** abra o caixa (menu *Caixa*), cadastre fornecedores, produtos e clientes, e comece a vender em *Vender*.

### Interface

- Visual moderno, com **tema claro e escuro** (botão da lua/sol no topo; a escolha fica lembrada).
- Funciona também em **tablet e celular** (o menu vira um botão ☰).
- **Atalhos de teclado** para o balcão:

| Tecla | O que faz |
|---|---|
| **F2** | Nova venda / ir para a busca de produto |
| **F3** | Receber de cliente |
| **F4** | Finalizar a venda |
| **F6** | Escolher o cliente na venda |
| **F8** | Ir para o desconto |
| **Enter** | Na busca de produto: adiciona (aceita leitor de código de barras) |
| **↑ ↓** | Navegar nas sugestões de busca |
| **Esc** | Fechar janela |

## Funções

| Área | O que faz |
|---|---|
| **PDV (vender)** | Busca por código, código de barras ou nome; quantidade fracionada (2,5 m³ de areia, 12,5 m de fio); desconto em R$ ou %; pagamento em dinheiro (com troco), PIX, débito, crédito, crediário, ou várias formas juntas; comprovante para imprimir |
| **Orçamentos** | Salva orçamento com validade, imprime, e depois transforma em venda mantendo o preço combinado (mesmo que o preço do produto mude). Não mexe no estoque até virar venda |
| **Vendas** | Histórico por período, reimpressão, cancelamento (devolve estoque e estorna o caixa) e **devolução parcial** de itens |
| **Produtos** | Código, código de barras, categoria, unidade (UN, SC, M, M², M³, KG, L, milheiro, barra, rolo, lata...), custo, preço, margem, estoque mínimo, localização no depósito |
| **Estoque** | Entrada de mercadoria (soma estoque e recalcula **custo médio**), inventário (ajuste pela contagem), registro de perdas/quebras, histórico de toda movimentação, alerta de estoque baixo |
| **Receber de cliente** | Dá baixa na conta do crediário: mostra as compras em aberto com os produtos e as parcelas; você marca **tudo, só algumas compras ou só uma parcela**, digita **quanto o cliente está pagando** (tudo, metade, só o vencido ou qualquer valor) e o sistema mostra antes de confirmar como a conta vai ficar. Calcula o troco, imprime comprovante com o saldo que ficou devendo e permite **estornar** um pagamento lançado errado |
| **Clientes** | Cadastro com CPF/CNPJ validado e limite de crediário. **Histórico de cada cliente** no período que você escolher (ou desde a primeira compra): total comprado, lucro, quanto pagou no crediário, quanto deve, o que compra por categoria, compras mês a mês, produtos que mais compra e a lista de compras com os itens |
| **Contas a receber** | Todas as parcelas do crediário, filtro de vencidas e botão "Receber" que já abre a baixa com aquela parcela marcada |
| **Contas a pagar** | Geradas automaticamente pelas compras (parceladas) ou lançadas à mão (aluguel, energia...); pagamento parcial; pagamento com dinheiro do caixa |
| **Caixa** | Abertura com fundo de troco, sangria, suprimento, totais por forma de pagamento e fechamento com conferência (mostra sobra ou falta) |
| **Painel** | Vendas e lucro do dia, dinheiro no caixa, gráfico das vendas dos últimos 14 dias, clientes com conta vencida, estoque baixo e contas a pagar da semana |
| **Relatórios** | Período livre ou atalhos (este mês, 3, 6 ou 12 meses, este ano, tudo), em quatro abas: **Resumo** (faturamento bruto/líquido, descontos, devoluções, custo, lucro bruto, ticket médio, formas de pagamento, mais vendidos, valor do estoque), **Mês a mês** (gráfico e tabela com vendas, líquido, lucro e margem de cada mês), **Por categoria** (quanto vendeu de elétrica, hidráulica, cimento... com lucro e margem; clique para ver os produtos) e **Por cliente** (ranking de quem mais comprou, com acesso ao histórico de cada um) |
| **Segurança dos dados** | Botão "Conferir consistência" (confere estoque × movimentações, vendas × pagamentos × parcelas × caixa) e botão de backup |

### Regras que o sistema garante

- Não vende mais do que tem em estoque (nem com dois caixas vendendo o último item ao mesmo tempo).
- Produto vendido por unidade/saco/caixa não aceita quantidade quebrada.
- Toda operação é "tudo ou nada": se qualquer parte de uma venda falhar, nada é gravado (nem estoque, nem caixa, nem parcelas).
- Dinheiro é calculado em centavos inteiros: nada de diferença de R$ 0,01 por arredondamento. As parcelas e o desconto
  rateado entre os itens sempre somam exatamente o total.
- Crediário só para cliente cadastrado, dentro do limite e **sem parcelas em atraso**.
- Na devolução, o valor primeiro abate o que o cliente ainda deve daquela venda; só o que sobrar é reembolsado.
- Não deixa receber mais do que o cliente deve nas parcelas escolhidas, nem tirar do caixa mais dinheiro do que tem nele.
- Pagamento parcial abate primeiro a parcela que vence antes. No dinheiro, só o valor da conta entra no caixa (o troco não).
- Todos os relatórios contam as vendas pela data da venda, já descontando devoluções e sem as canceladas; a soma
  dos meses, a soma das categorias e a soma dos clientes sempre dão exatamente o total do período.
- O estorno de um pagamento devolve a dívida ao cliente e tira o valor do caixa; não é permitido se a compra teve devolução depois.
- Venda e recebimento exigem caixa aberto.
- O banco de dados também recusa estoque negativo, pagamento acima do devido etc., mesmo que alguém mexa por fora.

## Backup

Todos os dados ficam no arquivo `loja.db`. Use o botão *Relatórios → Fazer backup agora* (salva em `backups/`)
e copie essa pasta para um pen drive ou nuvem regularmente.

## Testes

```
python -m unittest discover -s tests -t . -v
```

São 134 testes automáticos (com centenas de casos dentro deles), incluindo:

- **Valores:** conversão de "1.234,56", arredondamento, rateio de centavos, validação de CPF/CNPJ.
- **Estoque:** baixa na venda, bloqueio de estoque insuficiente, desfazer tudo se um item falhar, custo médio, inventário, perdas.
- **Vendas:** troco, pagamento misto, descontos, crediário, limite de crédito, cliente em atraso, cancelamento, devoluções parciais.
- **Financeiro:** pagamento parcial e total de parcelas, contas a pagar, abertura/sangria/fechamento de caixa.
- **Baixa na conta do cliente:** quitar tudo, só uma compra, só parte de uma compra, metade do valor, troco, valores
  inválidos, parcela de outro cliente, caixa fechado, estorno, e atualização automática de bancos de versões anteriores.
- **Relatórios por período:** vendas em vários meses (com mês vazio, desconto, devolução, cancelamento, venda sem
  cliente e produto sem categoria) conferidas mês a mês, por categoria, por cliente e no histórico de cada cliente.
- **Simulação:** 9.000 operações aleatórias (vendas, erros propositais, cancelamentos, devoluções, recebimentos,
  baixas escolhendo parcelas, estornos, compras,
  inventários, sangrias, vários dias) comparando o sistema, depois de cada operação, com um controle paralelo
  calculado de forma independente: estoque de cada produto, dinheiro na gaveta e dívida de cada cliente. No final,
  os relatórios mês a mês, por categoria e por cliente precisam somar exatamente o total.
- **API:** o servidor web de verdade, incluindo 40 vendas simultâneas disputando 5 unidades.
- **Interface:** abre o sistema num navegador real e faz o dia de trabalho completo clicando nas telas: vendas,
  crediário, baixa parcial com troco, quitação, estorno, devolução, orçamento, entrada de mercadoria, fechamento de
  caixa, relatórios por mês/categoria/cliente, histórico do cliente, atalhos de teclado, tema escuro e todas as
  telas na largura de um celular
  (precisa de Node.js com Playwright; se não houver, esse teste é pulado).

## Estrutura

```
loja/
  valores.py     dinheiro, quantidades, CPF/CNPJ, datas
  banco.py       tabelas do banco (SQLite) com travas de segurança
  sistema.py     todas as regras de negócio
  servidor.py    servidor web (API JSON + interface)
  static/        telas (HTML, CSS, JavaScript)
tests/           testes automáticos
```
