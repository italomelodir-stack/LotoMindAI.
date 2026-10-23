"use strict";
// Interface do sistema da loja. Valores chegam da API em centavos e quantidades em milésimos.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const R = (c) => "R$ " + ((c || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const Q = (m) => ((m || 0) / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 3 });
const paraCampo = (c) => ((c || 0) / 100).toFixed(2).replace(".", ",");
const qtdCampo = (m) => String((m || 0) / 1000).replace(".", ",");
const dataBR = (s) => {
  if (!s) return "";
  const [d, h] = String(s).split(" ");
  const [a, m, dia] = d.split("-");
  return `${dia}/${m}/${a}` + (h ? " " + h.slice(0, 5) : "");
};
const NOMES_FORMA = { DINHEIRO: "Dinheiro", PIX: "PIX", DEBITO: "Cartão de débito", CREDITO: "Cartão de crédito", CREDIARIO: "Crediário (fiado)",
  DINHEIRO_CAIXA: "Dinheiro do caixa", TRANSFERENCIA: "Transferência", BOLETO: "Boleto", CHEQUE: "Cheque" };
const forma = (f) => NOMES_FORMA[f] || f;

function centavos(s) {
  s = String(s ?? "").trim().replace(/R\$|\s/g, "");
  if (!s) return 0;
  if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
  const n = Number(s);
  return Number.isFinite(n) ? Math.round(n * 100) : NaN;
}
function milesimos(s) {
  const n = Number(String(s ?? "").trim().replace(",", "."));
  return Number.isFinite(n) ? Math.round(n * 1000) : NaN;
}

let CONFIG = {};

async function api(metodo, caminho, corpo) {
  const op = { method: metodo, headers: {} };
  if (corpo !== undefined) {
    op.headers["Content-Type"] = "application/json";
    op.body = JSON.stringify(corpo);
  }
  const resp = await fetch(caminho, op);
  const dados = await resp.json().catch(() => ({ erro: "Resposta inválida do servidor" }));
  if (!resp.ok) throw new Error(dados.erro || `Erro ${resp.status}`);
  return dados;
}
const GET = (c) => api("GET", c);
const POST = (c, b = {}) => api("POST", c, b);
const PUT = (c, b) => api("PUT", c, b);

function avisar(msg, tipo = "ok") {
  const d = document.createElement("div");
  d.className = tipo;
  d.textContent = msg;
  $("#aviso").appendChild(d);
  setTimeout(() => d.remove(), tipo === "erro" ? 6000 : 3000);
}
const erro = (e) => avisar(e.message || String(e), "erro");

function dadosForm(form) {
  const d = {};
  new FormData(form).forEach((v, k) => (d[k] = v));
  $$("input[type=checkbox]", form).forEach((c) => (d[c.name] = c.checked));
  return d;
}

// ---------------------------------------------------------------- modal
function abrirModal(titulo, html, largura) {
  $("#modal-titulo").textContent = titulo;
  $("#modal-corpo").innerHTML = html;
  $(".janela").style.maxWidth = largura || "760px";
  $("#modal").classList.remove("oculto");
  const primeiro = $("#modal-corpo input:not([type=hidden]), #modal-corpo select");
  if (primeiro) primeiro.focus();
  return $("#modal-corpo");
}
function fecharModal() { $("#modal").classList.add("oculto"); $("#modal-corpo").innerHTML = ""; }
$("#modal-fechar").onclick = fecharModal;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharModal(); });

// envia um formulário do modal; recarrega a página atual ao concluir
function aoEnviar(form, acao, msg) {
  form.onsubmit = async (e) => {
    e.preventDefault();
    const botao = $("button[type=submit]", form);
    if (botao) botao.disabled = true;
    try {
      const r = await acao(dadosForm(form));
      if (msg) avisar(msg);
      fecharModal();
      await renderizar();
      return r;
    } catch (err) {
      erro(err);
    } finally {
      if (botao) botao.disabled = false;
    }
  };
}

function imprimir(html) {
  $("#impressao").innerHTML = html;
  window.print();
}

// ------------------------------------------------------- componentes
const opcoes = (lista, sel) => lista.map((o) => `<option value="${esc(o[0])}" ${String(o[0]) === String(sel ?? "") ? "selected" : ""}>${esc(o[1])}</option>`).join("");

async function selectClientes(sel, nome = "cliente_id") {
  const clientes = await GET("/api/clientes?ativos=1");
  return `<select name="${nome}"><option value="">— Consumidor (sem cadastro) —</option>${opcoes(
    clientes.map((c) => [c.id, `${c.nome}${c.documento ? " · " + c.documento : ""}`]), sel)}</select>`;
}

// Bloco de formas de pagamento reutilizado no PDV e na conversão de orçamentos.
// Valor em branco = "o que falta".
function widgetPagamentos(el, obterTotal) {
  let linhas = [{ forma: "DINHEIRO", valor: "" }];
  const formas = CONFIG.formas_pagamento || [];
  function calcular() {
    const total = obterTotal();
    let preenchido = 0;
    linhas.forEach((l) => { if (l.valor.trim()) preenchido += centavos(l.valor) || 0; });
    const vazio = linhas.find((l) => !l.valor.trim());
    const valores = linhas.map((l) => (l.valor.trim() ? centavos(l.valor) : l === vazio ? Math.max(0, total - preenchido) : 0));
    const pago = valores.reduce((a, b) => a + (b || 0), 0);
    return { total, valores, pago };
  }
  function resumo() {
    const { total, pago, valores } = calcular();
    const dinheiro = linhas.reduce((s, l, i) => s + (l.forma === "DINHEIRO" ? valores[i] || 0 : 0), 0);
    const diff = pago - total;
    let txt;
    if (diff < 0) txt = `<span class="texto-erro">Falta ${R(-diff)}</span>`;
    else if (diff > 0 && dinheiro > diff) txt = `<b class="texto-ok">Troco: ${R(diff)}</b>`;
    else if (diff > 0) txt = `<span class="texto-erro">Passou ${R(diff)} (troco só em dinheiro)</span>`;
    else txt = `<span class="texto-ok">Pagamento completo</span>`;
    $(".resumo-pag", el).innerHTML = txt;
    const temCred = linhas.some((l) => l.forma === "CREDIARIO");
    $(".crediario", el).style.display = temCred ? "" : "none";
    linhas.forEach((l, i) => {
      const inp = $$(".pg-valor", el)[i];
      if (inp) inp.placeholder = paraCampo(valores[i]);
    });
  }
  function desenhar() {
    el.innerHTML = `
      <div class="linhas-pag">${linhas.map((l, i) => `
        <div class="pagamento">
          <select class="pg-forma" data-i="${i}">${opcoes(formas.map((f) => [f, forma(f)]), l.forma)}</select>
          <input class="pg-valor" data-i="${i}" value="${esc(l.valor)}" inputmode="decimal">
          <button type="button" class="pequeno pg-remover" data-i="${i}" title="Remover" ${linhas.length === 1 ? "disabled" : ""}>✕</button>
        </div>`).join("")}</div>
      <button type="button" class="pequeno pg-mais">+ Outra forma de pagamento</button>
      <div class="crediario grade" style="margin-top:8px">
        <label>Parcelas<input class="cred-parcelas" type="number" min="1" max="24" value="1"></label>
        <label>1º vencimento<input class="cred-venc" type="date"></label>
      </div>
      <div class="resumo-pag" style="margin-top:8px"></div>`;
    $$(".pg-forma", el).forEach((s) => (s.onchange = () => { linhas[s.dataset.i].forma = s.value; resumo(); }));
    $$(".pg-valor", el).forEach((s) => (s.oninput = () => { linhas[s.dataset.i].valor = s.value; resumo(); }));
    $$(".pg-remover", el).forEach((b) => (b.onclick = () => { linhas.splice(b.dataset.i, 1); desenhar(); }));
    $(".pg-mais", el).onclick = () => { linhas.push({ forma: "PIX", valor: "" }); desenhar(); };
    resumo();
  }
  desenhar();
  return {
    atualizar: resumo,
    limpar() { linhas = [{ forma: "DINHEIRO", valor: "" }]; desenhar(); },
    dados() {
      const { valores } = calcular();
      const pagamentos = linhas.map((l, i) => ({ forma: l.forma, valor: paraCampo(valores[i]) })).filter((p, i) => valores[i] > 0);
      const r = { pagamentos };
      if (linhas.some((l) => l.forma === "CREDIARIO")) {
        r.crediario = { parcelas: $(".cred-parcelas", el).value || 1 };
        if ($(".cred-venc", el).value) r.crediario.primeiro_vencimento = $(".cred-venc", el).value;
      }
      return r;
    },
  };
}

