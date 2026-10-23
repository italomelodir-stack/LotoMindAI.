// Teste da interface em navegador real (Chromium + Playwright): um dia de trabalho completo, clicando nas telas.
// Uso: node tests/interface.e2e.js http://127.0.0.1:PORTA
const { chromium } = require("playwright");
const assert = require("assert");

const URL_BASE = process.argv[2];
const errosJs = [];
const PAGINAS = ["painel", "pdv", "receber-cliente", "orcamentos", "vendas", "caixa", "produtos", "compras", "movimentos",
  "clientes", "fornecedores", "receber", "pagar", "relatorios"];

async function principal() {
  const navegador = await chromium.launch();
  const contexto = await navegador.newContext({ viewport: { width: 1366, height: 900 }, colorScheme: "light" });
  const pagina = await contexto.newPage();
  await pagina.addInitScript(() => { window.print = () => { window.__impresso = (window.__impresso || 0) + 1; }; });
  pagina.on("pageerror", (e) => errosJs.push("pageerror: " + e.message));
  // respostas 400/404 são recusas de regra de negócio provocadas de propósito pelo teste (viram aviso na tela)
  pagina.on("console", (m) => { if (m.type() === "error" && !/status of 40[04]/.test(m.text())) errosJs.push("console: " + m.text()); });
  pagina.on("response", (r) => { if (r.status() >= 500) errosJs.push(`HTTP ${r.status()} em ${r.url()}`); });

  const api = async (caminho) => (await pagina.request.get(URL_BASE + caminho)).json();
  const ir = async (hash) => {
    await pagina.goto(`${URL_BASE}/#${hash}`);
    await pagina.waitForFunction((h) => document.querySelector("#titulo-pagina")?.textContent && !document.querySelector("#conteudo").textContent.includes("Erro ao carregar")
      && document.querySelector("#conteudo").children.length > 0, hash);
    await pagina.waitForTimeout(150);
  };
  const modal = () => pagina.locator("#modal-corpo");
  const enviarModal = async () => { await modal().locator("button[type=submit]").click(); await pagina.waitForSelector("#modal.oculto", { state: "attached" }); };
  const texto = async (sel) => (await pagina.locator(sel).first().innerText()).replace(/\s+/g, " ").trim();
  const passo = (t) => console.log("  ✓ " + t);

  // 1. todas as telas abrem sem erro, mesmo com o banco vazio
  for (const p of PAGINAS) {
    await ir(p);
    assert.strictEqual(await pagina.locator("text=Erro ao carregar").count(), 0, `página ${p} com erro`);
  }
  passo(`todas as ${PAGINAS.length} telas abrem com o banco vazio`);

  // 2. abrir caixa
  await ir("caixa");
  await pagina.fill("#abrir [name=valor_inicial]", "100,00");
  await pagina.fill("#abrir [name=operador]", "Ana");
  await pagina.click("#abrir button[type=submit]");
  await pagina.waitForSelector("h2:has-text('Caixa aberto')");
  await pagina.waitForSelector("#side-caixa:has-text('Caixa aberto')");
  passo("caixa aberto com fundo de troco R$ 100,00");

  // 3. fornecedor
  await ir("fornecedores");
  await pagina.click("#novo");
  await modal().locator("[name=nome]").fill("Distribuidora Central");
  await modal().locator("[name=documento]").fill("11.222.333/0001-81");
  await enviarModal();
  await pagina.waitForSelector("text=11.222.333/0001-81");
  passo("fornecedor cadastrado (CNPJ formatado na lista)");

  // 4. produtos
  async function novoProduto(campos) {
    await ir("produtos");
    await pagina.click("#novo");
    for (const [k, v] of Object.entries(campos)) {
      const el = modal().locator(`[name=${k}]`);
      if ((await el.evaluate((e) => e.tagName)) === "SELECT") await el.selectOption(v);
      else await el.fill(v);
    }
    await enviarModal();
    await pagina.waitForSelector(`td:has-text('${campos.nome}')`);
  }
  await novoProduto({ codigo: "CIM", nome: "Cimento CP-II 50kg", categoria: "Cimento", unidade: "SC", preco_custo: "29,50", preco_venda: "38,90", estoque_minimo: "10", estoque_inicial: "50" });
  await novoProduto({ codigo: "ARE", nome: "Areia média", categoria: "Agregados", unidade: "M3", preco_custo: "90", preco_venda: "145", estoque_inicial: "10" });
  await pagina.click("#novo");
  await modal().locator("[name=preco_custo]").fill("10");
  await modal().locator("#margem").fill("50");
  assert.strictEqual(await modal().locator("[name=preco_venda]").inputValue(), "15,00");
  await modal().locator("[name=nome]").fill("Produto ruim");
  await modal().locator("[name=preco_venda]").fill("abc");
  await modal().locator("button[type=submit]").click();
  await pagina.waitForSelector(".toast.erro");
  assert.ok(await pagina.isVisible("#modal-corpo form"), "formulário deveria continuar aberto após erro");
  await pagina.keyboard.press("Escape");
  const prods = await api("/api/produtos");
  assert.strictEqual(prods.length, 2);
  const cim = prods.find((p) => p.codigo === "CIM");
  const are = prods.find((p) => p.codigo === "ARE");
  assert.strictEqual(cim.estoque, 50000);
  passo("produtos cadastrados; margem calcula o preço; valor inválido mostra erro e não grava");

  // 5. cliente
  await ir("clientes");
  await pagina.click("#novo");
  await modal().locator("[name=nome]").fill("Construtora Boa Obra");
  await modal().locator("[name=documento]").fill("52998224725");
  await modal().locator("[name=limite_credito]").fill("1.000,00");
  await enviarModal();
  await pagina.waitForSelector("text=529.982.247-25");
  const cliente = (await api("/api/clientes"))[0];
  passo("cliente cadastrado com limite de R$ 1.000,00");

  // 6. venda em dinheiro com troco (produto pelo código + Enter)
  await ir("pdv");
  await pagina.fill("#qtd", "3");
  await pagina.fill("#busca", "CIM");
  await pagina.press("#busca", "Enter");
  await pagina.waitForSelector("#itens td:has-text('Cimento')");
  assert.strictEqual(await texto("#total"), "R$ 116,70");
  await pagina.fill(".pg-recebido", "150");
  assert.match(await texto(".pg-resumo"), /Troco R\$ 33,30/);
  await pagina.click("#finalizar");
  await pagina.waitForSelector("#modal-titulo:has-text('Venda concluída')");
  assert.match(await texto("#modal-corpo"), /Troco R\$ 33,30/);
  await modal().locator("#imp").click();
  assert.strictEqual(await pagina.evaluate(() => window.__impresso), 1);
  assert.match(await texto("#impressao"), /TOTAL\s*R\$ 116,70/);
  await modal().locator("#ok").click();
  await pagina.waitForSelector("#cart-vazio .cart-vazio");
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 47000);
  passo("venda de 3 sacos: R$ 116,70, troco R$ 33,30, estoque 50 → 47, comprovante impresso");

  // 7. busca por nome, botões +/−, desconto em %, e pagamento faltando
  await pagina.fill("#qtd", "2,5");
  await pagina.fill("#busca", "areia");
  await pagina.waitForSelector(".ac-item");
  await pagina.click(".ac-item");
  await pagina.waitForSelector("#itens td:has-text('Areia')");
  assert.strictEqual(await texto("#total"), "R$ 362,50");
  await pagina.click("#itens .mais");
  assert.strictEqual(await texto("#total"), "R$ 507,50");
  await pagina.click("#itens .menos");
  assert.strictEqual(await texto("#total"), "R$ 362,50");
  await pagina.fill("#itens .q", "11");
  await pagina.waitForSelector("#itens tr.alerta:has-text('Só 10 M3 em estoque')");
  await pagina.fill("#itens .q", "2,5");
  await pagina.click("#desc-modo button[data-v='%']");
  await pagina.fill("#desconto", "10");
  assert.strictEqual(await texto("#total"), "R$ 326,25");
  await pagina.fill("#desconto", "");
  await pagina.click("#desc-modo button[data-v='R$']");
  await pagina.fill(".pg-recebido", "100");
  assert.match(await texto(".pg-resumo"), /Falta R\$ 262,50/);
  await pagina.click("#finalizar");
  await pagina.waitForSelector(".toast.erro:has-text('Pagamento insuficiente')");
  assert.strictEqual((await api(`/api/produtos/${are.id}`)).estoque, 10000);
  passo("busca por nome, +/− e aviso de estoque; desconto 10%; pagamento faltando é recusado sem mexer no estoque");

  // 8. a mesma venda no crediário em 2x, escolhendo o cliente pela busca (atalho F6)
  await pagina.keyboard.press("F6");
  await pagina.keyboard.type("Constru");
  await pagina.waitForSelector("#sel-cliente .ac-item");
  await pagina.keyboard.press("Enter");
  await pagina.waitForSelector("#sel-cliente .cliente-sel:has-text('Construtora Boa Obra')");
  await pagina.click(".chip[data-f=CREDIARIO]");
  await pagina.selectOption(".cred-parc", "2");
  assert.match(await pagina.locator(".cred-parc option:checked").textContent(), /2x de R\$ 181,25/);
  await pagina.keyboard.press("F4");
  await pagina.waitForSelector("#modal-titulo:has-text('Venda concluída')");
  await pagina.keyboard.press("Escape");
  let cli = await api(`/api/clientes/${cliente.id}`);
  assert.strictEqual(cli.saldo_devedor, 36250);
  assert.deepStrictEqual(cli.parcelas.map((p) => p.valor), [18125, 18125]);
  assert.strictEqual((await api(`/api/produtos/${are.id}`)).estoque, 7500);
  passo("venda de 2,5 m³ no crediário (F6 cliente, F4 finalizar) em 2x de R$ 181,25");

  // 9. RECEBER DE CLIENTE: escolher só uma parcela e pagar parte dela, com troco
  await pagina.keyboard.press("F3");
  await pagina.waitForSelector("text=Clientes com conta em aberto");
  await pagina.click(`a[href='#receber-cliente/${cliente.id}']`);
  await pagina.waitForSelector("#confirmar-rc");
  assert.strictEqual(await texto("#tot-sel"), "R$ 362,50");
  await pagina.locator(".sel-parc").nth(1).uncheck();
  assert.strictEqual(await texto("#tot-sel"), "R$ 181,25");
  assert.ok(await pagina.locator(".sel-compra").evaluate((e) => e.indeterminate), "compra deveria ficar parcialmente marcada");
  await pagina.fill("#valor-pagar", "100");
  assert.match(await texto("#previa"), /abate R\$ 100,00 \(fica R\$ 81,25\)/);
  assert.match(await texto("#previa"), /Cliente vai dever R\$ 262,50/);
  await pagina.fill("#valor-entregue", "150");
  assert.match(await texto("#troco-rc"), /Troco R\$ 50,00/);
  await pagina.fill("#obs-rc", "pagou no balcão");
  assert.match(await texto("#confirmar-rc"), /Confirmar pagamento de R\$ 100,00/);
  await pagina.click("#confirmar-rc");
  await pagina.waitForSelector("#modal-titulo:has-text('Pagamento registrado')");
  assert.match(await texto("#modal-corpo"), /Troco R\$ 50,00/);
  assert.match(await texto("#modal-corpo"), /Ainda deve R\$ 262,50/);
  await modal().locator("#imp").click();
  assert.match(await texto("#impressao"), /COMPROVANTE DE PAGAMENTO/);
  assert.match(await texto("#impressao"), /SALDO DEVEDOR ATUAL\s*R\$ 262,50/);
  await modal().locator("#ok").click();
  await pagina.waitForSelector("td:has-text('pagou no balcão')");
  cli = await api(`/api/clientes/${cliente.id}`);
  assert.strictEqual(cli.saldo_devedor, 26250);
  passo("baixa parcial: só a 1ª parcela, R$ 100,00 de R$ 181,25, troco de R$ 50,00, comprovante impresso");

  // 10. quitar tudo de uma vez no PIX; depois estornar e confirmar que a dívida volta
  assert.strictEqual(await texto("#tot-sel"), "R$ 262,50");
  await pagina.click("#formas-rc .chip[data-f=PIX]");
  assert.ok(await pagina.locator("#campo-entregue").evaluate((e) => e.classList.contains("oculto")), "troco só aparece no dinheiro");
  await pagina.click("#confirmar-rc");
  await pagina.waitForSelector("#modal-titulo:has-text('Pagamento registrado')");
  assert.match(await texto("#modal-corpo"), /Conta quitada!/);
  await modal().locator("#ok").click();
  await pagina.waitForSelector("text=Este cliente não deve nada");
  assert.strictEqual((await api(`/api/clientes/${cliente.id}`)).saldo_devedor, 0);
  await pagina.locator(".bx-est").first().click();
  await modal().locator("[name=motivo]").fill("PIX não caiu na conta");
  await enviarModal();
  await pagina.waitForSelector(".toast:has-text('Pagamento estornado')");
  await pagina.waitForSelector("td .badge:has-text('Estornado')");
  assert.strictEqual((await api(`/api/clientes/${cliente.id}`)).saldo_devedor, 26250);
  passo("quitação total no PIX e estorno: a dívida de R$ 262,50 volta para o cliente");

  // 11. pelo Contas a receber, receber só a parcela escolhida
  await ir("receber");
  await pagina.locator(".rec").first().click();
  await pagina.waitForSelector("#confirmar-rc");
  assert.strictEqual(await texto("#tot-sel"), "R$ 81,25");
  await pagina.click("#formas-rc .chip[data-f=DEBITO]");
  await pagina.click("#confirmar-rc");
  await pagina.waitForSelector("#modal-titulo:has-text('Pagamento registrado')");
  await modal().locator("#ok").click();
  cli = await api(`/api/clientes/${cliente.id}`);
  assert.strictEqual(cli.saldo_devedor, 18125);
  assert.deepStrictEqual(cli.parcelas.map((p) => p.status), ["PAGA", "ABERTA"]);
  passo("em Contas a receber, 'Receber' abre a baixa já com a parcela marcada (R$ 81,25 no débito)");

  // 12. devolução de 1 saco da primeira venda
  await ir("vendas");
  await pagina.locator(".ver").last().click();
  await modal().locator("#dev").click();
  await modal().locator("input[name^=item_]").fill("1");
  await modal().locator("[name=motivo]").fill("Sobrou");
  await enviarModal();
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 48000);
  passo("devolução de 1 saco: estoque 47 → 48 e R$ 38,90 devolvidos do caixa");

  // 13. orçamento e conversão em venda
  await ir("pdv");
  await pagina.fill("#qtd", "4");
  await pagina.fill("#busca", "CIM");
  await pagina.press("#busca", "Enter");
  await pagina.waitForSelector("#itens td:has-text('Cimento')");
  await pagina.fill("#desconto", "5,60");
  await pagina.click("#orcamento");
  await modal().locator("[name=nome_cliente]").fill("Sr. Pedro");
  await modal().locator("button[type=submit]").click();
  await pagina.waitForSelector("#modal-titulo:has-text('Orçamento salvo')");
  assert.match(await texto("#modal-corpo"), /R\$ 150,00/);
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 48000);
  await ir("orcamentos");
  await pagina.click(".ver");
  await modal().locator("#conv").click();
  await pagina.waitForSelector("#modal-corpo .chip[data-f=DEBITO]");
  await modal().locator(".chip[data-f=DEBITO]").click();
  await modal().locator("#ok").click();
  await pagina.waitForSelector("#modal-titulo:has-text('Venda concluída')");
  await pagina.keyboard.press("Escape");
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 44000);
  assert.strictEqual((await api("/api/orcamentos"))[0].status, "CONVERTIDO");
  passo("orçamento de R$ 150,00 salvo sem mexer no estoque e depois transformado em venda");

  // 14. entrada de mercadoria
  await ir("compras");
  await pagina.fill("#e-busca", "CIM");
  await pagina.press("#e-busca", "Enter");
  await pagina.waitForSelector("#e-itens td:has-text('Cimento')");
  assert.strictEqual(await pagina.inputValue(".e-custo"), "29,50");
  await pagina.fill(".e-qtd", "100");
  await pagina.fill(".e-custo", "31,50");
  assert.strictEqual(await texto("#e-total"), "Total da nota: R$ 3.150,00");
  await pagina.fill("#compra [name=nota_fiscal]", "5544");
  await pagina.click("#compra button[type=submit]");
  await pagina.waitForSelector(".toast:has-text('Entrada')");
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 144000);
  assert.strictEqual((await api("/api/contas-pagar?status=ABERTA"))[0].valor, 315000);
  passo("entrada de 100 sacos: estoque 44 → 144 e R$ 3.150,00 em contas a pagar");

  // 15. sangria e fechamento do caixa
  await ir("caixa");
  await pagina.click("#sangria");
  await modal().locator("[name=valor]").fill("50");
  await enviarModal();
  // 100 fundo + 116,70 venda + 100 baixa em dinheiro - 38,90 devolução - 50 sangria
  const esperado = 10000 + 11670 + 10000 - 3890 - 5000;
  assert.strictEqual((await api("/api/caixa")).caixa.saldo_dinheiro, esperado);
  await pagina.click("#fechar");
  await modal().locator("[name=valor_contado]").fill("227,80");
  await modal().locator("button[type=submit]").click();
  await pagina.waitForSelector("text=Caixa conferido, sem diferença.");
  await pagina.keyboard.press("Escape");
  passo("sangria de R$ 50,00 e fechamento com R$ 227,80 contados: sem diferença");

  // 16. relatórios, painel com gráfico e conferência
  await ir("relatorios");
  await pagina.click("#integridade");
  await pagina.waitForSelector("text=Tudo confere.");
  const rel = await api("/api/relatorios/vendas");
  assert.strictEqual(rel.quantidade, 3);
  assert.strictEqual(rel.liquido, 11670 + 36250 + 15000 - 3890);
  assert.strictEqual(rel.recebimentos_crediario, 10000 + 8125);
  await ir("painel");
  const dataHoje = (await api("/api/config")).hoje.split("-").reverse().join("/");
  await pagina.locator("#graf .alvo").last().hover();
  await pagina.waitForSelector("#graf .dica:not(.oculto)");
  assert.strictEqual(await texto("#graf .dica"), `R$ 590,30 ${dataHoje} · 3 vendas`);
  await pagina.click("#vis-graf button[data-v=t]");
  await pagina.waitForSelector("#graf-tab:not(.oculto)");
  passo("relatórios conferem, gráfico mostra a dica ao passar o mouse e tem visão em tabela");

  // 17. tema escuro e atalho F2
  const fundoClaro = await pagina.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await pagina.click("#tema-btn");
  assert.strictEqual(await pagina.evaluate(() => document.documentElement.dataset.theme), "dark");
  assert.notStrictEqual(await pagina.evaluate(() => getComputedStyle(document.body).backgroundColor), fundoClaro);
  await pagina.reload();
  await pagina.waitForSelector("#conteudo .kpi");
  assert.strictEqual(await pagina.evaluate(() => document.documentElement.dataset.theme), "dark", "tema escolhido deve ser lembrado");
  await pagina.keyboard.press("F2");
  await pagina.waitForSelector("#titulo-pagina:has-text('Vender')");
  passo("tema escuro liga, é lembrado ao recarregar; F2 abre a tela de venda");

  // 18. celular: nenhuma tela passa da largura e o menu abre
  await pagina.setViewportSize({ width: 390, height: 844 });
  for (const p of [...PAGINAS, `receber-cliente/${cliente.id}`]) {
    await ir(p);
    const [sw, cw] = await pagina.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    assert.ok(sw <= cw, `tela ${p} passa da largura do celular (${sw} > ${cw})`);
  }
  await pagina.click("#menu-btn");
  await pagina.waitForSelector(".app.menu-aberto");
  await pagina.click("#sidebar a[href='#clientes']");
  await pagina.waitForSelector("#titulo-pagina:has-text('Clientes')");
  passo("no celular todas as telas cabem na largura e o menu lateral abre e navega");

  await navegador.close();
  assert.deepStrictEqual(errosJs, [], "erros de JavaScript no navegador");
  passo("nenhum erro de JavaScript no navegador");
}

principal().catch((e) => {
  console.error(e);
  if (errosJs.length) console.error("Erros JS:", errosJs);
  process.exit(1);
});
