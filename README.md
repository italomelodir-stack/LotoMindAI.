# Sistema para Loja de Material de Construção

Sistema completo de vendas, estoque, caixa e financeiro para loja de material de construção.
Funciona num computador com Windows 10 ou 11, abre no navegador e não depende de internet no dia a dia.

## Instalar no Windows

Use o instalador **[`Instalar-Sistema-da-Loja-1.0.0.exe`](baixar/Instalar-Sistema-da-Loja-1.0.0.exe)** (um arquivo
só, cerca de 8 MB, na pasta `baixar/`):

1. No computador da loja, abra o link acima e clique no botão de baixar (**Download raw file**, ícone de seta para
   baixo). Depois dê dois cliques no arquivo baixado (fica na pasta *Downloads*).
2. Se aparecer "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo**.
   (O aviso aparece porque o instalador não tem assinatura digital paga; é comum em programas de pequenas empresas.)
3. Clique em **Instalar** e depois em **Concluir**. O sistema abre no navegador.

Não precisa de internet nem de senha de administrador: o Python que o sistema usa já vai dentro do instalador.
Ficam o atalho **Sistema da Loja** na área de trabalho e no menu Iniciar, e o item *Sistema da Loja* em
*Configurações do Windows → Aplicativos* (por onde também se desinstala). Funciona no Windows 10 e 11 (64 bits).

<details>
<summary>Gerar o instalador ou instalar sem ele</summary>

- **Gerar o `.exe`** (para quem mexe no programa; depois copie para `baixar/` ao lançar uma versão): com o NSIS 3 instalado (Windows: nsis.sourceforge.io;
  Linux: `apt install nsis`), rode `python instalador/construir_instalador.py`. O instalador sai em
  `dist/Instalar-Sistema-da-Loja-<versão>.exe`. O Python oficial de Windows é baixado do NuGet e conferido pelo SHA-256.
- **Sem o `.exe`, pelo ZIP do GitHub:** *Code → Download ZIP*, extraia (botão direito → *Extrair tudo*) e dê dois
  cliques em `INSTALAR.bat`. Na primeira vez precisa de internet para baixar o Python (cerca de 15 MB). Instala no
  mesmo lugar e do mesmo jeito que o `.exe`. Para remover: `DESINSTALAR.bat`.

</details>

**Primeiro dia:** vá em *Configurações* e preencha os dados da loja (nome, CNPJ, telefone, endereço — saem no topo
dos comprovantes). Depois abra o caixa (menu *Caixa*), cadastre fornecedores, produtos e clientes, e comece a vender
em *Vender*.

### Usando no dia a dia

- **Abrir:** dois cliques no atalho *Sistema da Loja*. Se já estiver aberto, ele só traz a tela de volta.
- **Fechar:** *Configurações → Fechar o sistema* (faz um backup e fecha). Desligar o computador direto também não
  perde dados.
- **Imprimir:** comprovante de venda, orçamento e recibo de pagamento saem em folha **A4**, com os dados da loja.
  Os relatórios e o histórico do cliente também têm botão *Imprimir*. Os documentos dizem "sem valor fiscal":
  o sistema **não emite nota fiscal** (NFC-e/NF-e).

### Onde ficam os dados e os backups

| O quê | Onde |
|---|---|
| Dados do sistema | `C:\Users\(seu usuário)\AppData\Local\LojaMaterialConstrucao\loja.db` |
| Backups | `Documentos\Backup da Loja` |
| Programa | `C:\Users\(seu usuário)\AppData\Local\Programs\LojaMaterialConstrucao` |

- O backup é **automático**: todo dia, ao fechar o caixa e ao fechar o sistema. Cada cópia é conferida antes de ser
  guardada. Ficam todos os dos últimos 7 dias e um por dia até 90 dias.
- Em *Configurações* dá para escolher uma **cópia extra** (pen drive, HD externo ou pasta do OneDrive/Google Drive),
  fazer backup na hora e **restaurar** um backup (antes de restaurar, o sistema guarda o estado atual).
- O painel avisa se o backup estiver atrasado ou se a cópia extra falhar (por exemplo, pen drive desconectado).

### Atualizar e desinstalar

- **Atualizar:** rode o instalador da versão nova por cima. Se o sistema estiver aberto, ele é fechado (com backup)
  antes de trocar o programa; **os dados não são tocados**.
- **Desinstalar:** *Configurações do Windows → Aplicativos → Sistema da Loja → Desinstalar*. Remove o programa e os
  atalhos; os dados e os backups continuam guardados — se instalar de novo, tudo volta como estava.