// ------------------------------------------------------------ recibos
function cabecalhoRecibo(titulo) {
  return `<div style="text-align:center"><b>${esc(CONFIG.nome_loja)}</b><br>${esc(titulo)}</div><hr>`;
}
function reciboVenda(v) {
  return `<div class="recibo">${cabecalhoRecibo(`VENDA Nº ${v.id} — ${dataBR(v.data)}`)}
    ${v.cliente ? `Cliente: ${esc(v.cliente)}<br>` : ""}${v.status === "CANCELADA" ? "<b>*** VENDA CANCELADA ***</b><br>" : ""}
    <table><tr><th>Item</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th></tr>
    ${v.itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade)} ${esc(i.unidade)}</td><td class="num">${R(i.preco_unitario)}</td><td class="num">${R(i.total)}</td></tr>`).join("")}
    </table><hr>
    <div class="linha-total"><span>Subtotal</span><span>${R(v.subtotal)}</span></div>
    ${v.desconto ? `<div class="linha-total"><span>Desconto</span><span>-${R(v.desconto)}</span></div>` : ""}
    <div class="linha-total"><b>TOTAL</b><b>${R(v.total)}</b></div><hr>
    ${v.pagamentos.map((p) => `<div class="linha-total"><span>${forma(p.forma)}</span><span>${R(p.valor)}</span></div>`).join("")}
    ${v.troco ? `<div class="linha-total"><span>Troco</span><span>${R(v.troco)}</span></div>` : ""}
    ${v.parcelas.length ? `<hr>Parcelas do crediário:<br>${v.parcelas.map((p) => `${p.parcela}/${p.total_parcelas} — venc. ${dataBR(p.vencimento)} — ${R(p.valor_original)}`).join("<br>")}
      <br><br><br>_______________________________<br>Assinatura do cliente` : ""}
    <hr><div style="text-align:center">Obrigado pela preferência!</div></div>`;
}
function reciboOrcamento(o) {
  return `<div class="recibo">${cabecalhoRecibo(`ORÇAMENTO Nº ${o.id} — ${dataBR(o.data)}`)}
    Cliente: ${esc(o.cliente || o.nome_cliente || "—")}<br>Válido até: ${dataBR(o.validade)}
    <table><tr><th>Item</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th></tr>
    ${o.itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade)} ${esc(i.unidade)}</td><td class="num">${R(i.preco_unitario)}</td><td class="num">${R(i.total)}</td></tr>`).join("")}
    </table><hr>
    <div class="linha-total"><span>Subtotal</span><span>${R(o.subtotal)}</span></div>
    ${o.desconto ? `<div class="linha-total"><span>Desconto</span><span>-${R(o.desconto)}</span></div>` : ""}
    <div class="linha-total"><b>TOTAL</b><b>${R(o.total)}</b></div>
    ${o.observacao ? `<hr>${esc(o.observacao)}` : ""}<hr><div style="text-align:center">Orçamento sujeito à disponibilidade de estoque.</div></div>`;
}

// =============================================================== PÁGINAS
const paginas = {};

paginas.painel = async (el) => {
  const p = await GET("/api/painel");
  const v = p.vendas_hoje;
  const baixo = await GET("/api/produtos?estoque_baixo=1");
  el.innerHTML = `<h1>Painel — ${dataBR(p.data)}</h1>
    <div class="indicadores">
      <div class="indicador"><div class="rotulo">Vendas hoje</div><div class="valor">${v.quantidade}</div></div>
      <div class="indicador"><div class="rotulo">Faturamento líquido hoje</div><div class="valor">${R(v.liquido)}</div></div>
      <div class="indicador"><div class="rotulo">Lucro bruto hoje</div><div class="valor">${R(v.lucro_bruto)}</div></div>
      <div class="indicador"><div class="rotulo">Caixa</div><div class="valor">${p.caixa ? `<span class="texto-ok">Aberto</span>` : `<span class="texto-erro">Fechado</span>`}</div>
        ${p.caixa ? `<div class="suave">Dinheiro na gaveta: ${R(p.caixa.saldo_dinheiro)}</div>` : ""}</div>
      <div class="indicador"><div class="rotulo">A receber (total em aberto)</div><div class="valor">${R(p.receber_aberto)}</div></div>
      <div class="indicador"><div class="rotulo">A receber vencido</div><div class="valor ${p.receber_vencido ? "texto-erro" : ""}">${R(p.receber_vencido)}</div></div>
      <div class="indicador"><div class="rotulo">A pagar (próx. 7 dias e vencidas)</div><div class="valor">${R(p.pagar_7_dias)}</div></div>
      <div class="indicador"><div class="rotulo">Orçamentos em aberto</div><div class="valor">${p.orcamentos_abertos}</div></div>
    </div>
    <div class="cartao"><h2>Produtos com estoque baixo (${baixo.length})</h2>
      ${baixo.length ? `<div class="tabela"><table><tr><th>Código</th><th>Produto</th><th class="num">Estoque</th><th class="num">Mínimo</th></tr>
      ${baixo.map((x) => `<tr><td>${esc(x.codigo)}</td><td>${esc(x.nome)}</td><td class="num texto-erro">${Q(x.estoque)} ${x.unidade}</td><td class="num">${Q(x.estoque_minimo)}</td></tr>`).join("")}</table></div>` : `<p class="suave">Nenhum produto abaixo do mínimo.</p>`}
    </div>`;
};

// ------------------------------------------------------------------ PDV
const carrinho = [];
paginas.pdv = async (el) => {
  const caixa = (await GET("/api/caixa")).caixa;
  el.innerHTML = `<h1>Vender</h1>
    ${caixa ? "" : `<div class="cartao texto-erro">O caixa está fechado. <a href="#caixa">Abra o caixa</a> para registrar vendas (orçamentos podem ser feitos normalmente).</div>`}
    <div class="pdv">
      <div>
        <div class="cartao">
          <div class="barra">
            <label style="flex:1">Produto (código, código de barras ou nome)<input id="busca" autocomplete="off" placeholder="Digite e tecle Enter"></label>
            <label style="width:110px">Quantidade<input id="qtd" value="1" inputmode="decimal"></label>
          </div>
          <div id="resultados" class="resultados" style="display:none"></div>
        </div>
        <div class="tabela"><table><thead><tr><th>Código</th><th>Produto</th><th class="num">Qtd</th><th>Un</th><th class="num">Preço</th><th class="num">Total</th><th></th></tr></thead>
          <tbody id="itens"></tbody></table></div>
      </div>
      <div class="cartao">
        <label>Cliente<span id="sel-cliente"></span></label>
        <div class="grade" style="margin-top:8px">
          <label>Desconto (R$)<input id="desconto" inputmode="decimal" placeholder="0,00"></label>
          <label>ou Desconto (%)<input id="desconto-pct" inputmode="decimal" placeholder="0"></label>
        </div>
        <div style="margin:12px 0">
          <div class="linha-total"><span>Subtotal</span><span id="subtotal"></span></div>
          <div class="linha-total"><span>Desconto</span><span id="vdesconto"></span></div>
          <div class="linha-total"><b>Total</b><span class="total-grande" id="total"></span></div>
        </div>
        <h2>Pagamento</h2>
        <div id="pagamentos"></div>
        <div class="acoes" style="margin-top:14px">
          <button class="primario" id="finalizar" ${caixa ? "" : "disabled"}>Finalizar venda</button>
          <button id="orcamento">Salvar como orçamento</button>
          <button id="limpar" class="perigo">Limpar</button>
        </div>
      </div>
    </div>`;
  $("#sel-cliente").innerHTML = await selectClientes(window.__clientePdv);
  $("#sel-cliente select").onchange = (e) => (window.__clientePdv = e.target.value);

  function totais() {
    const subtotal = carrinho.reduce((s, i) => s + Math.round((i.produto.preco_venda * milesimos(i.quantidade)) / 1000), 0);
    let desconto = centavos($("#desconto").value) || 0;
    const pct = Number(String($("#desconto-pct").value || "0").replace(",", "."));
    if (pct) desconto = Math.round((subtotal * Math.round(pct * 100)) / 10000);
    return { subtotal, desconto, total: Math.max(0, subtotal - desconto) };
  }
  const pag = widgetPagamentos($("#pagamentos"), () => totais().total);
  const totalLinha = (i) => R(Math.round((i.produto.preco_venda * (milesimos(i.quantidade) || 0)) / 1000));
  function desenhar() {
    $("#itens").innerHTML = carrinho.map((i, n) => `<tr>
      <td>${esc(i.produto.codigo)}</td><td>${esc(i.produto.nome)}<div class="suave">Estoque: ${Q(i.produto.estoque)}</div></td>
      <td class="num"><input class="q" data-n="${n}" value="${esc(i.quantidade)}" style="width:80px;text-align:right" inputmode="decimal"></td>
      <td>${i.produto.unidade}</td><td class="num">${R(i.produto.preco_venda)}</td>
      <td class="num tl">${totalLinha(i)}</td>
      <td><button class="pequeno perigo rm" data-n="${n}">✕</button></td></tr>`).join("") ||
      `<tr><td colspan="7" class="suave">Nenhum produto adicionado.</td></tr>`;
    $$(".q").forEach((inp) => (inp.oninput = () => {
      const item = carrinho[inp.dataset.n];
      item.quantidade = inp.value;
      $(".tl", inp.closest("tr")).textContent = totalLinha(item);
      atualizarTotais();
    }));
    $$(".rm").forEach((b) => (b.onclick = () => { carrinho.splice(b.dataset.n, 1); desenhar(); }));
    atualizarTotais();
  }
  function atualizarTotais() {
    const t = totais();
    $("#subtotal").textContent = R(t.subtotal);
    $("#vdesconto").textContent = "-" + R(t.desconto);
    $("#total").textContent = R(t.total);
    pag.atualizar();
  }
  function adicionar(produto) {
    const qtd = $("#qtd").value || "1";
    if (!(milesimos(qtd) > 0)) return erro(new Error("Quantidade inválida"));
    const existente = carrinho.find((i) => i.produto.id === produto.id);
    if (existente) existente.quantidade = qtdCampo(milesimos(existente.quantidade) + milesimos(qtd));
    else carrinho.push({ produto, quantidade: qtd });
    $("#busca").value = ""; $("#qtd").value = "1";
    $("#resultados").style.display = "none";
    $("#busca").focus();
    desenhar();
  }
  let ultimos = [];
  let temporizador;
  async function buscar() {
    const termo = $("#busca").value.trim();
    if (termo.length < 2) { $("#resultados").style.display = "none"; return; }
    ultimos = await GET("/api/produtos?ativos=1&busca=" + encodeURIComponent(termo));
    $("#resultados").style.display = "";
    $("#resultados").innerHTML = ultimos.slice(0, 20).map((p, n) => `<div data-n="${n}"><span><b>${esc(p.codigo)}</b> ${esc(p.nome)}</span>
      <span>${R(p.preco_venda)} · est. ${Q(p.estoque)} ${p.unidade}</span></div>`).join("") || `<div class="suave">Nenhum produto encontrado</div>`;
    $$("#resultados div[data-n]").forEach((d) => (d.onclick = () => adicionar(ultimos[d.dataset.n])));
  }
  $("#busca").oninput = () => { clearTimeout(temporizador); temporizador = setTimeout(() => buscar().catch(erro), 250); };
  $("#busca").onkeydown = async (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const termo = $("#busca").value.trim();
    if (!termo) return;
    try { adicionar(await GET("/api/produtos/codigo/" + encodeURIComponent(termo))); return; } catch (_) { /* busca por nome */ }
    await buscar();
    if (ultimos.length === 1) adicionar(ultimos[0]);
  };
  $("#qtd").onkeydown = (e) => { if (e.key === "Enter") $("#busca").focus(); };
  $("#desconto").oninput = () => { $("#desconto-pct").value = ""; atualizarTotais(); };
  $("#desconto-pct").oninput = () => { $("#desconto").value = ""; atualizarTotais(); };
  const itensEnvio = () => carrinho.map((i) => ({ produto_id: i.produto.id, quantidade: i.quantidade }));
  const descontoEnvio = () => ({ desconto: $("#desconto").value, desconto_percentual: $("#desconto-pct").value });
  function limpar() {
    carrinho.length = 0; window.__clientePdv = "";
    $("#desconto").value = ""; $("#desconto-pct").value = ""; $("#sel-cliente select").value = "";
    pag.limpar(); desenhar();
  }
  $("#limpar").onclick = limpar;
  $("#finalizar").onclick = async () => {
    const botao = $("#finalizar");
    botao.disabled = true;
    try {
      const venda = await POST("/api/vendas", { itens: itensEnvio(), cliente_id: $("#sel-cliente select").value, ...descontoEnvio(), ...pag.dados() });
      limpar();
      atualizarStatusCaixa();
      const c = abrirModal(`Venda nº ${venda.id} concluída`, `
        <div class="total-grande">${R(venda.total)}</div>
        ${venda.troco ? `<p style="font-size:22px">Troco: <b>${R(venda.troco)}</b></p>` : ""}
        <div class="acoes"><button class="primario" id="imp">Imprimir comprovante</button><button id="ok">Nova venda</button></div>`, "420px");
      $("#imp", c).onclick = () => imprimir(reciboVenda(venda));
      $("#ok", c).onclick = () => { fecharModal(); $("#busca").focus(); };
    } catch (e) { erro(e); } finally { botao.disabled = false; }
  };
  $("#orcamento").onclick = () => {
    const c = abrirModal("Salvar orçamento", `<form class="grade">
      <label>Nome do cliente (se não cadastrado)<input name="nome_cliente"></label>
      <label>Validade (dias)<input name="validade_dias" type="number" value="10" min="1"></label>
      <label class="largo">Observação<textarea name="observacao" rows="2"></textarea></label>
      <div class="largo"><button class="primario" type="submit">Salvar orçamento</button></div></form>`, "520px");
    $("form", c).onsubmit = async (e) => {
      e.preventDefault();
      try {
        const o = await POST("/api/orcamentos", { ...dadosForm(e.target), itens: itensEnvio(), cliente_id: $("#sel-cliente select").value, ...descontoEnvio() });
        limpar();
        const c2 = abrirModal(`Orçamento nº ${o.id} salvo`, `<p>Total: <b>${R(o.total)}</b> — válido até ${dataBR(o.validade)}</p>
          <button class="primario" id="imp">Imprimir orçamento</button>`, "420px");
        $("#imp", c2).onclick = () => imprimir(reciboOrcamento(o));
      } catch (err) { erro(err); }
    };
  };
  desenhar();
  $("#busca").focus();
};

