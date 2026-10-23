// Teste da interface em navegador real (Chromium + Playwright).
// Uso: node tests/interface.e2e.js http://127.0.0.1:PORTA
const { chromium } = require("playwright");
const assert = require("assert");

const URL_BASE = process.argv[2];
const errosJs = [];

async function principal() {
  const navegador = await chromium.launch();
  const pagina = await navegador.newPage({ viewport: { width: 1366, height: 900 } });
  await pagina.addInitScript(() => { window.print = () => { window.__impresso = (window.__impresso || 0) + 1; }; });
  pagina.on("pageerror", (e) => errosJs.push("pageerror: " + e.message));
  // respostas 400 são recusas de regra de negócio provocadas de propósito pelo teste (viram aviso na tela)
  pagina.on("console", (m) => { if (m.type() === "error" && !/status of 40[04]/.test(m.text())) errosJs.push("console: " + m.text()); });
  pagina.on("response", (r) => { if (r.status() >= 500) errosJs.push(`HTTP ${r.status()} em ${r.url()}`); });
  pagina.on("dialog", (d) => d.accept());

  const api = async (caminho) => (await pagina.request.get(URL_BASE + caminho)).json();
  const ir = async (hash) => {
    await pagina.goto(`${URL_BASE}/#${hash}`);
    await pagina.waitForSelector("#conteudo h1");
  };
  const modal = () => pagina.locator("#modal-corpo");
  const esperarModalFechar = () => pagina.waitForSelector("#modal.oculto", { state: "attached" });
  const passo = (t) => console.log("  ✓ " + t);

  // 1. todas as páginas abrem sem erro, mesmo com o banco vazio
  await pagina.goto(URL_BASE + "/");
  for (const p of ["painel", "pdv", "vendas", "orcamentos", "caixa", "produtos", "compras", "movimentos",
    "clientes", "fornecedores", "receber", "pagar", "relatorios"]) {
    await ir(p);
    assert.strictEqual(await pagina.locator("text=Erro ao carregar").count(), 0, `página ${p} com erro`);
  }
  passo("todas as 13 telas abrem com o banco vazio");

  // 2. abrir caixa
  await ir("caixa");
  await pagina.fill("#abrir [name=valor_inicial]", "100,00");
  await pagina.fill("#abrir [name=operador]", "Ana");
  await pagina.click("#abrir button[type=submit]");
  await pagina.waitForSelector("text=Caixa aberto desde");
  passo("caixa aberto com fundo de troco R$ 100,00");

  // 3. fornecedor
  await ir("fornecedores");
  await pagina.click("#novo");
  await modal().locator("[name=nome]").fill("Distribuidora Central");
  await modal().locator("[name=documento]").fill("11.222.333/0001-81");
  await modal().locator("button[type=submit]").click();
  await esperarModalFechar();
  await pagina.waitForSelector("td:has-text('Distribuidora Central')");
  passo("fornecedor cadastrado");

  // 4. produtos
  async function novoProduto(campos) {
    await ir("produtos");
    await pagina.click("#novo");
    for (const [k, v] of Object.entries(campos)) {
      const el = modal().locator(`[name=${k}]`);
      if ((await el.evaluate((e) => e.tagName)) === "SELECT") await el.selectOption(v);
      else await el.fill(v);
    }
    await modal().locator("button[type=submit]").click();
    await esperarModalFechar();
    await pagina.waitForSelector(`td:has-text('${campos.nome}')`);
  }
  await novoProduto({ codigo: "CIM", nome: "Cimento CP-II 50kg", categoria: "Cimento", unidade: "SC", preco_custo: "29,50", preco_venda: "38,90", estoque_minimo: "10", estoque_inicial: "50" });
  await novoProduto({ codigo: "ARE", nome: "Areia média", categoria: "Agregados", unidade: "M3", preco_custo: "90", preco_venda: "145", estoque_inicial: "10" });
  // erro de validação aparece como aviso, sem fechar o formulário
  await pagina.click("#novo");
  await modal().locator("[name=nome]").fill("Produto ruim");
  await modal().locator("[name=preco_venda]").fill("abc");
  await modal().locator("button[type=submit]").click();
  await pagina.waitForSelector("#aviso .erro");
  assert.ok(await pagina.isVisible("#modal-corpo form"));
  await pagina.click("#modal-fechar");
  let prods = await api("/api/produtos");
  assert.strictEqual(prods.length, 2);
  const cim = prods.find((p) => p.codigo === "CIM");
  const are = prods.find((p) => p.codigo === "ARE");
  assert.strictEqual(cim.estoque, 50000);
  passo("produtos cadastrados; valor inválido mostra mensagem de erro e não grava");

  // 5. cliente
  await ir("clientes");
  await pagina.click("#novo");
  await modal().locator("[name=nome]").fill("Construtora Boa Obra");
  await modal().locator("[name=documento]").fill("529.982.247-25");
  await modal().locator("[name=limite_credito]").fill("1.000,00");
  await modal().locator("button[type=submit]").click();
  await esperarModalFechar();
  await pagina.waitForSelector("td:has-text('Construtora Boa Obra')");
  const cliente = (await api("/api/clientes"))[0];
  passo("cliente cadastrado com limite de R$ 1.000,00");

  // 6. venda em dinheiro com troco
  await ir("pdv");
  await pagina.fill("#qtd", "3");
  await pagina.fill("#busca", "CIM");
  await pagina.press("#busca", "Enter");
  await pagina.waitForSelector("#itens td:has-text('Cimento')");
  assert.strictEqual(await pagina.textContent("#total"), "R$ 116,70");
  await pagina.fill(".pg-valor", "150");
  assert.match(await pagina.textContent(".resumo-pag"), /Troco: R\$ 33,30/);
  await pagina.click("#finalizar");
  await pagina.waitForSelector("#modal-titulo:has-text('concluída')");
  assert.match(await modal().textContent(), /Troco: R\$ 33,30/);
  await modal().locator("#imp").click();
  assert.strictEqual(await pagina.evaluate(() => window.__impresso), 1);
  assert.match(await pagina.textContent("#impressao"), /TOTAL\s*R\$ 116,70/);
  await modal().locator("#ok").click();
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 47000);
  passo("venda de 3 sacos: total R$ 116,70, troco R$ 33,30, estoque 50 → 47, comprovante impresso");

  // 7. busca por nome, desconto e pagamento faltando
  await pagina.fill("#qtd", "2,5");
  await pagina.fill("#busca", "areia");
  await pagina.waitForSelector("#resultados div[data-n]");
  await pagina.click("#resultados div[data-n]");
  await pagina.waitForSelector("#itens td:has-text('Areia')");
  assert.strictEqual(await pagina.textContent("#total"), "R$ 362,50");
  await pagina.fill("#desconto-pct", "10");
  assert.strictEqual(await pagina.textContent("#total"), "R$ 326,25");
  await pagina.fill("#desconto-pct", "");
  await pagina.fill("#desconto", "");
  await pagina.dispatchEvent("#desconto", "input");
  await pagina.fill(".pg-valor", "100");
  assert.match(await pagina.textContent(".resumo-pag"), /Falta R\$ 262,50/);
  await pagina.click("#finalizar");
  await pagina.waitForSelector("#aviso .erro:has-text('Pagamento insuficiente')");
  assert.strictEqual((await api(`/api/produtos/${are.id}`)).estoque, 10000);
  passo("pagamento faltando é recusado e o estoque não muda");

  // 8. mesma venda no crediário em 2x
  await pagina.selectOption("#sel-cliente select", String(cliente.id));
  await pagina.selectOption(".pg-forma", "CREDIARIO");
  await pagina.fill(".pg-valor", "");
  await pagina.fill(".cred-parcelas", "2");
  await pagina.click("#finalizar");
  await pagina.waitForSelector("#modal-titulo:has-text('concluída')");
  await pagina.click("#modal-fechar");
  let cli = await api(`/api/clientes/${cliente.id}`);
  assert.strictEqual(cli.saldo_devedor, 36250);
  assert.deepStrictEqual(cli.parcelas.map((p) => p.valor), [18125, 18125]);
  assert.strictEqual((await api(`/api/produtos/${are.id}`)).estoque, 7500);
  passo("venda de 2,5 m³ no crediário em 2x de R$ 181,25; cliente deve R$ 362,50");

  // 9. receber parcela em contas a receber
  await ir("receber");
  await pagina.click(".rec >> nth=0");
  await modal().locator("[name=valor]").fill("100,00");
  await modal().locator("button[type=submit]").click();
  await esperarModalFechar();
  cli = await api(`/api/clientes/${cliente.id}`);
  assert.strictEqual(cli.saldo_devedor, 26250);
  // receber o restante pelo extrato do cliente
  await ir("clientes");
  await pagina.click(".ex");
  await pagina.waitForSelector("#receber");
  assert.strictEqual(await pagina.inputValue("#receber [name=valor]"), "262,50");
  await pagina.selectOption("#receber [name=forma]", "PIX");
  await pagina.click("#receber button[type=submit]");
  await pagina.waitForSelector("#aviso .ok:has-text('Saldo restante: R$ 0,00')");
  await pagina.click("#modal-fechar");
  passo("parcela recebida (R$ 100,00 em dinheiro) e restante quitado pelo extrato (R$ 262,50 PIX)");

  // 10. devolução de 1 saco da primeira venda
  await ir("vendas");
  await pagina.click(".ver >> nth=-1");
  await pagina.click("#dev");
  await modal().locator("input[name^=item_]").fill("1");
  await modal().locator("[name=motivo]").fill("Sobrou");
  await modal().locator("button[type=submit]").click();
  await esperarModalFechar();
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 48000);
  passo("devolução de 1 saco: estoque 47 → 48 e R$ 38,90 devolvidos do caixa");

  // 11. orçamento e conversão em venda
  await ir("pdv");
  await pagina.fill("#qtd", "4");
  await pagina.fill("#busca", "CIM");
  await pagina.press("#busca", "Enter");
  await pagina.waitForSelector("#itens td:has-text('Cimento')");
  await pagina.fill("#itens .q", "5");
  assert.strictEqual(await pagina.textContent("#total"), "R$ 194,50");
  await pagina.fill("#itens .q", "4");
  await pagina.fill("#desconto", "5,60");
  await pagina.dispatchEvent("#desconto", "input");
  await pagina.click("#orcamento");
  await modal().locator("[name=nome_cliente]").fill("Sr. Pedro");
  await modal().locator("button[type=submit]").click();
  await pagina.waitForSelector("#modal-titulo:has-text('Orçamento nº')");
  assert.match(await modal().textContent(), /R\$ 150,00/);
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 48000);
  await ir("orcamentos");
  await pagina.click(".ver");
  await pagina.click("#conv");
  await pagina.waitForSelector("#modal-corpo #ok");
  await pagina.selectOption("#modal-corpo .pg-forma", "DEBITO");
  await pagina.click("#modal-corpo #ok");
  await pagina.waitForSelector("#modal-titulo:has-text('concluída')");
  await pagina.click("#modal-fechar");
  assert.strictEqual((await api(`/api/produtos/${cim.id}`)).estoque, 44000);
  assert.strictEqual((await api("/api/orcamentos"))[0].status, "CONVERTIDO");
  passo("orçamento de R$ 150,00 salvo sem mexer no estoque e depois convertido em venda");

  // 12. entrada de mercadoria
  await ir("compras");
  await pagina.fill(".cp-prod", "CIM — Cimento CP-II 50kg");
  assert.strictEqual(await pagina.inputValue(".cp-custo"), "29,50");
  await pagina.fill(".cp-qtd", "100");
  await pagina.fill(".cp-custo", "31,50");
  assert.strictEqual(await pagina.textContent("#total-compra"), "Total: R$ 3.150,00");
  await pagina.fill("#compra [name=nota_fiscal]", "5544");
  await pagina.click("#compra button[type=submit]");
  await pagina.waitForSelector("#aviso .ok:has-text('Entrada')");
  const cimAtual = await api(`/api/produtos/${cim.id}`);
  assert.strictEqual(cimAtual.estoque, 144000);
  const pagar = await api("/api/contas-pagar?status=ABERTA");
  assert.strictEqual(pagar[0].valor, 315000);
  passo("entrada de 100 sacos: estoque 44 → 144 e R$ 3.150,00 em contas a pagar");

  // 13. sangria e fechamento do caixa
  await ir("caixa");
  await pagina.click("#sangria");
  await modal().locator("[name=valor]").fill("50");
  await modal().locator("button[type=submit]").click();
  await esperarModalFechar();
  const caixa = (await api("/api/caixa")).caixa;
  // 100 fundo + 116,70 venda + 100 parcela - 38,90 devolução - 50 sangria
  assert.strictEqual(caixa.saldo_dinheiro, 10000 + 11670 + 10000 - 3890 - 5000);
  await pagina.click("#fechar");
  await modal().locator("[name=valor_contado]").fill("227,80");
  await modal().locator("button[type=submit]").click();
  await pagina.waitForSelector("text=Caixa conferido, sem diferença.");
  passo("sangria de R$ 50,00 e fechamento com R$ 227,80 contados: sem diferença");

  // 14. relatórios e conferência
  await ir("relatorios");
  await pagina.click("#integridade");
  await pagina.waitForSelector("text=Tudo confere");
  const rel = await api("/api/relatorios/vendas");
  assert.strictEqual(rel.quantidade, 3);
  assert.strictEqual(rel.liquido, 11670 + 36250 + 15000 - 3890);
  passo("relatórios conferem e verificação de consistência sem problemas");

  // 15. tudo de novo em tela de celular
  await pagina.setViewportSize({ width: 390, height: 844 });
  for (const p of ["painel", "pdv", "vendas", "produtos", "caixa", "relatorios"]) await ir(p);
  passo("telas abrem em tamanho de celular");

  await navegador.close();
  assert.deepStrictEqual(errosJs, [], "erros de JavaScript no navegador");
  passo("nenhum erro de JavaScript no navegador");
}

principal().catch((e) => {
  console.error(e);
  if (errosJs.length) console.error("Erros JS:", errosJs);
  process.exit(1);
});