- Quem usava a primeira versão (aberta pelo `iniciar.bat`, com o `loja.db` dentro da pasta do programa): rode o
  `INSTALAR.bat` naquela mesma pasta, que os dados são trazidos automaticamente.

### Outros sistemas (Linux/Mac) e opções avançadas

Com Python 3.9 ou mais novo: `python3 -m loja` (os dados ficam em `~/.local/share/LojaMaterialConstrucao`).

```
python -m loja --porta 8080                 # porta (se estiver ocupada, usa a próxima livre)
python -m loja --dados PASTA --backups PASTA  # outras pastas para dados e backups
python -m loja --sem-navegador              # não abre o navegador
python -m loja --fechar                     # fecha o sistema aberto (com backup) e espera ele terminar
python -m loja --host 0.0.0.0               # libera o acesso de outros computadores da rede (sem senha!)
```

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
| **Configurações** | Dados da loja para os documentos impressos, backup automático com cópia extra e restauração, conferência de consistência (estoque × movimentações, vendas × pagamentos × parcelas × caixa) e botão para fechar o sistema |

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
- Só a própria tela do sistema consegue mandar comandos para ele: um site aberto no mesmo navegador não consegue
  (proteção contra CSRF e DNS rebinding). Por padrão o sistema só aceita conexões do próprio computador.

## Testes

```
python -m unittest discover -s tests -t . -v
```

São 160 testes automáticos (com centenas de casos dentro deles), incluindo:

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
- **API:** o servidor web de verdade, incluindo 40 vendas simultâneas disputando 5 unidades e a recusa de comandos
  vindos de outros sites.
- **Backup e inicialização:** backup conferido e em arquivo único, cópia extra com pen drive desconectado, limpeza
  dos antigos (150 dias simulados), restauração (inclusive de backup de versão antiga e recusa de arquivo danificado),
  dados da loja, e o programa aberto de verdade num processo separado: segundo clique no atalho, porta ocupada por
  outro programa, dados da versão anterior, funcionamento sem janela e mensagem de erro.
- **Instalador `.exe`:** gera o instalador e, num Windows simulado (wine) sem nada instalado, instala, confere os
  atalhos e o item em *Aplicativos*, abre o sistema pelo atalho da área de trabalho e vende; atualiza com o sistema
  aberto (ele fecha com backup e os dados continuam), desinstala com o sistema aberto (programa, atalhos e registro
  saem; dados e backups ficam) e instala de novo (precisa de `makensis` e `wine`; sem eles, é pulado).
- **Instalador pelo ZIP:** roda o `instalar.ps1` no PowerShell, abre o programa instalado com o Python de Windows
  (no wine), faz uma venda, fecha pela tela, reinstala e desinstala; recusa pacote do Python adulterado
  (precisa de `pwsh` e `wine`; sem eles, é pulado).
- **Valor por extenso** dos recibos (30 valores, de centavos a milhões).
- **Interface:** abre o sistema num navegador real e faz o dia de trabalho completo clicando nas telas: vendas,
  crediário, baixa parcial com troco, quitação, estorno, devolução, orçamento, entrada de mercadoria, fechamento de
  caixa, relatórios por mês/categoria/cliente, histórico do cliente, impressão em A4 com os dados da loja, backup e
  restauração pela tela, fechar o sistema, atalhos de teclado, tema escuro e todas as telas na largura de um celular
  (precisa de Node.js com Playwright; se não houver, esse teste é pulado).

Toda a bateria também foi rodada com o **mesmo Python de Windows que vai dentro do instalador** (3.13, no wine):
153 testes aprovados; os outros 7 usam ferramentas que só existem no computador de testes (wine, PowerShell,
navegador automático) e são pulados lá.

## Estrutura

```
instalador/
  loja.nsi                  instalador .exe (NSIS): telas, atalhos, desinstalador
  construir_instalador.py   gera o .exe com o Python oficial de Windows dentro
  instalar.ps1 ...          instalação pelo ZIP (INSTALAR.bat / DESINSTALAR.bat)
loja/
  aplicativo.py  inicialização (pastas de dados, instância única, backup automático)
  backup.py      backups conferidos, limpeza e restauração
  valores.py     dinheiro, quantidades, CPF/CNPJ, datas
  banco.py       tabelas do banco (SQLite) com travas de segurança
  sistema.py     todas as regras de negócio
  servidor.py    servidor web (API JSON + interface)
  static/        telas (HTML, CSS, JavaScript)
tests/           testes automáticos
```