// ---------------------------------------------------------------- vendas
function etiquetaStatus(s) {
  const cls = { CONCLUIDA: "ok", PAGA: "ok", CONVERTIDO: "ok", ABERTO: "alerta", ABERTA: "alerta", CANCELADA: "erro", CANCELADO: "erro", FECHADO: "" }[s] ?? "";
  return `<span class="etiqueta ${cls}">${esc(s)}</span>`;
}
const filtroDatas = { inicio: "", fim: "" };
paginas.vendas = async (el) => {
  filtroDatas.inicio ||= CONFIG.hoje; filtroDatas.fim ||= CONFIG.hoje;
  const lista = await GET(`/api/vendas?inicio=${filtroDatas.inicio}&fim=${filtroDatas.fim}`);
  const total = lista.filter((v) => v.status === "CONCLUIDA").reduce((s, v) => s + v.total - v.total_devolvido, 0);
  el.innerHTML = `<h1>Vendas</h1>
    <form class="barra" id="filtro"><label>De<input type="date" name="inicio" value="${filtroDatas.inicio}"></label>
      <label>Até<input type="date" name="fim" value="${filtroDatas.fim}"></label><button type="submit">Filtrar</button>
      <span class="suave">${lista.length} venda(s) · líquido ${R(total)}</span></form>
    <div class="tabela"><table><tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Pagamento</th><th class="num">Total</th><th class="num">Devolvido</th><th>Status</th><th></th></tr>
    ${lista.map((v) => `<tr><td>${v.id}</td><td>${dataBR(v.data)}</td><td>${esc(v.cliente || "Consumidor")}</td>
      <td>${esc((v.formas || "").split(", ").map(forma).join(", "))}</td><td class="num">${R(v.total)}</td>
      <td class="num">${v.total_devolvido ? R(v.total_devolvido) : ""}</td><td>${etiquetaStatus(v.status)}</td>
      <td><button class="pequeno ver" data-id="${v.id}">Ver</button></td></tr>`).join("") || `<tr><td colspan="8" class="suave">Nenhuma venda no período.</td></tr>`}</table></div>`;
  $("#filtro").onsubmit = (e) => { e.preventDefault(); Object.assign(filtroDatas, dadosForm(e.target)); renderizar(); };
  $$(".ver").forEach((b) => (b.onclick = () => verVenda(b.dataset.id).catch(erro)));
};

async function verVenda(id) {
  const v = await GET("/api/vendas/" + id);
  const c = abrirModal(`Venda nº ${v.id}`, `
    <p>${dataBR(v.data)} · Cliente: <b>${esc(v.cliente || "Consumidor")}</b> · ${etiquetaStatus(v.status)}
    ${v.status === "CANCELADA" ? `<br><span class="texto-erro">Cancelada em ${dataBR(v.cancelada_em)}: ${esc(v.motivo_cancelamento)}</span>` : ""}</p>
    <div class="tabela"><table><tr><th>Produto</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th><th class="num">Devolvido</th></tr>
    ${v.itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade)} ${i.unidade}</td><td class="num">${R(i.preco_unitario)}</td>
      <td class="num">${R(i.total)}</td><td class="num">${i.quantidade_devolvida ? `${Q(i.quantidade_devolvida)} (${R(i.valor_devolvido)})` : ""}</td></tr>`).join("")}</table></div>
    <p>Subtotal ${R(v.subtotal)} · Desconto ${R(v.desconto)} · <b>Total ${R(v.total)}</b>${v.total_devolvido ? ` · Devolvido ${R(v.total_devolvido)}` : ""}</p>
    <p>Pagamentos: ${v.pagamentos.map((p) => `${forma(p.forma)} ${R(p.valor)}${p.troco ? ` (troco ${R(p.troco)})` : ""}`).join(" · ")}</p>
    ${v.parcelas.length ? `<h2>Parcelas</h2><div class="tabela"><table><tr><th>Parcela</th><th>Vencimento</th><th class="num">Valor</th><th class="num">Pago</th><th>Status</th></tr>
      ${v.parcelas.map((p) => `<tr><td>${p.parcela}/${p.total_parcelas}</td><td>${dataBR(p.vencimento)}</td><td class="num">${R(p.valor)}</td><td class="num">${R(p.valor_pago)}</td><td>${etiquetaStatus(p.status)}</td></tr>`).join("")}</table></div>` : ""}
    ${v.devolucoes.length ? `<h2>Devoluções</h2>${v.devolucoes.map((d) => `<p>${dataBR(d.data)} — ${R(d.valor)} (abatido do crediário ${R(d.valor_abatido)}, reembolsado ${R(d.valor_reembolsado)} em ${forma(d.forma_reembolso)}) ${esc(d.motivo)}</p>`).join("")}` : ""}
    <div class="acoes" style="margin-top:12px"><button id="imp">Imprimir</button>
      ${v.status === "CONCLUIDA" ? `<button id="dev">Devolução de itens</button><button id="canc" class="perigo">Cancelar venda</button>` : ""}</div>`);
  $("#imp", c).onclick = () => imprimir(reciboVenda(v));
  if (v.status !== "CONCLUIDA") return;
  $("#canc", c).onclick = () => {
    const c2 = abrirModal(`Cancelar venda nº ${v.id}`, `<form><p>O estoque volta, as parcelas são canceladas e o valor recebido sai do caixa.</p>
      <label>Motivo<input name="motivo" required></label><p><button type="submit" class="perigo">Confirmar cancelamento</button></p></form>`, "480px");
    aoEnviar($("form", c2), (d) => POST(`/api/vendas/${v.id}/cancelar`, d), "Venda cancelada");
  };
  $("#dev", c).onclick = () => {
    const itens = v.itens.filter((i) => i.quantidade > i.quantidade_devolvida);
    const c2 = abrirModal(`Devolução — venda nº ${v.id}`, `<form>
      <div class="tabela"><table><tr><th>Produto</th><th class="num">Pode devolver</th><th class="num">Devolver</th></tr>
      ${itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade - i.quantidade_devolvida)} ${i.unidade}</td>
        <td class="num"><input name="item_${i.id}" value="0" style="width:80px;text-align:right" inputmode="decimal"></td></tr>`).join("")}</table></div>
      <div class="grade" style="margin-top:10px"><label>Motivo<input name="motivo"></label>
      <label>Reembolso em<select name="forma_reembolso">${opcoes((CONFIG.formas_reembolso || []).map((f) => [f, forma(f)]))}</select></label></div>
      <p class="suave">Se a venda tiver crediário em aberto, o valor devolvido abate primeiro a dívida do cliente; só o que sobrar é reembolsado.</p>
      <button type="submit" class="primario">Registrar devolução</button></form>`);
    aoEnviar($("form", c2), (d) => {
      const lista = itens.filter((i) => milesimos(d["item_" + i.id]) > 0).map((i) => ({ item_id: i.id, quantidade: d["item_" + i.id] }));
      return POST(`/api/vendas/${v.id}/devolucao`, { itens: lista, motivo: d.motivo, forma_reembolso: d.forma_reembolso })
        .then((r) => { avisar(`Devolução de ${R(r.valor)} registrada (abatido ${R(r.valor_abatido)}, reembolsado ${R(r.valor_reembolsado)})`); return r; });
    });
  };
}

// ------------------------------------------------------------ orçamentos
paginas.orcamentos = async (el) => {
  const lista = await GET("/api/orcamentos");
  el.innerHTML = `<h1>Orçamentos</h1><p class="suave">Para criar um orçamento, monte os itens na tela <a href="#pdv">Vender</a> e clique em "Salvar como orçamento".</p>
    <div class="tabela"><table><tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Validade</th><th class="num">Total</th><th>Status</th><th></th></tr>
    ${lista.map((o) => `<tr><td>${o.id}</td><td>${dataBR(o.data)}</td><td>${esc(o.cliente || o.nome_cliente || "—")}</td>
      <td>${dataBR(o.validade)} ${o.status === "ABERTO" && o.validade < CONFIG.hoje ? `<span class="etiqueta erro">vencido</span>` : ""}</td>
      <td class="num">${R(o.total)}</td><td>${etiquetaStatus(o.status)}${o.venda_id ? ` venda nº ${o.venda_id}` : ""}</td>
      <td><button class="pequeno ver" data-id="${o.id}">Ver</button></td></tr>`).join("") || `<tr><td colspan="7" class="suave">Nenhum orçamento.</td></tr>`}</table></div>`;
  $$(".ver").forEach((b) => (b.onclick = () => verOrcamento(b.dataset.id).catch(erro)));
};

async function verOrcamento(id) {
  const o = await GET("/api/orcamentos/" + id);
  const c = abrirModal(`Orçamento nº ${o.id}`, `
    <p>${dataBR(o.data)} · Cliente: <b>${esc(o.cliente || o.nome_cliente || "—")}</b> · válido até ${dataBR(o.validade)} · ${etiquetaStatus(o.status)}
    ${o.vencido ? `<span class="etiqueta erro">vencido</span>` : ""}</p>
    <div class="tabela"><table><tr><th>Produto</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th><th class="num">Estoque atual</th></tr>
    ${o.itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade)} ${i.unidade}</td><td class="num">${R(i.preco_unitario)}</td><td class="num">${R(i.total)}</td>
      <td class="num ${i.estoque < i.quantidade ? "texto-erro" : ""}">${Q(i.estoque)}</td></tr>`).join("")}</table></div>
    <p>Subtotal ${R(o.subtotal)} · Desconto ${R(o.desconto)} · <b>Total ${R(o.total)}</b></p>
    <div class="acoes"><button id="imp">Imprimir</button>
    ${o.status === "ABERTO" && !o.vencido ? `<button id="conv" class="primario">Transformar em venda</button>` : ""}
    ${o.status === "ABERTO" ? `<button id="canc" class="perigo">Cancelar orçamento</button>` : ""}</div>`);
  $("#imp", c).onclick = () => imprimir(reciboOrcamento(o));
  if ($("#canc", c)) $("#canc", c).onclick = async () => {
    try { await POST(`/api/orcamentos/${o.id}/cancelar`); avisar("Orçamento cancelado"); fecharModal(); renderizar(); } catch (e) { erro(e); }
  };
  if ($("#conv", c)) $("#conv", c).onclick = async () => {
    const c2 = abrirModal(`Venda do orçamento nº ${o.id} — ${R(o.total)}`, `<label>Cliente<span id="cli"></span></label>
      <h2 style="margin-top:12px">Pagamento</h2><div id="pg"></div><p><button class="primario" id="ok">Finalizar venda</button></p>`, "520px");
    $("#cli", c2).innerHTML = await selectClientes(o.cliente_id);
    const pag = widgetPagamentos($("#pg", c2), () => o.total);
    $("#ok", c2).onclick = async () => {
      try {
        const venda = await POST(`/api/orcamentos/${o.id}/converter`, { cliente_id: $("#cli select", c2).value, ...pag.dados() });
        const c3 = abrirModal(`Venda nº ${venda.id} concluída`, `<div class="total-grande">${R(venda.total)}</div>
          ${venda.troco ? `<p style="font-size:22px">Troco: <b>${R(venda.troco)}</b></p>` : ""}<button class="primario" id="imp">Imprimir comprovante</button>`, "420px");
        $("#imp", c3).onclick = () => imprimir(reciboVenda(venda));
        renderizar(); atualizarStatusCaixa();
      } catch (e) { erro(e); }
    };
  };
}

// --------------------------------------------------------------- produtos
const filtroProd = { busca: "", categoria: "", baixo: false };
paginas.produtos = async (el) => {
  const [lista, cats] = await Promise.all([
    GET(`/api/produtos?busca=${encodeURIComponent(filtroProd.busca)}&categoria=${encodeURIComponent(filtroProd.categoria)}&estoque_baixo=${filtroProd.baixo ? 1 : 0}`),
    GET("/api/produtos/categorias")]);
  el.innerHTML = `<h1>Produtos</h1>
    <form class="barra" id="filtro"><label>Buscar<input name="busca" value="${esc(filtroProd.busca)}" placeholder="nome ou código"></label>
      <label>Categoria<select name="categoria"><option value="">Todas</option>${opcoes(cats.map((c) => [c, c]), filtroProd.categoria)}</select></label>
      <label style="flex-direction:row;align-items:center"><input type="checkbox" name="baixo" ${filtroProd.baixo ? "checked" : ""}> Só estoque baixo</label>
      <button type="submit">Filtrar</button><button type="button" class="primario" id="novo">+ Novo produto</button></form>
    <div class="tabela"><table><tr><th>Código</th><th>Produto</th><th>Categoria</th><th class="num">Custo</th><th class="num">Venda</th><th class="num">Margem</th><th class="num">Estoque</th><th></th></tr>
    ${lista.map((p) => `<tr class="${p.ativo ? "" : "inativo"}"><td>${esc(p.codigo)}${p.codigo_barras ? `<div class="suave">${esc(p.codigo_barras)}</div>` : ""}</td>
      <td>${esc(p.nome)}${p.ativo ? "" : " (inativo)"}${p.localizacao ? `<div class="suave">${esc(p.localizacao)}</div>` : ""}</td><td>${esc(p.categoria)}</td>
      <td class="num">${R(p.preco_custo)}</td><td class="num">${R(p.preco_venda)}</td>
      <td class="num">${p.preco_custo ? (((p.preco_venda - p.preco_custo) / p.preco_custo) * 100).toFixed(1).replace(".", ",") + "%" : "—"}</td>
      <td class="num ${p.estoque <= p.estoque_minimo ? "texto-erro" : ""}">${Q(p.estoque)} ${p.unidade}<div class="suave">mín. ${Q(p.estoque_minimo)}</div></td>
      <td><div class="acoes"><button class="pequeno ed" data-id="${p.id}">Editar</button><button class="pequeno aj" data-id="${p.id}">Inventário</button>
      <button class="pequeno pe" data-id="${p.id}">Perda</button><a class="pequeno" href="#movimentos/${p.id}">Histórico</a></div></td></tr>`).join("") ||
      `<tr><td colspan="8" class="suave">Nenhum produto.</td></tr>`}</table></div>`;
  $("#filtro").onsubmit = (e) => { e.preventDefault(); const d = dadosForm(e.target); Object.assign(filtroProd, d); renderizar(); };
  $("#novo").onclick = () => formProduto(null, cats).catch(erro);
  const porId = Object.fromEntries(lista.map((p) => [p.id, p]));
  $$(".ed").forEach((b) => (b.onclick = () => formProduto(porId[b.dataset.id], cats).catch(erro)));
  $$(".aj").forEach((b) => (b.onclick = () => {
    const p = porId[b.dataset.id];
    const c = abrirModal(`Inventário — ${p.nome}`, `<form><p>Estoque no sistema: <b>${Q(p.estoque)} ${p.unidade}</b></p>
      <div class="grade"><label>Quantidade contada<input name="quantidade" required inputmode="decimal"></label><label>Motivo<input name="motivo" required value="Contagem de inventário"></label></div>
      <p><button class="primario" type="submit">Ajustar estoque</button></p></form>`, "520px");
    aoEnviar($("form", c), (d) => POST(`/api/produtos/${p.id}/ajuste`, d), "Estoque ajustado");
  }));
  $$(".pe").forEach((b) => (b.onclick = () => {
    const p = porId[b.dataset.id];
    const c = abrirModal(`Registrar perda — ${p.nome}`, `<form><p>Estoque atual: <b>${Q(p.estoque)} ${p.unidade}</b></p>
      <div class="grade"><label>Quantidade perdida<input name="quantidade" required inputmode="decimal"></label><label>Motivo<input name="motivo" required placeholder="quebra, avaria, vencido..."></label></div>
      <p><button class="primario" type="submit">Registrar perda</button></p></form>`, "520px");
    aoEnviar($("form", c), (d) => POST(`/api/produtos/${p.id}/perda`, d), "Perda registrada");
  }));
};

async function formProduto(p, cats) {
  const fornecedores = await GET("/api/fornecedores?ativos=1");
  const novo = !p;
  p = p || { unidade: "UN", ativo: 1 };
  const c = abrirModal(novo ? "Novo produto" : `Editar — ${p.nome}`, `<form class="grade">
    <label>Código interno<input name="codigo" value="${esc(p.codigo)}" placeholder="automático"></label>
    <label>Código de barras<input name="codigo_barras" value="${esc(p.codigo_barras)}"></label>
    <label class="largo">Nome / descrição<input name="nome" required value="${esc(p.nome)}"></label>
    <label>Categoria<input name="categoria" list="cats" value="${esc(p.categoria)}"><datalist id="cats">${cats.map((x) => `<option value="${esc(x)}">`).join("")}</datalist></label>
    <label>Unidade<select name="unidade">${opcoes(Object.entries(CONFIG.unidades).map(([k, n]) => [k, `${k} — ${n}`]), p.unidade)}</select></label>
    <label>Preço de custo (R$)<input name="preco_custo" value="${p.preco_custo != null ? paraCampo(p.preco_custo) : ""}" inputmode="decimal"></label>
    <label>Preço de venda (R$)<input name="preco_venda" required value="${p.preco_venda != null ? paraCampo(p.preco_venda) : ""}" inputmode="decimal"></label>
    <label>Margem desejada (%) <input id="margem" inputmode="decimal" placeholder="calcula a venda"></label>
    <label>Estoque mínimo<input name="estoque_minimo" value="${p.estoque_minimo != null ? qtdCampo(p.estoque_minimo) : "0"}" inputmode="decimal"></label>
    ${novo ? `<label>Estoque inicial<input name="estoque_inicial" value="0" inputmode="decimal"></label>` : ""}
    <label>Localização (corredor/prateleira)<input name="localizacao" value="${esc(p.localizacao)}"></label>
    <label>Fornecedor principal<select name="fornecedor_id"><option value="">—</option>${opcoes(fornecedores.map((f) => [f.id, f.nome]), p.fornecedor_id)}</select></label>
    ${novo ? "" : `<label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="ativo" ${p.ativo ? "checked" : ""}> Ativo</label>`}
    <div class="largo"><button class="primario" type="submit">Salvar</button></div></form>`);
  $("#margem", c).oninput = (e) => {
    const custo = centavos($("[name=preco_custo]", c).value);
    const m = Number(e.target.value.replace(",", "."));
    if (custo > 0 && Number.isFinite(m)) $("[name=preco_venda]", c).value = paraCampo(Math.round(custo * (1 + m / 100)));
  };
  aoEnviar($("form", c), (d) => (novo ? POST("/api/produtos", d) : PUT(`/api/produtos/${p.id}`, d)), "Produto salvo");
}

// ---------------------------------------------------------- movimentações
paginas.movimentos = async (el, pid) => {
  const [lista, produtos] = await Promise.all([GET("/api/movimentos" + (pid ? `?produto_id=${pid}` : "")), GET("/api/produtos")]);
  el.innerHTML = `<h1>Movimentações de estoque</h1>
    <div class="barra"><label>Produto<select id="prod"><option value="">Todos (últimos 300)</option>${opcoes(produtos.map((p) => [p.id, `${p.codigo} — ${p.nome}`]), pid)}</select></label></div>
    <div class="tabela"><table><tr><th>Data</th><th>Produto</th><th>Tipo</th><th class="num">Quantidade</th><th class="num">Saldo</th><th>Referência</th><th>Observação</th></tr>
    ${lista.map((m) => `<tr><td>${dataBR(m.data)}</td><td>${esc(m.codigo)} — ${esc(m.produto)}</td><td>${esc(m.tipo.replace(/_/g, " "))}</td>
      <td class="num ${m.quantidade < 0 ? "texto-erro" : "texto-ok"}">${m.quantidade > 0 ? "+" : ""}${Q(m.quantidade)} ${m.unidade}</td>
      <td class="num">${Q(m.saldo_apos)}</td><td>${esc(m.referencia)}</td><td>${esc(m.observacao)}</td></tr>`).join("") || `<tr><td colspan="7" class="suave">Sem movimentações.</td></tr>`}</table></div>`;
  $("#prod").onchange = (e) => (location.hash = "movimentos" + (e.target.value ? "/" + e.target.value : ""));
};

// ---------------------------------------------------------------- compras
paginas.compras = async (el) => {
  const [lista, fornecedores, produtos] = await Promise.all([GET("/api/compras"), GET("/api/fornecedores?ativos=1"), GET("/api/produtos?ativos=1")]);
  el.innerHTML = `<h1>Entrada de mercadoria (compras)</h1>
    <div class="cartao"><h2>Nova entrada</h2>
    ${fornecedores.length ? `<form id="compra">
      <div class="grade"><label>Fornecedor<select name="fornecedor_id" required>${opcoes(fornecedores.map((f) => [f.id, f.nome]))}</select></label>
        <label>Nota fiscal<input name="nota_fiscal"></label>
        <label>Parcelas a pagar<input name="parcelas" type="number" value="1" min="1" max="24"></label>
        <label>1º vencimento<input name="primeiro_vencimento" type="date"></label></div>
      <datalist id="lista-prod">${produtos.map((p) => `<option value="${esc(p.codigo)} — ${esc(p.nome)}">`).join("")}</datalist>
      <div class="tabela" style="margin-top:10px"><table><thead><tr><th>Produto</th><th class="num">Quantidade</th><th class="num">Custo unitário (R$)</th><th class="num">Total</th><th></th></tr></thead><tbody id="linhas"></tbody></table></div>
      <div class="acoes" style="margin-top:10px"><button type="button" id="mais">+ Item</button><span id="total-compra" class="suave"></span>
        <button type="submit" class="primario">Lançar entrada</button></div>
      <p class="suave">O estoque é somado, o custo médio do produto é recalculado e as parcelas vão para Contas a pagar.</p></form>`
      : `<p>Cadastre um <a href="#fornecedores">fornecedor</a> antes de lançar compras.</p>`}</div>
    <h2>Últimas entradas</h2>
    <div class="tabela"><table><tr><th>Nº</th><th>Data</th><th>Fornecedor</th><th>NF</th><th class="num">Total</th><th></th></tr>
    ${lista.map((c) => `<tr><td>${c.id}</td><td>${dataBR(c.data)}</td><td>${esc(c.fornecedor)}</td><td>${esc(c.nota_fiscal)}</td><td class="num">${R(c.total)}</td>
      <td><button class="pequeno ver" data-id="${c.id}">Ver</button></td></tr>`).join("") || `<tr><td colspan="6" class="suave">Nenhuma compra.</td></tr>`}</table></div>`;
  $$(".ver").forEach((b) => (b.onclick = async () => {
    const c = await GET("/api/compras/" + b.dataset.id).catch(erro);
    if (!c) return;
    abrirModal(`Compra nº ${c.id} — ${c.fornecedor}`, `<div class="tabela"><table><tr><th>Produto</th><th class="num">Qtd</th><th class="num">Custo</th><th class="num">Total</th></tr>
      ${c.itens.map((i) => `<tr><td>${esc(i.produto)}</td><td class="num">${Q(i.quantidade)} ${i.unidade}</td><td class="num">${R(i.custo_unitario)}</td><td class="num">${R(i.total)}</td></tr>`).join("")}</table></div>
      <p><b>Total ${R(c.total)}</b></p><p>Parcelas: ${c.contas.map((p) => `${p.parcela}/${p.total_parcelas} venc. ${dataBR(p.vencimento)} ${R(p.valor)} (${p.status})`).join(" · ")}</p>`);
  }));
  if (!fornecedores.length) return;
  const porCodigo = Object.fromEntries(produtos.map((p) => [p.codigo, p]));
  const linhas = [{ prod: "", qtd: "", custo: "" }];
  const valorLinha = (l) => Math.round((centavos(l.custo) || 0) * (milesimos(l.qtd) || 0) / 1000);
  function desenhar() {
    $("#linhas").innerHTML = linhas.map((l, i) => `<tr>
      <td><input class="cp-prod" data-i="${i}" list="lista-prod" value="${esc(l.prod)}" style="width:100%" placeholder="digite o código ou nome"></td>
      <td class="num"><input class="cp-qtd" data-i="${i}" value="${esc(l.qtd)}" style="width:90px;text-align:right" inputmode="decimal"></td>
      <td class="num"><input class="cp-custo" data-i="${i}" value="${esc(l.custo)}" style="width:110px;text-align:right" inputmode="decimal"></td>
      <td class="num tl">${R(valorLinha(l))}</td>
      <td><button type="button" class="pequeno perigo rm" data-i="${i}">✕</button></td></tr>`).join("");
    const atualizar = (x) => {
      $(".tl", x.closest("tr")).textContent = R(valorLinha(linhas[x.dataset.i]));
      $("#total-compra").textContent = "Total: " + R(linhas.reduce((s, l) => s + valorLinha(l), 0));
    };
    $$(".cp-prod").forEach((x) => (x.oninput = () => {
      const l = linhas[x.dataset.i]; l.prod = x.value;
      const p = porCodigo[x.value.split(" — ")[0]];
      const campoCusto = $(".cp-custo", x.closest("tr"));
      if (p && !l.custo) campoCusto.value = l.custo = paraCampo(p.preco_custo);
      atualizar(x);
    }));
    $$(".cp-qtd").forEach((x) => (x.oninput = () => { linhas[x.dataset.i].qtd = x.value; atualizar(x); }));
    $$(".cp-custo").forEach((x) => (x.oninput = () => { linhas[x.dataset.i].custo = x.value; atualizar(x); }));
    $("#total-compra").textContent = "Total: " + R(linhas.reduce((s, l) => s + valorLinha(l), 0));
    $$(".rm").forEach((x) => (x.onclick = () => { linhas.splice(x.dataset.i, 1); if (!linhas.length) linhas.push({ prod: "", qtd: "", custo: "" }); desenhar(); }));
  }
  $("#mais").onclick = () => { linhas.push({ prod: "", qtd: "", custo: "" }); desenhar(); };
  $("#compra").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const itens = linhas.filter((l) => l.prod.trim()).map((l) => {
        const p = porCodigo[l.prod.split(" — ")[0]];
        if (!p) throw new Error(`Produto não encontrado: ${l.prod}`);
        return { produto_id: p.id, quantidade: l.qtd, custo_unitario: l.custo };
      });
      const c = await POST("/api/compras", { ...dadosForm(e.target), itens });
      avisar(`Entrada nº ${c.id} lançada: ${R(c.total)}`);
      renderizar();
    } catch (err) { erro(err); }
  };
  desenhar();
};

// --------------------------------------------------------------- clientes
let buscaCliente = "";
paginas.clientes = async (el) => {
  const lista = await GET("/api/clientes?busca=" + encodeURIComponent(buscaCliente));
  el.innerHTML = `<h1>Clientes</h1>
    <form class="barra" id="filtro"><label>Buscar<input name="busca" value="${esc(buscaCliente)}" placeholder="nome, CPF/CNPJ ou telefone"></label>
      <button type="submit">Buscar</button><button type="button" class="primario" id="novo">+ Novo cliente</button></form>
    <div class="tabela"><table><tr><th>Nome</th><th>CPF/CNPJ</th><th>Telefone</th><th class="num">Limite crediário</th><th class="num">Deve</th><th></th></tr>
    ${lista.map((c) => `<tr class="${c.ativo ? "" : "inativo"}"><td>${esc(c.nome)}</td><td>${esc(c.documento)}</td><td>${esc(c.telefone)}</td>
      <td class="num">${R(c.limite_credito)}</td><td class="num ${c.saldo_devedor ? "texto-erro" : ""}">${R(c.saldo_devedor)}</td>
      <td><div class="acoes"><button class="pequeno ex" data-id="${c.id}">Extrato / receber</button><button class="pequeno ed" data-id="${c.id}">Editar</button></div></td></tr>`).join("") ||
      `<tr><td colspan="6" class="suave">Nenhum cliente.</td></tr>`}</table></div>`;
  $("#filtro").onsubmit = (e) => { e.preventDefault(); buscaCliente = dadosForm(e.target).busca; renderizar(); };
  const porId = Object.fromEntries(lista.map((c) => [c.id, c]));
  $("#novo").onclick = () => formCliente(null);
  $$(".ed").forEach((b) => (b.onclick = () => formCliente(porId[b.dataset.id])));
  $$(".ex").forEach((b) => (b.onclick = () => extratoCliente(b.dataset.id).catch(erro)));
};

function formCliente(c) {
  const novo = !c;
  c = c || { ativo: 1 };
  const m = abrirModal(novo ? "Novo cliente" : `Editar — ${c.nome}`, `<form class="grade">
    <label class="largo">Nome<input name="nome" required value="${esc(c.nome)}"></label>
    <label>CPF/CNPJ<input name="documento" value="${esc(c.documento)}"></label>
    <label>Telefone<input name="telefone" value="${esc(c.telefone)}"></label>
    <label>E-mail<input name="email" value="${esc(c.email)}"></label>
    <label>Limite de crediário (R$)<input name="limite_credito" value="${paraCampo(c.limite_credito)}" inputmode="decimal"></label>
    <label class="largo">Endereço<input name="endereco" value="${esc(c.endereco)}"></label>
    ${novo ? "" : `<label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="ativo" ${c.ativo ? "checked" : ""}> Ativo</label>`}
    <div class="largo"><button class="primario" type="submit">Salvar</button></div></form>`);
  aoEnviar($("form", m), (d) => (novo ? POST("/api/clientes", d) : PUT(`/api/clientes/${c.id}`, d)), "Cliente salvo");
}

async function extratoCliente(id) {
  const c = await GET("/api/clientes/" + id);
  const abertas = c.parcelas.filter((p) => p.status === "ABERTA");
  const m = abrirModal(`Extrato — ${c.nome}`, `
    <div class="indicadores">
      <div class="indicador"><div class="rotulo">Deve</div><div class="valor">${R(c.saldo_devedor)}</div></div>
      <div class="indicador"><div class="rotulo">Vencido</div><div class="valor ${c.valor_vencido ? "texto-erro" : ""}">${R(c.valor_vencido)}</div></div>
      <div class="indicador"><div class="rotulo">Crédito disponível</div><div class="valor">${R(c.credito_disponivel)}</div></div></div>
    ${c.saldo_devedor ? `<form class="barra" id="receber"><label>Receber valor (quita as parcelas mais antigas)<input name="valor" required value="${paraCampo(c.saldo_devedor)}" inputmode="decimal"></label>
      <label>Forma<select name="forma">${opcoes((CONFIG.formas_recebimento || []).map((f) => [f, forma(f)]))}</select></label><button class="primario" type="submit">Receber</button></form>` : ""}
    <h2>Parcelas em aberto</h2>
    <div class="tabela"><table><tr><th>Venda</th><th>Parcela</th><th>Vencimento</th><th class="num">Valor</th><th class="num">Pago</th><th class="num">Resta</th></tr>
    ${abertas.map((p) => `<tr><td>${p.venda_id}</td><td>${p.parcela}/${p.total_parcelas}</td><td class="${p.vencida ? "texto-erro" : ""}">${dataBR(p.vencimento)}</td>
      <td class="num">${R(p.valor)}</td><td class="num">${R(p.valor_pago)}</td><td class="num">${R(p.restante)}</td></tr>`).join("") || `<tr><td colspan="6" class="suave">Nada em aberto.</td></tr>`}</table></div>
    <h2 style="margin-top:12px">Pagamentos recebidos</h2>
    <div class="tabela"><table><tr><th>Data</th><th>Venda</th><th>Parcela</th><th>Forma</th><th class="num">Valor</th></tr>
    ${c.recebimentos.map((r) => `<tr><td>${dataBR(r.data)}</td><td>${r.venda_id}</td><td>${r.parcela}/${r.total_parcelas}</td><td>${forma(r.forma)}</td><td class="num">${R(r.valor)}</td></tr>`).join("") || `<tr><td colspan="5" class="suave">Nenhum.</td></tr>`}</table></div>
    <h2 style="margin-top:12px">Compras</h2>
    <p>${c.vendas.map((v) => `nº ${v.id} (${dataBR(v.data)}) ${R(v.total)} ${v.status === "CANCELADA" ? "— cancelada" : ""}`).join("<br>") || "Nenhuma."}</p>`, "860px");
  const f = $("#receber", m);
  if (f) f.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await POST(`/api/clientes/${id}/receber`, dadosForm(f));
      avisar(`Recebido ${R(r.recebido)}. Saldo restante: ${R(r.cliente.saldo_devedor)}`);
      atualizarStatusCaixa();
      extratoCliente(id);
    } catch (err) { erro(err); }
  };
}

// ----------------------------------------------------------- fornecedores
paginas.fornecedores = async (el) => {
  const lista = await GET("/api/fornecedores");
  el.innerHTML = `<h1>Fornecedores</h1><p><button class="primario" id="novo">+ Novo fornecedor</button></p>
    <div class="tabela"><table><tr><th>Nome</th><th>CPF/CNPJ</th><th>Telefone</th><th>E-mail</th><th></th></tr>
    ${lista.map((f) => `<tr class="${f.ativo ? "" : "inativo"}"><td>${esc(f.nome)}</td><td>${esc(f.documento)}</td><td>${esc(f.telefone)}</td><td>${esc(f.email)}</td>
      <td><button class="pequeno ed" data-id="${f.id}">Editar</button></td></tr>`).join("") || `<tr><td colspan="5" class="suave">Nenhum fornecedor.</td></tr>`}</table></div>`;
  const porId = Object.fromEntries(lista.map((f) => [f.id, f]));
  const form = (f) => {
    const novo = !f; f = f || { ativo: 1 };
    const m = abrirModal(novo ? "Novo fornecedor" : `Editar — ${f.nome}`, `<form class="grade">
      <label class="largo">Nome / razão social<input name="nome" required value="${esc(f.nome)}"></label>
      <label>CPF/CNPJ<input name="documento" value="${esc(f.documento)}"></label><label>Telefone<input name="telefone" value="${esc(f.telefone)}"></label>
      <label>E-mail<input name="email" value="${esc(f.email)}"></label><label class="largo">Endereço<input name="endereco" value="${esc(f.endereco)}"></label>
      ${novo ? "" : `<label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="ativo" ${f.ativo ? "checked" : ""}> Ativo</label>`}
      <div class="largo"><button class="primario" type="submit">Salvar</button></div></form>`);
    aoEnviar($("form", m), (d) => (novo ? POST("/api/fornecedores", d) : PUT(`/api/fornecedores/${f.id}`, d)), "Fornecedor salvo");
  };
  $("#novo").onclick = () => form(null);
  $$(".ed").forEach((b) => (b.onclick = () => form(porId[b.dataset.id])));
};

// ------------------------------------------------------ contas a receber
const filtroReceber = { status: "ABERTA", vencidas: false };
paginas.receber = async (el) => {
  const lista = await GET(`/api/contas-receber?status=${filtroReceber.status}&vencidas=${filtroReceber.vencidas ? 1 : 0}`);
  const soma = lista.reduce((s, c) => s + (c.status === "ABERTA" ? c.restante : 0), 0);
  el.innerHTML = `<h1>Contas a receber (crediário)</h1>
    <form class="barra" id="filtro"><label>Situação<select name="status">${opcoes([["ABERTA", "Em aberto"], ["PAGA", "Pagas"], ["CANCELADA", "Canceladas"], ["", "Todas"]], filtroReceber.status)}</select></label>
      <label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="vencidas" ${filtroReceber.vencidas ? "checked" : ""}> Só vencidas</label>
      <button type="submit">Filtrar</button><span class="suave">Em aberto na lista: <b>${R(soma)}</b></span></form>
    <div class="tabela"><table><tr><th>Cliente</th><th>Venda</th><th>Parcela</th><th>Vencimento</th><th class="num">Valor</th><th class="num">Pago</th><th class="num">Resta</th><th>Status</th><th></th></tr>
    ${lista.map((c) => `<tr><td>${esc(c.cliente)}</td><td>${c.venda_id ?? ""}</td><td>${c.parcela}/${c.total_parcelas}</td>
      <td class="${c.vencida ? "texto-erro" : ""}">${dataBR(c.vencimento)}${c.vencida ? " (vencida)" : ""}</td>
      <td class="num">${R(c.valor)}</td><td class="num">${R(c.valor_pago)}</td><td class="num">${R(c.restante)}</td><td>${etiquetaStatus(c.status)}</td>
      <td>${c.status === "ABERTA" ? `<button class="pequeno primario rec" data-id="${c.id}">Receber</button>` : ""}</td></tr>`).join("") ||
      `<tr><td colspan="9" class="suave">Nenhuma conta.</td></tr>`}</table></div>`;
  $("#filtro").onsubmit = (e) => { e.preventDefault(); Object.assign(filtroReceber, dadosForm(e.target)); renderizar(); };
  const porId = Object.fromEntries(lista.map((c) => [c.id, c]));
  $$(".rec").forEach((b) => (b.onclick = () => {
    const conta = porId[b.dataset.id];
    const m = abrirModal(`Receber parcela ${conta.parcela}/${conta.total_parcelas} — ${conta.cliente}`, `<form class="grade">
      <label>Valor (aceita pagamento parcial)<input name="valor" required value="${paraCampo(conta.restante)}" inputmode="decimal"></label>
      <label>Forma<select name="forma">${opcoes((CONFIG.formas_recebimento || []).map((f) => [f, forma(f)]))}</select></label>
      <div class="largo"><button class="primario" type="submit">Confirmar recebimento</button></div></form>`, "520px");
    aoEnviar($("form", m), (d) => POST(`/api/contas-receber/${conta.id}/receber`, d).then((r) => { atualizarStatusCaixa(); return r; }), "Recebimento registrado");
  }));
};

// -------------------------------------------------------- contas a pagar
const filtroPagar = { status: "ABERTA", vencidas: false };
paginas.pagar = async (el) => {
  const [lista, fornecedores] = await Promise.all([GET(`/api/contas-pagar?status=${filtroPagar.status}&vencidas=${filtroPagar.vencidas ? 1 : 0}`), GET("/api/fornecedores")]);
  const soma = lista.reduce((s, c) => s + (c.status === "ABERTA" ? c.restante : 0), 0);
  el.innerHTML = `<h1>Contas a pagar</h1>
    <form class="barra" id="filtro"><label>Situação<select name="status">${opcoes([["ABERTA", "Em aberto"], ["PAGA", "Pagas"], ["CANCELADA", "Canceladas"], ["", "Todas"]], filtroPagar.status)}</select></label>
      <label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" name="vencidas" ${filtroPagar.vencidas ? "checked" : ""}> Só vencidas</label>
      <button type="submit">Filtrar</button><button type="button" class="primario" id="nova">+ Lançar conta</button><span class="suave">Em aberto na lista: <b>${R(soma)}</b></span></form>
    <div class="tabela"><table><tr><th>Descrição</th><th>Fornecedor</th><th>Parcela</th><th>Vencimento</th><th class="num">Valor</th><th class="num">Pago</th><th class="num">Resta</th><th>Status</th><th></th></tr>
    ${lista.map((c) => `<tr><td>${esc(c.descricao)}</td><td>${esc(c.fornecedor || "")}</td><td>${c.parcela}/${c.total_parcelas}</td>
      <td class="${c.vencida ? "texto-erro" : ""}">${dataBR(c.vencimento)}${c.vencida ? " (vencida)" : ""}</td>
      <td class="num">${R(c.valor)}</td><td class="num">${R(c.valor_pago)}</td><td class="num">${R(c.restante)}</td><td>${etiquetaStatus(c.status)}</td>
      <td>${c.status === "ABERTA" ? `<div class="acoes"><button class="pequeno primario pg" data-id="${c.id}">Pagar</button>${c.valor_pago ? "" : `<button class="pequeno perigo cc" data-id="${c.id}">Cancelar</button>`}</div>` : ""}</td></tr>`).join("") ||
      `<tr><td colspan="9" class="suave">Nenhuma conta.</td></tr>`}</table></div>`;
  $("#filtro").onsubmit = (e) => { e.preventDefault(); Object.assign(filtroPagar, dadosForm(e.target)); renderizar(); };
  $("#nova").onclick = () => {
    const m = abrirModal("Lançar conta a pagar", `<form class="grade">
      <label class="largo">Descrição<input name="descricao" required placeholder="aluguel, energia, frete..."></label>
      <label>Valor (R$)<input name="valor" required inputmode="decimal"></label><label>Vencimento<input name="vencimento" type="date" required value="${CONFIG.hoje}"></label>
      <label>Fornecedor<select name="fornecedor_id"><option value="">—</option>${opcoes(fornecedores.map((f) => [f.id, f.nome]))}</select></label>
      <div class="largo"><button class="primario" type="submit">Lançar</button></div></form>`, "560px");
    aoEnviar($("form", m), (d) => POST("/api/contas-pagar", d), "Conta lançada");
  };
  const porId = Object.fromEntries(lista.map((c) => [c.id, c]));
  $$(".pg").forEach((b) => (b.onclick = () => {
    const conta = porId[b.dataset.id];
    const m = abrirModal(`Pagar — ${conta.descricao}`, `<form class="grade">
      <label>Valor<input name="valor" required value="${paraCampo(conta.restante)}" inputmode="decimal"></label>
      <label>Forma<select name="forma">${opcoes((CONFIG.formas_pagamento_conta || []).map((f) => [f, forma(f)]), "PIX")}</select></label>
      <p class="largo suave">"Dinheiro do caixa" retira o valor da gaveta do caixa aberto.</p>
      <div class="largo"><button class="primario" type="submit">Confirmar pagamento</button></div></form>`, "520px");
    aoEnviar($("form", m), (d) => POST(`/api/contas-pagar/${conta.id}/pagar`, d), "Pagamento registrado");
  }));
  $$(".cc").forEach((b) => (b.onclick = async () => {
    if (!confirm("Cancelar esta conta?")) return;
    try { await POST(`/api/contas-pagar/${b.dataset.id}/cancelar`); avisar("Conta cancelada"); renderizar(); } catch (e) { erro(e); }
  }));
};

// ------------------------------------------------------------------ caixa
function tabelaCaixa(s) {
  return `<div class="tabela"><table><tr><th>Hora</th><th>Tipo</th><th>Forma</th><th>Descrição</th><th class="num">Valor</th></tr>
    <tr><td>${dataBR(s.abertura)}</td><td>ABERTURA</td><td>Dinheiro</td><td>Fundo de troco</td><td class="num">${R(s.valor_inicial)}</td></tr>
    ${s.movimentos.map((m) => `<tr><td>${dataBR(m.data)}</td><td>${esc(m.tipo.replace(/_/g, " "))}</td><td>${forma(m.forma)}</td><td>${esc(m.descricao)}</td>
      <td class="num ${m.valor < 0 ? "texto-erro" : ""}">${R(m.valor)}</td></tr>`).join("")}</table></div>`;
}
function totaisCaixa(s) {
  return `<div class="indicadores"><div class="indicador"><div class="rotulo">Dinheiro na gaveta</div><div class="valor">${R(s.saldo_dinheiro)}</div></div>
    ${Object.entries(s.totais_por_forma).filter(([f]) => f !== "DINHEIRO").map(([f, val]) => `<div class="indicador"><div class="rotulo">${forma(f)}</div><div class="valor">${R(val)}</div></div>`).join("")}</div>`;
}
paginas.caixa = async (el) => {
  const { caixa, sessoes } = await GET("/api/caixa");
  el.innerHTML = `<h1>Caixa</h1>
    ${caixa ? `<div class="cartao"><h2>Caixa aberto desde ${dataBR(caixa.abertura)} ${caixa.operador ? "— " + esc(caixa.operador) : ""}</h2>${totaisCaixa(caixa)}
      <div class="acoes"><button id="sangria">Sangria (retirada)</button><button id="suprimento">Suprimento (reforço)</button><button id="fechar" class="primario">Fechar caixa</button></div></div>
      <h2>Movimentos deste caixa</h2>${tabelaCaixa(caixa)}`
    : `<div class="cartao"><h2>Caixa fechado</h2><form class="barra" id="abrir"><label>Fundo de troco (R$)<input name="valor_inicial" value="0,00" inputmode="decimal"></label>
      <label>Operador<input name="operador"></label><button class="primario" type="submit">Abrir caixa</button></form></div>`}
    <h2 style="margin-top:16px">Caixas anteriores</h2>
    <div class="tabela"><table><tr><th>Nº</th><th>Abertura</th><th>Fechamento</th><th>Operador</th><th class="num">Esperado</th><th class="num">Contado</th><th class="num">Diferença</th><th></th></tr>
    ${sessoes.filter((s) => s.status === "FECHADO").map((s) => `<tr><td>${s.id}</td><td>${dataBR(s.abertura)}</td><td>${dataBR(s.fechamento)}</td><td>${esc(s.operador)}</td>
      <td class="num">${R(s.valor_esperado)}</td><td class="num">${R(s.valor_contado)}</td>
      <td class="num ${s.diferenca ? "texto-erro" : "texto-ok"}">${R(s.diferenca)}</td><td><button class="pequeno ver" data-id="${s.id}">Ver</button></td></tr>`).join("") ||
      `<tr><td colspan="8" class="suave">Nenhum.</td></tr>`}</table></div>`;
  $$(".ver").forEach((b) => (b.onclick = async () => {
    const s = await GET("/api/caixa/" + b.dataset.id).catch(erro);
    if (s) abrirModal(`Caixa nº ${s.id}`, totaisCaixa(s) + tabelaCaixa(s), "900px");
  }));
  if (!caixa) {
    $("#abrir").onsubmit = async (e) => {
      e.preventDefault();
      try { await POST("/api/caixa/abrir", dadosForm(e.target)); avisar("Caixa aberto"); atualizarStatusCaixa(); renderizar(); } catch (err) { erro(err); }
    };
    return;
  }
  const mov = (tipo, titulo) => () => {
    const m = abrirModal(titulo, `<form class="grade"><label>Valor (R$)<input name="valor" required inputmode="decimal"></label><label>Motivo<input name="motivo"></label>
      <div class="largo"><button class="primario" type="submit">Confirmar</button></div></form>`, "480px");
    aoEnviar($("form", m), (d) => POST("/api/caixa/" + tipo, d).then((r) => { atualizarStatusCaixa(); return r; }), "Lançado");
  };
  $("#sangria").onclick = mov("sangria", "Sangria — retirada de dinheiro");
  $("#suprimento").onclick = mov("suprimento", "Suprimento — reforço de troco");
  $("#fechar").onclick = () => {
    const m = abrirModal("Fechar caixa", `<form class="grade"><p class="largo">Conte o dinheiro da gaveta e informe o valor.</p>
      <label>Dinheiro contado (R$)<input name="valor_contado" required inputmode="decimal"></label><label>Observação<input name="observacao"></label>
      <div class="largo"><button class="primario" type="submit">Fechar caixa</button></div></form>`, "480px");
    $("form", m).onsubmit = async (e) => {
      e.preventDefault();
      try {
        const s = await POST("/api/caixa/fechar", dadosForm(e.target));
        atualizarStatusCaixa(); renderizar();
        abrirModal("Caixa fechado", `<p>Esperado: <b>${R(s.valor_esperado)}</b> · Contado: <b>${R(s.valor_contado)}</b></p>
          <p class="${s.diferenca ? "texto-erro" : "texto-ok"}" style="font-size:20px">${s.diferenca === 0 ? "Caixa conferido, sem diferença." : s.diferenca > 0 ? `Sobra de ${R(s.diferenca)}` : `Falta de ${R(-s.diferenca)}`}</p>`, "480px");
      } catch (err) { erro(err); }
    };
  };
};

// ------------------------------------------------------------- relatórios
const filtroRel = { inicio: "", fim: "" };
paginas.relatorios = async (el) => {
  if (!filtroRel.inicio) { filtroRel.inicio = CONFIG.hoje.slice(0, 8) + "01"; filtroRel.fim = CONFIG.hoje; }
  const q = `inicio=${filtroRel.inicio}&fim=${filtroRel.fim}`;
  const [r, mais, est] = await Promise.all([GET("/api/relatorios/vendas?" + q), GET("/api/relatorios/mais-vendidos?" + q), GET("/api/relatorios/estoque")]);
  el.innerHTML = `<h1>Relatórios</h1>
    <form class="barra" id="filtro"><label>De<input type="date" name="inicio" value="${filtroRel.inicio}"></label><label>Até<input type="date" name="fim" value="${filtroRel.fim}"></label>
      <button type="submit">Gerar</button></form>
    <div class="indicadores">
      <div class="indicador"><div class="rotulo">Vendas</div><div class="valor">${r.quantidade}</div><div class="suave">${r.canceladas} cancelada(s)</div></div>
      <div class="indicador"><div class="rotulo">Valor bruto</div><div class="valor">${R(r.bruto)}</div></div>
      <div class="indicador"><div class="rotulo">Descontos</div><div class="valor">${R(r.descontos)}</div></div>
      <div class="indicador"><div class="rotulo">Devoluções</div><div class="valor">${R(r.devolucoes)}</div></div>
      <div class="indicador"><div class="rotulo">Faturamento líquido</div><div class="valor">${R(r.liquido)}</div></div>
      <div class="indicador"><div class="rotulo">Custo das mercadorias</div><div class="valor">${R(r.custo_mercadorias)}</div></div>
      <div class="indicador"><div class="rotulo">Lucro bruto</div><div class="valor ${r.lucro_bruto < 0 ? "texto-erro" : "texto-ok"}">${R(r.lucro_bruto)}</div></div>
      <div class="indicador"><div class="rotulo">Ticket médio</div><div class="valor">${R(r.ticket_medio)}</div></div>
      <div class="indicador"><div class="rotulo">Recebido do crediário</div><div class="valor">${R(r.recebimentos_crediario)}</div></div>
    </div>
    <div class="cartao"><h2>Vendas por forma de pagamento</h2>
      <table>${Object.entries(r.por_forma).map(([f, v]) => `<tr><td>${forma(f)}</td><td class="num">${R(v)}</td></tr>`).join("") || `<tr><td class="suave">Sem vendas.</td></tr>`}</table></div>
    <div class="cartao"><h2>Produtos mais vendidos</h2><div class="tabela"><table><tr><th>Código</th><th>Produto</th><th class="num">Quantidade</th><th class="num">Valor</th></tr>
      ${mais.map((p) => `<tr><td>${esc(p.codigo)}</td><td>${esc(p.nome)}</td><td class="num">${Q(p.quantidade)} ${p.unidade}</td><td class="num">${R(p.valor)}</td></tr>`).join("") || `<tr><td colspan="4" class="suave">Sem vendas.</td></tr>`}</table></div></div>
    <div class="cartao"><h2>Estoque</h2>
      <p>${est.produtos} produtos ativos · Valor a custo: <b>${R(est.valor_custo)}</b> · Valor a preço de venda: <b>${R(est.valor_venda)}</b> ·
      ${est.estoque_baixo.length} abaixo do mínimo · ${est.sem_estoque.length} zerados</p></div>
    <div class="cartao"><h2>Segurança dos dados</h2>
      <div class="acoes"><button id="integridade">Conferir consistência (estoque, vendas, caixa, contas)</button><button id="backup">Fazer backup agora</button></div>
      <div id="res-seg" style="margin-top:10px"></div></div>`;
  $("#filtro").onsubmit = (e) => { e.preventDefault(); Object.assign(filtroRel, dadosForm(e.target)); renderizar(); };
  $("#integridade").onclick = async () => {
    try {
      const i = await GET("/api/integridade");
      $("#res-seg").innerHTML = i.ok ? `<span class="texto-ok">✔ Tudo confere: nenhum problema encontrado.</span>` : `<div class="texto-erro">${i.problemas.map(esc).join("<br>")}</div>`;
    } catch (e) { erro(e); }
  };
  $("#backup").onclick = async () => {
    try { const b = await POST("/api/backup"); $("#res-seg").innerHTML = `<span class="texto-ok">Backup salvo em ${esc(b.arquivo)}</span>`; } catch (e) { erro(e); }
  };
};

// ------------------------------------------------------------------ rotas
async function atualizarStatusCaixa() {
  try {
    const p = await GET("/api/painel");
    $("#status-caixa").innerHTML = p.caixa ? `<span class="aberto">● Caixa aberto</span><br>Gaveta: ${R(p.caixa.saldo_dinheiro)}` : `<span class="fechado">● Caixa fechado</span>`;
  } catch (_) { /* servidor indisponível */ }
}

async function renderizar() {
  const [nome, param] = (location.hash.slice(1) || "painel").split("/");
  const pagina = paginas[nome] || paginas.painel;
  $$("nav a").forEach((a) => a.classList.toggle("ativo", a.getAttribute("href") === "#" + nome));
  const el = $("#conteudo");
  try {
    await pagina(el, param);
  } catch (e) {
    el.innerHTML = `<div class="cartao texto-erro">Erro ao carregar: ${esc(e.message)}</div>`;
  }
}

window.addEventListener("hashchange", () => { fecharModal(); renderizar(); });
(async () => {
  CONFIG = await GET("/api/config");
  document.title = CONFIG.nome_loja;
  $(".marca").textContent = "🧱 " + CONFIG.nome_loja;
  atualizarStatusCaixa();
  renderizar();
})();
