"use strict";
// Interface do sistema da loja. A API devolve dinheiro em centavos e quantidades em milésimos.

// ================================================================ utilidades
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
const diaMes = (s) => { const [, m, d] = s.split("-"); return `${d}/${m}`; };
const dataLonga = (iso) => {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d)).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
};
const somarDias = (iso, n) => {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d + n)).toISOString().slice(0, 10);
};
const compacto = (c) => {
  const r = (c || 0) / 100;
  const f = (x) => x.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  if (Math.abs(r) >= 1e6) return `R$ ${f(r / 1e6)} mi`;
  if (Math.abs(r) >= 1000) return `R$ ${f(r / 1000)} mil`;
  return `R$ ${Math.round(r)}`;
};
const iniciais = (nome) => String(nome || "?").trim().split(/\s+/).filter((p) => p.length > 2 || /^[A-Z]/.test(p)).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "?";
const docFmt = (d) => {
  d = String(d || "");
  if (d.length === 11) return d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  if (d.length === 14) return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
  return d;
};
const avatar = (nome, cls = "") => `<div class="avatar ${cls}" aria-hidden="true">${esc(iniciais(nome))}</div>`;
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
const linhaValor = (preco, qtd) => Math.round((preco * (milesimos(qtd) || 0)) / 1000);

const FORMAS = {
  DINHEIRO: { nome: "Dinheiro", icone: "banknote" }, PIX: { nome: "PIX", icone: "zap" },
  DEBITO: { nome: "Débito", icone: "card" }, CREDITO: { nome: "Crédito", icone: "card" },
  CREDIARIO: { nome: "Crediário", icone: "book" }, DINHEIRO_CAIXA: { nome: "Dinheiro do caixa", icone: "banknote" },
  TRANSFERENCIA: { nome: "Transferência", icone: "arrows" }, BOLETO: { nome: "Boleto", icone: "file" }, CHEQUE: { nome: "Cheque", icone: "file" },
};
const forma = (f) => FORMAS[f]?.nome || f;

// ================================================================== ícones
const ICONES = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
  wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
  receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8M16 13H8M16 17H8"/>',
  banknote: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
  package: '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.7 4.73a2 2 0 0 0 2 0L20.7 7"/>',
  truck: '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
  arrows: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  building: '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2M10 6h4M10 10h4M10 14h4M10 18h4"/>',
  down: '<circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="m8 12 4 4 4-4"/>',
  up: '<circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/>',
  chart: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2m-7.07-14.07 1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M5 12h14M12 5v14"/>', minus: '<path d="M5 12h14"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  printer: '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
  pencil: '<path d="M21.17 6.81a1 1 0 0 0-3.99-3.99L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/><path d="m15 5 4 4"/>',
  trash: '<path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
  clipboard: '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  undo: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  eye: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
  card: '<rect width="20" height="14" x="2" y="5" rx="2"/><path d="M2 10h20"/>',
  zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  book: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
  bricks: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M2 12h20M12 4v8M7 12v8M17 12v8"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  trend: '<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  unlock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
  checkc: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
};
const ic = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONES[n] || ""}</svg>`;

// ===================================================================== API
let CONFIG = {};
let CAIXA = null;
async function api(metodo, caminho, corpo) {
  const op = { method: metodo, headers: {} };
  if (corpo !== undefined) { op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(corpo); }
  let resp;
  try { resp = await fetch(caminho, op); } catch (_) { throw new Error("Sem conexão com o sistema. Verifique se o programa está aberto."); }
  const dados = await resp.json().catch(() => ({ erro: "Resposta inválida do servidor" }));
  if (!resp.ok) throw new Error(dados.erro || `Erro ${resp.status}`);
  return dados;
}
const GET = (c) => api("GET", c);
const POST = (c, b = {}) => api("POST", c, b);
const PUT = (c, b) => api("PUT", c, b);

// ========================================================== avisos e modal
function avisar(msg, tipo = "ok") {
  const d = document.createElement("div");
  d.className = "toast " + tipo;
  d.innerHTML = ic(tipo === "erro" ? "alert" : "checkc") + "<div></div>";
  d.lastChild.textContent = msg;
  $("#avisos").appendChild(d);
  setTimeout(() => d.remove(), tipo === "erro" ? 6000 : 3500);
}
const erro = (e) => avisar(e.message || String(e), "erro");

function dadosForm(form) {
  const d = {};
  new FormData(form).forEach((v, k) => (d[k] = v));
  $$("input[type=checkbox]", form).forEach((c) => { if (c.name) d[c.name] = c.checked; });
  return d;
}

let aoFecharModal = null;
function abrirModal(titulo, html, largura = "720px") {
  $("#modal-titulo").textContent = titulo;
  $("#modal-corpo").innerHTML = html;
  $(".janela").style.maxWidth = largura;
  $("#modal").classList.remove("oculto");
  const primeiro = $("#modal-corpo [autofocus]") || $("#modal-corpo input:not([type=hidden]):not([type=checkbox]), #modal-corpo select");
  if (primeiro) setTimeout(() => primeiro.focus(), 0);
  return $("#modal-corpo");
}
function fecharModal() {
  if ($("#modal").classList.contains("oculto")) return;
  $("#modal").classList.add("oculto");
  $("#modal-corpo").innerHTML = "";
  const f = aoFecharModal;
  aoFecharModal = null;
  if (f) f();
}
$("#modal-fechar").innerHTML = ic("x");
$("#modal-fechar").onclick = fecharModal;
$("#modal").addEventListener("mousedown", (e) => { if (e.target.id === "modal") fecharModal(); });

// Formulário em modal. Se `acao(dados)` der erro, o formulário continua aberto e o erro aparece.
function modalForm(titulo, campos, acao, { botao = "Salvar", largura = "640px", perigo = false, msg = "" } = {}) {
  const c = abrirModal(titulo, `<form class="form">${campos}
    <div class="rodape larg"><button type="button" class="btn" data-cancelar>Cancelar</button>
    <button type="submit" class="btn ${perigo ? "perigo" : "primario"}">${botao}</button></div></form>`, largura);
  const form = $("form", c);
  $("[data-cancelar]", form).onclick = fecharModal;
  form.onsubmit = async (e) => {
    e.preventDefault();
    const b = $("button[type=submit]", form);
    b.disabled = true;
    try {
      await acao(dadosForm(form), form);
      if (msg) avisar(msg);
      fecharModal();
      await renderizar();
    } catch (err) { erro(err); } finally { b.disabled = false; }
  };
  return form;
}

function confirmar(titulo, texto, { botao = "Confirmar", perigo = false } = {}) {
  return new Promise((ok) => {
    let resposta = false;
    const c = abrirModal(titulo, `<p class="sec" style="margin:0">${texto}</p>
      <div class="rodape"><button class="btn" data-n>Voltar</button><button class="btn ${perigo ? "perigo" : "primario"}" data-s autofocus>${botao}</button></div>`, "460px");
    aoFecharModal = () => ok(resposta);
    $("[data-n]", c).onclick = fecharModal;
    $("[data-s]", c).onclick = () => { resposta = true; fecharModal(); };
  });
}

function imprimir(html) {
  $("#impressao").innerHTML = html;
  window.print();
}

// ============================================================= componentes
const vazio = (icone, titulo, texto = "", acao = "") =>
  `<div class="vazio"><div class="ic">${ic(icone)}</div><b>${titulo}</b>${texto}${acao ? `<div>${acao}</div>` : ""}</div>`;
const STATUS = {
  CONCLUIDA: ["Concluída", "ok"], PAGA: ["Paga", "ok"], CONVERTIDO: ["Virou venda", "ok"], ATIVA: ["Registrado", "ok"],
  ABERTO: ["Em aberto", "info"], ABERTA: ["Em aberto", "info"], FECHADO: ["Fechado", ""],
  CANCELADA: ["Cancelada", "danger"], CANCELADO: ["Cancelado", "danger"], ESTORNADA: ["Estornado", "danger"],
  VENCIDA: ["Vencida", "danger"], VENCIDO: ["Vencido", "danger"], INATIVO: ["Inativo", ""],
};
const badge = (s) => { const [t, c] = STATUS[s] || [s, ""]; return `<span class="badge ${c}">${esc(t)}</span>`; };
const kpi = ({ rot, val, det = "", icone = "chart", tom = "" }) =>
  `<div class="card kpi"><div class="ic ${tom}">${ic(icone)}</div><div><div class="rot">${rot}</div><div class="val">${val}</div>${det ? `<div class="det">${det}</div>` : ""}</div></div>`;
const opcoes = (lista, sel) => lista.map((o) => `<option value="${esc(o[0])}" ${String(o[0]) === String(sel ?? "") ? "selected" : ""}>${esc(o[1])}</option>`).join("");
const segmentado = (id, itens, atual) => `<div class="seg" id="${id}">${itens.map(([v, t]) => `<button type="button" data-v="${esc(v)}" class="${v === atual ? "on" : ""}">${t}</button>`).join("")}</div>`;
function aoSegmentar(id, cb) { $$(`#${id} button`).forEach((b) => (b.onclick = () => cb(b.dataset.v))); }

// Caixa de busca com lista de sugestões, navegável pelo teclado (↑ ↓ Enter Esc).
function autocompletar(input, { buscar, item, escolher, aoEnter, minimo = 2, textoVazio = "Nada encontrado" }) {
  const lista = document.createElement("div");
  lista.className = "ac-lista oculto";
  input.parentElement.appendChild(lista);
  lista.onmousedown = (e) => e.preventDefault();
  let resultados = [], ativo = 0, termoMostrado = null, tempo, pedido = 0;
  const fechar = () => { lista.classList.add("oculto"); termoMostrado = null; };
  function mostrar(r, termo) {
    resultados = r; ativo = 0; termoMostrado = termo;
    lista.innerHTML = r.length ? r.map((x, i) => `<div class="ac-item ${i === 0 ? "ativo" : ""}" data-i="${i}">${item(x)}</div>`).join("")
      : `<div class="ac-vazio">${textoVazio}</div>`;
    lista.classList.remove("oculto");
    $$(".ac-item", lista).forEach((d) => (d.onclick = () => { fechar(); escolher(resultados[d.dataset.i]); }));
  }
  async function buscarAgora(termo) {
    const n = ++pedido;
    const r = await buscar(termo);
    if (n === pedido && input.value.trim() === termo) mostrar(r, termo);
    return r;
  }
  input.addEventListener("input", () => {
    clearTimeout(tempo);
    const termo = input.value.trim();
    if (termo.length < minimo) { fechar(); return; }
    tempo = setTimeout(() => buscarAgora(termo).catch(erro), 180);
  });
  input.addEventListener("keydown", async (e) => {
    const aberto = !lista.classList.contains("oculto") && resultados.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!aberto) return;
      e.preventDefault();
      ativo = (ativo + (e.key === "ArrowDown" ? 1 : resultados.length - 1)) % resultados.length;
      $$(".ac-item", lista).forEach((d, i) => d.classList.toggle("ativo", i === ativo));
      $$(".ac-item", lista)[ativo].scrollIntoView({ block: "nearest" });
    } else if (e.key === "Escape") {
      if (!lista.classList.contains("oculto")) { e.stopPropagation(); fechar(); }
    } else if (e.key === "Enter") {
      e.preventDefault();
      const termo = input.value.trim();
      if (!termo) return;
      clearTimeout(tempo);
      if (aberto && termoMostrado === termo) { const x = resultados[ativo]; fechar(); escolher(x); return; }
      try {
        if (aoEnter && (await aoEnter(termo))) { fechar(); return; }
        const r = await buscarAgora(termo);
        if (r.length === 1) { fechar(); escolher(r[0]); }
      } catch (err) { erro(err); }
    }
  });
  input.addEventListener("blur", () => setTimeout(fechar, 120));
  return { fechar };
}

const itemProduto = (p) => `<div class="txt"><b>${esc(p.nome)}</b><span>${esc(p.codigo)}${p.categoria ? " · " + esc(p.categoria) : ""}${p.localizacao ? " · " + esc(p.localizacao) : ""}</span></div>
  <div class="dir"><b>${R(p.preco_venda)}</b><span class="${p.estoque > 0 ? "" : "t-danger"}">${p.estoque > 0 ? `${Q(p.estoque)} ${esc(p.unidade)} em estoque` : "sem estoque"}</span></div>`;
function autocompletarProduto(input, escolher) {
  return autocompletar(input, {
    buscar: async (t) => (await GET("/api/produtos?ativos=1&busca=" + encodeURIComponent(t))).slice(0, 15),
    item: itemProduto,
    escolher,
    minimo: 2,
    textoVazio: "Nenhum produto encontrado",
    aoEnter: async (t) => {
      try { escolher(await GET("/api/produtos/codigo/" + encodeURIComponent(t))); return true; } catch (_) { return false; }
    },
  });
}

// Seleção de cliente com busca. Mostra dívida, vencido e limite livre do escolhido.
function seletorCliente(el, { inicial = null, aoMudar = () => {}, placeholder = "Buscar cliente (nome, CPF/CNPJ ou telefone)" } = {}) {
  let atual = null;
  function desenhar() {
    if (atual) {
      const livre = Math.max(0, atual.limite_credito - atual.saldo_devedor);
      el.innerHTML = `<div class="cliente-sel">${avatar(atual.nome)}<div class="info"><b>${esc(atual.nome)}</b>
        <span>${atual.saldo_devedor ? `Deve ${R(atual.saldo_devedor)}` : "Sem débitos"} · Limite livre ${R(livre)}${atual.valor_vencido ? ` · <span class="t-danger">${R(atual.valor_vencido)} vencido</span>` : ""}</span></div>
        <button type="button" class="btn sm icone fantasma" title="Tirar cliente" aria-label="Tirar cliente">${ic("x")}</button></div>`;
      $("button", el).onclick = () => { definir(null); setTimeout(() => $("input", el)?.focus(), 0); };
    } else {
      el.innerHTML = `<div class="ac busca">${ic("search")}<input class="cli-busca" placeholder="${placeholder}" autocomplete="off"></div>`;
      autocompletar($("input", el), {
        buscar: async (t) => (await GET("/api/clientes?ativos=1&busca=" + encodeURIComponent(t))).slice(0, 12),
        item: (c) => `${avatar(c.nome)}<div class="txt"><b>${esc(c.nome)}</b><span>${esc(docFmt(c.documento) || c.telefone || "—")}</span></div>
          <div class="dir">${c.saldo_devedor ? `<b class="${c.valor_vencido ? "t-danger" : ""}">${R(c.saldo_devedor)}</b><span>em aberto</span>` : `<span>sem débitos</span>`}</div>`,
        escolher: async (c) => definir((await GET(`/api/clientes/${c.id}/debitos`)).cliente),
        minimo: 1, textoVazio: "Nenhum cliente encontrado",
      });
    }
  }
  function definir(c) { atual = c; desenhar(); aoMudar(c); }
  desenhar();
  if (inicial) GET(`/api/clientes/${inicial}/debitos`).then((d) => definir(d.cliente)).catch(erro);
  return { obter: () => atual, focar: () => $("input", el)?.focus() };
}

// Pagamento de venda: uma forma (com troco no dinheiro) ou várias formas divididas.
function widgetPagamento(el, { obterTotal, obterCliente = () => null }) {
  const FV = CONFIG.formas_pagamento || ["DINHEIRO", "PIX", "DEBITO", "CREDITO", "CREDIARIO"];
  const st = { modo: "simples", forma: "DINHEIRO", recebido: "", linhas: [], parcelas: "1", venc: "" };
  function calcular() {
    const total = obterTotal();
    if (st.modo === "simples") {
      const v = st.forma === "DINHEIRO" && st.recebido.trim() ? centavos(st.recebido) : total;
      return { total, pagamentos: [{ forma: st.forma, valor: v }], pago: v };
    }
    let preenchido = 0;
    st.linhas.forEach((l) => { if (l.valor.trim()) preenchido += centavos(l.valor) || 0; });
    const vazia = st.linhas.find((l) => !l.valor.trim());
    const pagamentos = st.linhas.map((l) => ({ forma: l.forma, valor: l.valor.trim() ? centavos(l.valor) : l === vazia ? Math.max(0, total - preenchido) : 0 }));
    return { total, pagamentos, pago: pagamentos.reduce((s, p) => s + p.valor, 0) };
  }
  const temCred = () => (st.modo === "simples" ? st.forma === "CREDIARIO" : st.linhas.some((l) => l.forma === "CREDIARIO"));
  const blocoCred = () => `<div class="cred mt-s">
      <div class="aviso-box info cred-sem-cliente oculto">${ic("info")}<div>Escolha o cliente acima para vender no crediário.</div></div>
      <div class="form mt-s"><label class="campo"><span>Parcelas</span><select class="cred-parc">${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}" ${String(i + 1) === st.parcelas ? "selected" : ""}>${i + 1}x</option>`).join("")}</select></label>
      <label class="campo"><span>1º vencimento</span><input type="date" class="cred-venc" value="${esc(st.venc)}" min="${CONFIG.hoje}"></label></div></div>`;
  function desenhar() {
    if (st.modo === "simples") {
      el.innerHTML = `<div class="formas">${FV.map((f) => `<button type="button" class="chip ${st.forma === f ? "on" : ""}" data-f="${f}">${ic(FORMAS[f].icone)}${FORMAS[f].nome}</button>`).join("")}</div>
        ${st.forma === "DINHEIRO" ? `<label class="campo mt"><span>Valor recebido do cliente</span><div class="prefixo"><b>R$</b><input class="pg-recebido num" inputmode="decimal" value="${esc(st.recebido)}" autocomplete="off"></div></label>
          <div class="atalhos-valor mt-s pg-notas"></div>` : ""}
        ${st.forma === "CREDIARIO" ? blocoCred() : ""}
        <div class="pg-resumo mt"></div>
        <button type="button" class="btn sm fantasma mt-s pg-dividir">${ic("plus")}Dividir em mais de uma forma</button>`;
      $$(".chip", el).forEach((b) => (b.onclick = () => { st.forma = b.dataset.f; desenhar(); }));
      const r = $(".pg-recebido", el);
      if (r) r.oninput = () => { st.recebido = r.value; resumo(); };
      $(".pg-dividir", el).onclick = () => {
        st.modo = "dividido";
        st.linhas = [{ forma: st.forma, valor: "" }, { forma: st.forma === "PIX" ? "DINHEIRO" : "PIX", valor: "" }];
        desenhar();
      };
    } else {
      el.innerHTML = `<div class="pg-linhas">${st.linhas.map((l, i) => `<div class="linha mb" style="flex-wrap:nowrap">
          <select class="pg-forma" data-i="${i}" style="flex:1">${opcoes(FV.map((f) => [f, FORMAS[f].nome]), l.forma)}</select>
          <div class="prefixo" style="width:130px;flex-shrink:0"><b>R$</b><input class="pg-valor num" data-i="${i}" value="${esc(l.valor)}" inputmode="decimal"></div>
          <button type="button" class="btn icone fantasma pg-rm" data-i="${i}" title="Remover" aria-label="Remover" ${st.linhas.length <= 1 ? "disabled" : ""}>${ic("x")}</button></div>`).join("")}</div>
        <div class="linha"><button type="button" class="btn sm pg-mais">${ic("plus")}Outra forma</button>
          <button type="button" class="btn sm fantasma pg-unico">Pagamento único</button></div>
        ${temCred() ? blocoCred() : ""}
        <div class="pg-resumo mt"></div>
        <p class="muted small">Deixe um valor em branco para completar com o que falta.</p>`;
      $$(".pg-forma", el).forEach((s) => (s.onchange = () => { st.linhas[s.dataset.i].forma = s.value; desenhar(); }));
      $$(".pg-valor", el).forEach((s) => (s.oninput = () => { st.linhas[s.dataset.i].valor = s.value; resumo(); }));
      $$(".pg-rm", el).forEach((b) => (b.onclick = () => { st.linhas.splice(b.dataset.i, 1); desenhar(); }));
      $(".pg-mais", el).onclick = () => { st.linhas.push({ forma: "PIX", valor: "" }); desenhar(); };
      $(".pg-unico", el).onclick = () => { st.modo = "simples"; st.forma = st.linhas[0]?.forma || "DINHEIRO"; st.recebido = ""; desenhar(); };
    }
    const p = $(".cred-parc", el), v = $(".cred-venc", el);
    if (p) p.onchange = () => { st.parcelas = p.value; resumo(); };
    if (v) v.onchange = () => { st.venc = v.value; };
    resumo();
  }
  function resumo() {
    const { total, pagamentos, pago } = calcular();
    const caixa = $(".pg-resumo", el);
    if (!caixa) return;
    const dinheiro = pagamentos.reduce((s, p) => s + (p.forma === "DINHEIRO" ? p.valor || 0 : 0), 0);
    const diff = pago - total;
    if (Number.isNaN(pago)) caixa.innerHTML = `<div class="destaque-falta"><span>Valor inválido</span></div>`;
    else if (diff < 0) caixa.innerHTML = `<div class="destaque-falta"><span>Falta</span><span>${R(-diff)}</span></div>`;
    else if (diff > 0 && dinheiro > diff) caixa.innerHTML = `<div class="destaque-ok"><span>Troco</span><b>${R(diff)}</b></div>`;
    else if (diff > 0) caixa.innerHTML = `<div class="destaque-falta"><span>Passou ${R(diff)} — troco só em dinheiro</span></div>`;
    else caixa.innerHTML = st.modo === "simples" && st.forma !== "DINHEIRO"
      ? `<div class="linha entre sec"><span>${st.forma === "CREDIARIO" ? "Vai para a conta do cliente" : `Cobrar no ${FORMAS[st.forma].nome}`}</span><b>${R(total)}</b></div>`
      : `<div class="linha t-ok strong">${ic("checkc")}<span>Pagamento completo</span></div>`;
    const r = $(".pg-recebido", el);
    if (r) r.placeholder = paraCampo(total);
    const notas = $(".pg-notas", el);
    if (notas) {
      const sugest = [...new Set([total, Math.ceil(total / 1000) * 1000, Math.ceil(total / 5000) * 5000, Math.ceil(total / 10000) * 10000])].filter((x) => x >= total && x > 0).slice(0, 4);
      notas.innerHTML = sugest.map((x, i) => `<button type="button" class="btn sm" data-v="${x}">${i === 0 ? "Valor exato" : R(x)}</button>`).join("");
      $$("button", notas).forEach((b) => (b.onclick = () => { st.recebido = paraCampo(Number(b.dataset.v)); r.value = st.recebido; resumo(); }));
    }
    const credVal = pagamentos.filter((p) => p.forma === "CREDIARIO").reduce((s, p) => s + (p.valor || 0), 0);
    $$(".cred-parc option", el).forEach((o) => {
      const n = Number(o.value);
      o.textContent = credVal ? `${n}x de ${credVal % n ? "≈ " : ""}${R(Math.round(credVal / n))}` : `${n}x`;
    });
    const aviso = $(".cred-sem-cliente", el);
    if (aviso) aviso.classList.toggle("oculto", !!obterCliente());
  }
  desenhar();
  return {
    atualizar: resumo,
    limpar() { Object.assign(st, { modo: "simples", forma: "DINHEIRO", recebido: "", linhas: [], parcelas: "1", venc: "" }); desenhar(); },
    dados() {
      const { pagamentos } = calcular();
      if (pagamentos.some((p) => Number.isNaN(p.valor))) throw new Error("Confira o valor do pagamento: número inválido");
      const r = { pagamentos: pagamentos.filter((p) => p.valor > 0).map((p) => ({ forma: p.forma, valor: paraCampo(p.valor) })) };
      if (temCred()) {
        r.crediario = { parcelas: st.parcelas };
        if (st.venc) r.crediario.primeiro_vencimento = st.venc;
      }
      return r;
    },
  };
}

// Gráfico de colunas (uma série): faturamento por dia. Dica ao passar o mouse ou focar pelo teclado.
function passoBonito(x) {
  if (x <= 0) return 5000;
  const mag = 10 ** Math.floor(Math.log10(x));
  const n = x / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
}
function graficoColunas(el, serie) {
  const NS = "http://www.w3.org/2000/svg";
  el.classList.add("grafico");
  el.innerHTML = `<svg role="img" aria-label="Faturamento por dia"></svg><div class="dica oculto"><b></b><span></span></div>`;
  const svg = $("svg", el), dica = $(".dica", el);
  const no = (tag, attrs, txt) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (txt != null) n.textContent = txt; return n; };
  let largura = 0;
  function desenhar() {
    const W = Math.max(300, el.clientWidth);
    if (W === largura) return;
    largura = W;
    const H = 236, mL = 64, mR = 6, mT = 24, mB = 26;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("height", H);
    svg.textContent = "";
    const max = Math.max(0, ...serie.map((s) => s.total));
    const passo = passoBonito(max / 4), topo = passo * 4;
    const pw = W - mL - mR, ph = H - mT - mB, banda = pw / serie.length, bw = Math.min(24, banda * 0.62);
    const y = (v) => mT + ph - (v / topo) * ph;
    for (let k = 0; k <= 4; k++) {
      const v = passo * k, yy = Math.round(y(v)) + 0.5;
      svg.appendChild(no("line", { x1: mL, x2: W - mR, y1: yy, y2: yy, class: "grade-y" }));
      svg.appendChild(no("text", { x: mL - 10, y: yy + 4, "text-anchor": "end", class: "eixo-txt" }, compacto(v)));
    }
    const cada = banda >= 38 ? 1 : banda >= 20 ? 2 : 3;
    const imax = serie.reduce((m, s, i) => (s.total > serie[m].total ? i : m), 0);
    serie.forEach((s, i) => {
      const x = mL + i * banda + (banda - bw) / 2, base = mT + ph;
      const h = (s.total / topo) * ph;
      if (h > 0.5) {
        const r = Math.min(4, h, bw / 2), t = base - h;
        svg.appendChild(no("path", { class: "barra", "data-i": i,
          d: `M${x},${base}V${t + r}Q${x},${t} ${x + r},${t}H${x + bw - r}Q${x + bw},${t} ${x + bw},${t + r}V${base}Z` }));
        if ((i === imax || i === serie.length - 1) && s.total > 0)
          svg.appendChild(no("text", { x: x + bw / 2, y: t - 7, "text-anchor": "middle", class: "rotulo" }, compacto(s.total)));
      }
      if ((serie.length - 1 - i) % cada === 0)
        svg.appendChild(no("text", { x: mL + i * banda + banda / 2, y: H - 6, "text-anchor": "middle", class: "eixo-txt" }, i === serie.length - 1 ? "Hoje" : diaMes(s.data)));
      const alvo = no("rect", { x: mL + i * banda, y: mT, width: banda, height: ph, class: "alvo", tabindex: 0, "data-i": i,
        "aria-label": `${dataBR(s.data)}: ${R(s.total)}, ${s.quantidade} venda(s)` });
      const mostrar = () => {
        el.classList.add("hover");
        $$(".barra", svg).forEach((b) => b.classList.toggle("ativa", Number(b.dataset.i) === i));
        $("b", dica).textContent = R(s.total);
        $("span", dica).textContent = `${dataBR(s.data)} · ${s.quantidade} venda${s.quantidade === 1 ? "" : "s"}`;
        dica.classList.remove("oculto");
        const k = el.clientWidth / W;
        dica.style.left = Math.min(Math.max((x + bw / 2) * k, 70), el.clientWidth - 70) + "px";
        dica.style.top = (Math.min(y(s.total), base - 2) - 10) * k + "px";
      };
      const esconder = () => { el.classList.remove("hover"); dica.classList.add("oculto"); };
      alvo.addEventListener("pointerenter", mostrar);
      alvo.addEventListener("focus", mostrar);
      alvo.addEventListener("pointerleave", esconder);
      alvo.addEventListener("blur", esconder);
      svg.appendChild(alvo);
    });
  }
  desenhar();
  if (window.ResizeObserver) new ResizeObserver(() => { if (el.clientWidth) desenhar(); }).observe(el);
}

// =============================================================== recibos
const cabecalhoRecibo = (titulo) => `<div style="text-align:center"><b>${esc(CONFIG.nome_loja)}</b><br>${esc(titulo)}</div><hr>`;
function reciboVenda(v) {
  return `<div class="recibo">${cabecalhoRecibo(`VENDA Nº ${v.id} — ${dataBR(v.data)}`)}
    ${v.cliente ? `Cliente: ${esc(v.cliente)}<br>` : ""}${v.status === "CANCELADA" ? "<b>*** VENDA CANCELADA ***</b><br>" : ""}
    <table><tr><th>Item</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th></tr>
    ${v.itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade)} ${esc(i.unidade)}</td><td class="num">${R(i.preco_unitario)}</td><td class="num">${R(i.total)}</td></tr>`).join("")}
    </table><hr>
    <div class="lt"><span>Subtotal</span><span>${R(v.subtotal)}</span></div>
    ${v.desconto ? `<div class="lt"><span>Desconto</span><span>-${R(v.desconto)}</span></div>` : ""}
    <div class="lt"><b>TOTAL</b><b>${R(v.total)}</b></div><hr>
    ${v.pagamentos.map((p) => `<div class="lt"><span>${forma(p.forma)}</span><span>${R(p.valor)}</span></div>`).join("")}
    ${v.troco ? `<div class="lt"><span>Troco</span><span>${R(v.troco)}</span></div>` : ""}
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
    <div class="lt"><span>Subtotal</span><span>${R(o.subtotal)}</span></div>
    ${o.desconto ? `<div class="lt"><span>Desconto</span><span>-${R(o.desconto)}</span></div>` : ""}
    <div class="lt"><b>TOTAL</b><b>${R(o.total)}</b></div>
    ${o.observacao ? `<hr>${esc(o.observacao)}` : ""}<hr><div style="text-align:center">Orçamento sujeito à disponibilidade de estoque.</div></div>`;
}
function reciboBaixa(b) {
  return `<div class="recibo">${cabecalhoRecibo(`COMPROVANTE DE PAGAMENTO Nº ${b.id}`)}
    Data: ${dataBR(b.data)}<br>Cliente: ${esc(b.cliente)}${b.cliente_documento ? `<br>CPF/CNPJ: ${esc(docFmt(b.cliente_documento))}` : ""}
    ${b.status === "ESTORNADA" ? "<br><b>*** PAGAMENTO ESTORNADO ***</b>" : ""}<hr>
    <table><tr><th>Referente a</th><th class="num">Pago</th></tr>
    ${b.itens.map((i) => `<tr><td>Compra nº ${i.venda_id} — parc. ${i.parcela}/${i.total_parcelas}${i.status === "PAGA" ? " (quitada)" : ""}</td><td class="num">${R(i.valor)}</td></tr>`).join("")}
    </table><hr>
    <div class="lt"><b>VALOR PAGO</b><b>${R(b.valor)}</b></div>
    <div class="lt"><span>Forma</span><span>${forma(b.forma)}</span></div>
    ${b.troco ? `<div class="lt"><span>Entregue</span><span>${R(b.valor_recebido)}</span></div><div class="lt"><span>Troco</span><span>${R(b.troco)}</span></div>` : ""}
    <hr><div class="lt"><span>Saldo anterior</span><span>${R(b.saldo_anterior)}</span></div>
    <div class="lt"><b>SALDO DEVEDOR ATUAL</b><b>${R(b.saldo_apos)}</b></div>
    ${b.observacao ? `<hr>${esc(b.observacao)}` : ""}
    <br><br>_______________________________<br>${esc(CONFIG.nome_loja)}</div>`;
}

// ================================================================= páginas
const paginas = {};
const TITULOS = {
  painel: ["Painel", "Resumo do dia"], pdv: ["Vender", "Ponto de venda"], "receber-cliente": ["Receber de cliente", "Baixa na conta do crediário"],
  orcamentos: ["Orçamentos", "Propostas para clientes"], vendas: ["Vendas", "Histórico, devoluções e cancelamentos"],
  caixa: ["Caixa", "Abertura, sangria e fechamento"], produtos: ["Produtos", "Cadastro, preços e estoque"],
  compras: ["Entrada de mercadoria", "Compras de fornecedores"], movimentos: ["Movimentações", "Tudo que entrou e saiu do estoque"],
  clientes: ["Clientes", "Cadastro e crédito"], fornecedores: ["Fornecedores", "Cadastro"], receber: ["Contas a receber", "Parcelas do crediário"],
  pagar: ["Contas a pagar", "Fornecedores e despesas"], relatorios: ["Relatórios", "Desempenho da loja"],
};
const NAV = [
  [null, [["painel", "Painel", "dashboard"], ["pdv", "Vender", "cart", "F2"], ["receber-cliente", "Receber de cliente", "wallet", "F3"],
    ["orcamentos", "Orçamentos", "file"], ["vendas", "Vendas", "receipt"], ["caixa", "Caixa", "banknote"]]],
  ["Estoque", [["produtos", "Produtos", "package"], ["compras", "Entrada de mercadoria", "truck"], ["movimentos", "Movimentações", "arrows"]]],
  ["Cadastros", [["clientes", "Clientes", "users"], ["fornecedores", "Fornecedores", "building"]]],
  ["Financeiro", [["receber", "Contas a receber", "down"], ["pagar", "Contas a pagar", "up"], ["relatorios", "Relatórios", "chart"]]],
];
const avisoCaixaFechado = (texto) => `<div class="aviso-box mb">${ic("lock")}<div style="flex:1"><b>O caixa está fechado.</b> ${texto}</div><a class="btn sm" href="#caixa">Abrir caixa</a></div>`;

// ------------------------------------------------------------------ painel
const saudacao = () => { const h = new Date().getHours(); return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite"; };
const listaFormas = (porForma) => {
  const formas = Object.entries(porForma);
  const total = formas.reduce((s, [, x]) => s + x, 0);
  return formas.map(([f, x]) => `<div class="mb"><div class="linha entre"><span>${forma(f)}</span><b class="num">${R(x)}</b></div>
    <div class="barra-prop" title="${Math.round((x / total) * 100)}%"><i style="width:${(x / total) * 100}%"></i></div></div>`).join("")
    + `<div class="linha entre strong" style="border-top:1px solid var(--border);padding-top:10px"><span>Total</span><span class="num">${R(total)}</span></div>`;
};
paginas.painel = async (el) => {
  const [p, baixo] = await Promise.all([GET("/api/painel"), GET("/api/produtos?estoque_baixo=1")]);
  const v = p.vendas_hoje;
  const margem = v.liquido ? Math.round((v.lucro_bruto / v.liquido) * 100) : 0;
  el.innerHTML = `
    <div class="linha entre mb"><div><h2 style="font-size:21px">${saudacao()}!</h2><div class="muted">${dataLonga(p.data)}</div></div>
      <div class="linha"><a class="btn primario" href="#pdv">${ic("cart")}Nova venda</a><a class="btn" href="#receber-cliente">${ic("wallet")}Receber de cliente</a>
      <a class="btn esconder-m" href="#compras">${ic("truck")}Entrada de mercadoria</a></div></div>
    ${p.caixa ? "" : avisoCaixaFechado("Abra o caixa para começar a vender e receber.")}
    <div class="grid g-4">
      ${kpi({ rot: "Vendido hoje", val: R(v.liquido), det: `${v.quantidade} venda${v.quantidade === 1 ? "" : "s"} · ticket médio ${R(v.ticket_medio)}`, icone: "trend" })}
      ${kpi({ rot: "Lucro bruto hoje", val: R(v.lucro_bruto), det: v.liquido ? `margem de ${margem}% sobre as vendas` : "sem vendas ainda", icone: "chart", tom: "ok" })}
      ${kpi({ rot: "Dinheiro no caixa", val: p.caixa ? R(p.caixa.saldo_dinheiro) : "Fechado", det: p.caixa ? `aberto em ${dataBR(p.caixa.abertura)}` : "abra o caixa para vender", icone: "banknote", tom: "info" })}
      ${kpi({ rot: "A receber dos clientes", val: R(p.receber_aberto), det: p.receber_vencido ? `<span class="t-danger">${R(p.receber_vencido)} vencido</span>` : "nada vencido", icone: "wallet", tom: p.receber_vencido ? "danger" : "warn" })}
    </div>
    <div class="grid g-2-1 mt">
      <div class="card"><div class="card-h"><div><h2>Vendas dos últimos 14 dias</h2><div class="sub">Faturamento líquido por dia (vendas menos devoluções)</div></div>
        <div class="acoes">${segmentado("vis-graf", [["g", "Gráfico"], ["t", "Tabela"]], "g")}</div></div>
        <div class="card-b"><div id="graf"></div><div id="graf-tab" class="oculto tabela"><table class="tbl-compacta"><thead><tr><th>Dia</th><th class="num">Vendas</th><th class="num">Valor</th></tr></thead>
          <tbody>${p.vendas_por_dia.slice().reverse().map((d) => `<tr><td>${dataBR(d.data)}</td><td class="num">${d.quantidade}</td><td class="num">${R(d.total)}</td></tr>`).join("")}</tbody></table></div></div></div>
      <div class="card"><div class="card-h"><h2>Hoje por forma de pagamento</h2></div><div class="card-b">
        ${Object.keys(v.por_forma).length ? listaFormas(v.por_forma) : vazio("receipt", "Nenhuma venda hoje", "", `<a class="btn sm primario" href="#pdv">Fazer uma venda</a>`)}
      </div></div>
    </div>
    <div class="grid g-3 mt">
      <div class="card"><div class="card-h"><h2>Clientes com conta vencida</h2></div><div class="card-b flush">
        ${p.clientes_em_atraso.length ? `<table class="tbl-compacta"><tbody>${p.clientes_em_atraso.map((c) => `<tr>
          <td><b>${esc(c.nome)}</b><span class="sub">vencido desde ${dataBR(c.desde)}</span></td>
          <td class="num t-danger strong">${R(c.vencido)}</td><td class="acoes"><a class="btn sm" href="#receber-cliente/${c.id}">Receber</a></td></tr>`).join("")}</tbody></table>`
          : vazio("checkc", "Nenhuma conta vencida")}</div></div>
      <div class="card"><div class="card-h"><h2>Estoque baixo</h2><div class="acoes"><a class="btn sm fantasma" href="#produtos">Ver produtos</a></div></div><div class="card-b flush">
        ${baixo.length ? `<table class="tbl-compacta"><tbody>${baixo.slice(0, 8).map((x) => `<tr><td>${esc(x.nome)}<span class="sub">${esc(x.codigo)} · mín. ${Q(x.estoque_minimo)}</span></td>
          <td class="num ${x.estoque === 0 ? "t-danger" : "t-warn"} strong">${Q(x.estoque)} ${esc(x.unidade)}</td></tr>`).join("")}</tbody></table>`
          : vazio("package", "Estoque em dia")}</div></div>
      <div class="card"><div class="card-h"><h2>Contas a pagar (7 dias)</h2><div class="acoes"><a class="btn sm fantasma" href="#pagar">Ver todas</a></div></div><div class="card-b flush">
        ${p.contas_pagar_proximas.length ? `<table class="tbl-compacta"><tbody>${p.contas_pagar_proximas.map((c) => `<tr><td>${esc(c.descricao)}<span class="sub ${c.vencimento < p.data ? "t-danger" : ""}">vence ${dataBR(c.vencimento)}</span></td>
          <td class="num strong">${R(c.restante)}</td></tr>`).join("")}</tbody></table>`
          : vazio("checkc", "Nada para pagar nos próximos dias")}</div></div>
    </div>`;
  graficoColunas($("#graf"), p.vendas_por_dia);
  aoSegmentar("vis-graf", (x) => {
    $$("#vis-graf button").forEach((b) => b.classList.toggle("on", b.dataset.v === x));
    $("#graf").classList.toggle("oculto", x !== "g");
    $("#graf-tab").classList.toggle("oculto", x !== "t");
  });
};

// --------------------------------------------------------------------- PDV
const pdv = { itens: [], cliente: null, descModo: "R$", desconto: "" };
paginas.pdv = async (el) => {
  el.innerHTML = `
    ${CAIXA ? "" : avisoCaixaFechado("Você pode montar orçamentos, mas para vender é preciso abrir o caixa.")}
    <div class="grid g-main-side">
      <div class="pilha">
        <div class="card"><div class="card-b">
          <div class="linha" style="flex-wrap:nowrap;align-items:flex-end">
            <label class="campo" style="flex:1"><span>Produto <span class="ajuda">— nome, código ou código de barras</span><kbd>F2</kbd></span>
              <div class="ac busca grande">${ic("search")}<input id="busca" autocomplete="off" placeholder="Digite e tecle Enter"></div></label>
            <label class="campo" style="width:110px"><span>Quantidade</span><input id="qtd" value="1" class="num" inputmode="decimal" style="height:50px;font-size:16px"></label>
          </div></div></div>
        <div class="card"><div class="card-h"><h2>Itens da venda</h2><span class="sub" id="n-itens"></span>
          <div class="acoes"><button class="btn sm fantasma" id="limpar">${ic("trash")}Limpar</button></div></div>
          <div class="tabela"><table><thead><tr><th>Produto</th><th style="text-align:center">Quantidade</th><th class="num">Preço</th><th class="num">Total</th><th></th></tr></thead>
          <tbody id="itens"></tbody></table></div><div id="cart-vazio"></div></div>
      </div>
      <div class="card sticky"><div class="card-b">
        <div class="campo"><span>Cliente <kbd>F6</kbd></span><div id="sel-cliente"></div></div>
        <div class="campo mt"><span>Desconto <kbd>F8</kbd></span><div class="linha" style="flex-wrap:nowrap">
          ${segmentado("desc-modo", [["R$", "R$"], ["%", "%"]], pdv.descModo)}<input id="desconto" class="num" inputmode="decimal" placeholder="0" value="${esc(pdv.desconto)}"></div></div>
        <div class="mt"><div class="linha-total"><span>Subtotal</span><b id="subtotal"></b></div>
          <div class="linha-total"><span>Desconto</span><b id="vdesconto"></b></div>
          <div class="linha-total grande"><span>Total</span><span class="total-grande" id="total"></span></div></div>
        <div class="campo mt"><span>Pagamento</span><div id="pagamento"></div></div>
        <button class="btn primario lg bloco mt" id="finalizar">${ic("check")}Finalizar venda<kbd>F4</kbd></button>
        <button class="btn bloco mt-s" id="orcamento">${ic("file")}Salvar como orçamento</button>
      </div></div>
    </div>`;

  const totais = () => {
    const subtotal = pdv.itens.reduce((s, i) => s + linhaValor(i.produto.preco_venda, i.quantidade), 0);
    const desconto = pdv.descModo === "%"
      ? Math.round((subtotal * Math.round((Number(pdv.desconto.replace(",", ".")) || 0) * 100)) / 10000)
      : centavos(pdv.desconto) || 0;
    return { subtotal, desconto, total: Math.max(0, subtotal - desconto) };
  };
  let pag = null;
  const cli = seletorCliente($("#sel-cliente"), { inicial: pdv.cliente?.id, aoMudar: (c) => { pdv.cliente = c; if (pag) pag.atualizar(); } });
  pag = widgetPagamento($("#pagamento"), { obterTotal: () => totais().total, obterCliente: () => pdv.cliente });

  function atualizarTotais() {
    const t = totais();
    $("#subtotal").textContent = R(t.subtotal);
    $("#vdesconto").textContent = t.desconto ? "- " + R(t.desconto) : R(0);
    $("#total").textContent = R(t.total);
    const n = pdv.itens.length;
    $("#n-itens").textContent = n ? `${n} ${n === 1 ? "item" : "itens"}` : "";
    pag.atualizar();
  }
  function avisoEstoque(item, tr) {
    const falta = milesimos(item.quantidade) > item.produto.estoque;
    tr.classList.toggle("alerta", falta);
    $(".est", tr).innerHTML = falta ? `<span class="t-danger">Só ${Q(item.produto.estoque)} ${esc(item.produto.unidade)} em estoque</span>`
      : `${esc(item.produto.codigo)} · estoque ${Q(item.produto.estoque)} ${esc(item.produto.unidade)}`;
  }
  function desenhar() {
    $("#itens").innerHTML = pdv.itens.map((i, n) => `<tr data-n="${n}">
      <td><b>${esc(i.produto.nome)}</b><span class="sub est"></span></td>
      <td style="text-align:center"><div class="qtd"><button type="button" class="menos" aria-label="Diminuir">${ic("minus")}</button>
        <input class="q num" value="${esc(i.quantidade)}" inputmode="decimal" aria-label="Quantidade"><button type="button" class="mais" aria-label="Aumentar">${ic("plus")}</button></div>
        <span class="sub">${esc(i.produto.unidade)}</span></td>
      <td class="num">${R(i.produto.preco_venda)}</td><td class="num strong tl">${R(linhaValor(i.produto.preco_venda, i.quantidade))}</td>
      <td class="acoes"><button class="btn sm icone fantasma rm" title="Remover item" aria-label="Remover item">${ic("trash")}</button></td></tr>`).join("");
    $("#cart-vazio").innerHTML = pdv.itens.length ? "" : `<div class="cart-vazio"><div class="ic">${ic("cart")}</div><b>Nenhum produto ainda</b><br>Busque um produto acima para começar a venda.</div>`;
    $$("#itens tr").forEach((tr) => {
      const item = pdv.itens[tr.dataset.n];
      const inp = $(".q", tr);
      const mudar = () => {
        item.quantidade = inp.value;
        $(".tl", tr).textContent = R(linhaValor(item.produto.preco_venda, item.quantidade));
        avisoEstoque(item, tr);
        atualizarTotais();
      };
      inp.oninput = mudar;
      $(".mais", tr).onclick = () => { inp.value = qtdCampo((milesimos(inp.value) || 0) + 1000); mudar(); };
      $(".menos", tr).onclick = () => { const q = (milesimos(inp.value) || 0) - 1000; if (q > 0) { inp.value = qtdCampo(q); mudar(); } };
      $(".rm", tr).onclick = () => { pdv.itens.splice(tr.dataset.n, 1); desenhar(); };
      avisoEstoque(item, tr);
    });
    atualizarTotais();
  }
  function adicionar(produto) {
    const qtd = $("#qtd").value.trim() || "1";
    if (!(milesimos(qtd) > 0)) { erro(new Error("Quantidade inválida")); return; }
    const existente = pdv.itens.find((i) => i.produto.id === produto.id);
    if (existente) existente.quantidade = qtdCampo((milesimos(existente.quantidade) || 0) + milesimos(qtd));
    else pdv.itens.push({ produto, quantidade: qtd });
    $("#busca").value = "";
    $("#qtd").value = "1";
    $("#busca").focus();
    desenhar();
  }
  autocompletarProduto($("#busca"), adicionar);
  $("#qtd").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); $("#busca").focus(); } };
  aoSegmentar("desc-modo", (m) => { pdv.descModo = m; $$("#desc-modo button").forEach((b) => b.classList.toggle("on", b.dataset.v === m)); atualizarTotais(); });
  $("#desconto").oninput = (e) => { pdv.desconto = e.target.value; atualizarTotais(); };
  const itensEnvio = () => pdv.itens.map((i) => ({ produto_id: i.produto.id, quantidade: i.quantidade }));
  const descontoEnvio = () => (pdv.descModo === "%" ? { desconto_percentual: pdv.desconto } : { desconto: pdv.desconto });
  const zerar = () => { pdv.itens = []; pdv.cliente = null; pdv.desconto = ""; };
  $("#limpar").onclick = async () => {
    if (!pdv.itens.length || (await confirmar("Limpar venda", "Tirar todos os itens desta venda?", { botao: "Limpar", perigo: true }))) { zerar(); renderizar(); }
  };
  $("#finalizar").onclick = async () => {
    if (!pdv.itens.length) { erro(new Error("Adicione ao menos um produto")); $("#busca").focus(); return; }
    const b = $("#finalizar");
    b.disabled = true;
    try {
      const venda = await POST("/api/vendas", { itens: itensEnvio(), cliente_id: pdv.cliente?.id || null, ...descontoEnvio(), ...pag.dados() });
      zerar();
      await atualizarCaixa();
      const c = abrirModal("Venda concluída", `<div class="sucesso"><div class="ic">${ic("check")}</div>
        <div class="muted">Venda nº ${venda.id}${venda.cliente ? " · " + esc(venda.cliente) : ""}</div><div class="total-grande">${R(venda.total)}</div>
        ${venda.troco ? `<div class="destaque-ok mt" style="justify-content:center;gap:12px"><span>Troco</span><b>${R(venda.troco)}</b></div>` : ""}
        ${venda.parcelas.length ? `<p class="sec">${venda.parcelas.length}x no crediário · 1ª parcela em ${dataBR(venda.parcelas[0].vencimento)}</p>` : ""}</div>
        <div class="rodape" style="justify-content:center"><button class="btn" id="imp">${ic("printer")}Imprimir comprovante</button><button class="btn primario" id="ok" autofocus>Nova venda</button></div>`, "460px");
      aoFecharModal = () => renderizar();
      $("#imp", c).onclick = () => imprimir(reciboVenda(venda));
      $("#ok", c).onclick = fecharModal;
    } catch (e) { erro(e); } finally { b.disabled = false; }
  };
  $("#orcamento").onclick = () => {
    if (!pdv.itens.length) { erro(new Error("Adicione ao menos um produto")); return; }
    modalForm("Salvar orçamento", `
      ${pdv.cliente ? `<div class="larg">Cliente: <b>${esc(pdv.cliente.nome)}</b></div>` : `<label class="campo larg"><span>Nome do cliente <span class="ajuda">(se não for cadastrado)</span></span><input name="nome_cliente"></label>`}
      <label class="campo"><span>Validade (dias)</span><input name="validade_dias" type="number" value="10" min="1"></label>
      <div class="campo"><span>Total</span><div class="strong" style="padding-top:9px">${R(totais().total)}</div></div>
      <label class="campo larg"><span>Observação</span><textarea name="observacao" rows="2" placeholder="Ex.: entrega inclusa, prazo de 3 dias"></textarea></label>`,
    async (d) => {
      const o = await POST("/api/orcamentos", { ...d, itens: itensEnvio(), cliente_id: pdv.cliente?.id || null, ...descontoEnvio() });
      zerar();
      setTimeout(() => {
        const c = abrirModal("Orçamento salvo", `<div class="sucesso"><div class="ic">${ic("file")}</div><div class="muted">Orçamento nº ${o.id} · válido até ${dataBR(o.validade)}</div>
          <div class="total-grande">${R(o.total)}</div></div><div class="rodape" style="justify-content:center"><button class="btn primario" id="imp">${ic("printer")}Imprimir orçamento</button><button class="btn" id="ok">Fechar</button></div>`, "440px");
        $("#imp", c).onclick = () => imprimir(reciboOrcamento(o));
        $("#ok", c).onclick = fecharModal;
      }, 0);
    }, { botao: "Salvar orçamento", largura: "520px" });
  };
  paginas.pdv.teclas = (e) => {
    if (e.key === "F4") { e.preventDefault(); $("#finalizar").click(); }
    else if (e.key === "F6") { e.preventDefault(); cli.focar(); }
    else if (e.key === "F8") { e.preventDefault(); $("#desconto").focus(); }
  };
  desenhar();
  $("#busca").focus();
};

// ---------------------------------------------------------- receber de cliente
const rc = { preselecao: null };
paginas["receber-cliente"] = async (el, param) => {
  if (!param) return escolherClienteParaReceber(el);
  const cid = Number(param);
  const [{ cliente, compras }, baixas] = await Promise.all([GET(`/api/clientes/${cid}/debitos`), GET(`/api/baixas?cliente_id=${cid}`)]);
  const parcelas = compras.flatMap((c) => c.parcelas);
  const porId = Object.fromEntries(parcelas.map((p) => [p.id, p]));
  const sel = new Set(rc.preselecao ? rc.preselecao.filter((id) => porId[id]) : parcelas.map((p) => p.id));
  rc.preselecao = null;
  const st = { forma: "DINHEIRO" };
  const livre = Math.max(0, cliente.limite_credito - cliente.saldo_devedor);
  const produtosTxt = (c) => {
    const p = c.produtos.slice(0, 3).map((x) => `${Q(x.quantidade)} ${esc(x.unidade)} ${esc(x.descricao)}`).join(" · ");
    return p + (c.produtos.length > 3 ? ` · e mais ${c.produtos.length - 3}` : "");
  };
  el.innerHTML = `
    <div class="card mb"><div class="card-b linha" style="gap:16px">
      <div class="pessoa" style="flex:1;min-width:240px">${avatar(cliente.nome, "g")}<div><div class="nome" style="font-size:17px">${esc(cliente.nome)}</div>
        <div class="muted small">${[docFmt(cliente.documento), cliente.telefone].filter(Boolean).map(esc).join(" · ") || "sem documento"}</div></div></div>
      <div class="linha" style="gap:28px">
        <div><div class="muted small">Deve no total</div><div class="strong" style="font-size:20px">${R(cliente.saldo_devedor)}</div></div>
        <div><div class="muted small">Vencido</div><div class="strong ${cliente.valor_vencido ? "t-danger" : ""}" style="font-size:20px">${R(cliente.valor_vencido)}</div></div>
        <div class="esconder-m"><div class="muted small">Limite livre</div><div class="strong" style="font-size:20px">${R(livre)}</div></div>
      </div>
      <a class="btn" href="#receber-cliente">${ic("users")}Trocar cliente</a></div></div>
    ${CAIXA ? "" : avisoCaixaFechado("Abra o caixa para registrar o pagamento.")}
    <div class="grid g-main-side">
      <div class="pilha">
        <div class="card"><div class="card-h"><div><h2>Compras em aberto</h2><div class="sub">Marque o que o cliente está pagando — tudo, algumas compras ou só uma parcela</div></div>
          ${parcelas.length ? `<div class="acoes"><label class="check"><input type="checkbox" id="sel-tudo"> Selecionar tudo</label></div>` : ""}</div>
          <div class="card-b">${compras.length ? compras.map((c) => `<div class="compra" data-v="${c.venda_id}">
            <label class="compra-h"><input type="checkbox" class="sel-compra" data-v="${c.venda_id}">
              <div class="txt"><b>Compra nº ${c.venda_id}</b> <span class="muted">· ${dataBR(c.data).slice(0, 10)}</span> ${c.vencido ? badge("VENCIDA") : ""}
                <div class="prod">${produtosTxt(c) || "—"}</div></div>
              <div class="valor">${R(c.restante)}<span>em aberto${c.total ? ` de ${R(c.total)}` : ""}</span></div></label>
            ${c.parcelas.map((p) => `<label class="parcela"><input type="checkbox" class="sel-parc" data-id="${p.id}">
              <span>Parcela ${p.parcela}/${p.total_parcelas} · vence ${dataBR(p.vencimento)} ${p.vencida ? badge("VENCIDA") : ""}</span>
              <span class="muted small">${p.valor_pago ? `já pago ${R(p.valor_pago)}` : ""}</span><span class="v strong">${R(p.restante)}</span></label>`).join("")}
            </div>`).join("") : vazio("checkc", "Este cliente não deve nada", "Todas as contas estão pagas.")}</div></div>
        <div class="card"><div class="card-h"><h2>Pagamentos anteriores</h2></div><div class="card-b flush">
          ${baixas.length ? `<div class="tabela"><table class="tbl-compacta"><thead><tr><th>Data</th><th>Forma</th><th class="num">Valor</th><th class="num">Ficou devendo</th><th>Situação</th><th></th></tr></thead><tbody>
          ${baixas.map((b) => `<tr><td>${dataBR(b.data)}${b.observacao ? `<span class="sub">${esc(b.observacao)}</span>` : ""}</td><td>${forma(b.forma)}</td>
            <td class="num strong">${R(b.valor)}</td><td class="num">${R(b.saldo_apos)}</td><td>${badge(b.status)}</td>
            <td class="acoes"><button class="btn sm icone fantasma bx-imp" data-id="${b.id}" title="Imprimir comprovante" aria-label="Imprimir comprovante">${ic("printer")}</button>
            ${b.status === "ATIVA" ? `<button class="btn sm fantasma bx-est" data-id="${b.id}" title="Desfazer este pagamento">${ic("undo")}Estornar</button>` : ""}</td></tr>`).join("")}
          </tbody></table></div>` : vazio("history", "Nenhum pagamento registrado")}</div></div>
      </div>
      ${parcelas.length ? `<div class="card sticky"><div class="card-h"><h2>Pagamento</h2></div><div class="card-b">
        <div class="linha-total"><span>Total selecionado</span><b id="tot-sel"></b></div>
        <label class="campo mt"><span>Quanto o cliente está pagando</span><div class="prefixo"><b>R$</b><input id="valor-pagar" class="input-xl num" inputmode="decimal" autocomplete="off"></div></label>
        <div class="atalhos-valor mt-s"><button type="button" class="btn sm" data-at="tudo">Tudo selecionado</button><button type="button" class="btn sm" data-at="metade">Metade</button>
          ${cliente.valor_vencido ? `<button type="button" class="btn sm" data-at="vencido">Só o vencido</button>` : ""}</div>
        <div class="campo mt"><span>Forma de pagamento</span><div class="formas" id="formas-rc">${(CONFIG.formas_recebimento || []).map((f) =>
          `<button type="button" class="chip ${f === st.forma ? "on" : ""}" data-f="${f}">${ic(FORMAS[f].icone)}${FORMAS[f].nome}</button>`).join("")}</div></div>
        <label class="campo mt" id="campo-entregue"><span>Dinheiro entregue <span class="ajuda">(opcional, para calcular o troco)</span></span>
          <div class="prefixo"><b>R$</b><input id="valor-entregue" class="num" inputmode="decimal" autocomplete="off"></div></label>
        <div id="troco-rc" class="mt-s"></div>
        <label class="campo mt"><span>Observação</span><input id="obs-rc" placeholder="opcional"></label>
        <hr class="sep"><div class="muted small strong" style="text-transform:uppercase;letter-spacing:.06em">Como vai ficar</div><div id="previa" class="previa mt-s"></div>
        <button class="btn primario lg bloco mt" id="confirmar-rc" ${CAIXA ? "" : "disabled"}>${ic("check")}<span>Confirmar pagamento</span></button>
      </div></div>` : ""}
    </div>`;

  $$(".bx-imp").forEach((b) => (b.onclick = async () => { try { imprimir(reciboBaixa(await GET("/api/baixas/" + b.dataset.id))); } catch (e) { erro(e); } }));
  $$(".bx-est").forEach((b) => (b.onclick = () => {
    const x = baixas.find((y) => String(y.id) === b.dataset.id);
    modalForm("Estornar pagamento", `<div class="aviso-box danger larg">${ic("alert")}<div>O pagamento de <b>${R(x.valor)}</b> (${forma(x.forma)}) de ${dataBR(x.data)} será desfeito:
      a dívida volta para o cliente e o valor sai do caixa.</div></div><label class="campo larg"><span>Motivo</span><input name="motivo" required placeholder="Ex.: lançado no cliente errado"></label>`,
    (d) => POST(`/api/baixas/${x.id}/estornar`, d).then(atualizarCaixa), { botao: "Estornar pagamento", perigo: true, largura: "520px", msg: "Pagamento estornado" });
  }));
  if (!parcelas.length) return;

  // mesma ordem do sistema: quem vence antes é quitado primeiro
  const ordenadas = [...parcelas].sort((a, b) => (a.vencimento < b.vencimento ? -1 : a.vencimento > b.vencimento ? 1 : a.parcela - b.parcela || a.id - b.id));
  const totalSel = () => parcelas.filter((p) => sel.has(p.id)).reduce((s, p) => s + p.restante, 0);
  const valorDigitado = () => ($("#valor-pagar").value.trim() ? centavos($("#valor-pagar").value) : totalSel());
  function atualizar() {
    $$(".sel-parc").forEach((c) => (c.checked = sel.has(Number(c.dataset.id))));
    compras.forEach((c) => {
      const box = $(`.sel-compra[data-v="${c.venda_id}"]`);
      const n = c.parcelas.filter((p) => sel.has(p.id)).length;
      box.checked = n === c.parcelas.length;
      box.indeterminate = n > 0 && n < c.parcelas.length;
      box.closest(".compra").classList.toggle("sel", n > 0);
    });
    const tudo = $("#sel-tudo");
    tudo.checked = sel.size === parcelas.length;
    tudo.indeterminate = sel.size > 0 && sel.size < parcelas.length;
    const total = totalSel();
    $("#tot-sel").textContent = R(total);
    $("#valor-pagar").placeholder = paraCampo(total);
    const valor = valorDigitado();
    $("#campo-entregue").classList.toggle("oculto", st.forma !== "DINHEIRO");
    const entregue = st.forma === "DINHEIRO" && $("#valor-entregue").value.trim() ? centavos($("#valor-entregue").value) : null;
    $("#troco-rc").innerHTML = entregue != null && valor > 0
      ? (entregue >= valor ? `<div class="destaque-ok"><span>Troco</span><b>${R(entregue - valor)}</b></div>`
        : `<div class="destaque-falta"><span>Entregue é menor que o valor</span><span>${R(valor - entregue)}</span></div>`) : "";
    const prev = $("#previa"), botao = $("#confirmar-rc");
    let ok = true;
    if (!sel.size) { prev.innerHTML = `<div class="muted">Marque ao menos uma parcela.</div>`; ok = false; }
    else if (!(valor > 0)) { prev.innerHTML = `<div class="t-danger">Informe um valor válido.</div>`; ok = false; }
    else if (valor > total) { prev.innerHTML = `<div class="t-danger">O valor passa do total selecionado (${R(total)}).</div>`; ok = false; }
    else {
      let resta = valor;
      const linhas = [];
      for (const p of ordenadas) {
        if (!sel.has(p.id) || resta <= 0) continue;
        const parte = Math.min(resta, p.restante);
        resta -= parte;
        linhas.push(`<div class="it"><span>Compra ${p.venda_id} · parc. ${p.parcela}/${p.total_parcelas}</span><span>${parte === p.restante
          ? `<span class="t-ok strong">quita ${R(parte)}</span>` : `abate ${R(parte)} <span class="muted">(fica ${R(p.restante - parte)})</span>`}</span></div>`);
      }
      prev.innerHTML = linhas.join("") + `<div class="linha-total grande"><span>Cliente vai dever</span><b>${R(cliente.saldo_devedor - valor)}</b></div>`;
    }
    if (entregue != null && !(entregue >= valor)) ok = false;
    botao.disabled = !ok || !CAIXA;
    $("span", botao).textContent = ok ? `Confirmar pagamento de ${R(valor)}` : "Confirmar pagamento";
  }
  $$(".sel-parc").forEach((c) => (c.onchange = () => { const id = Number(c.dataset.id); if (c.checked) sel.add(id); else sel.delete(id); atualizar(); }));
  $$(".sel-compra").forEach((c) => (c.onchange = () => {
    const compra = compras.find((x) => String(x.venda_id) === c.dataset.v);
    compra.parcelas.forEach((p) => (c.checked ? sel.add(p.id) : sel.delete(p.id)));
    atualizar();
  }));
  $("#sel-tudo").onchange = (e) => { parcelas.forEach((p) => (e.target.checked ? sel.add(p.id) : sel.delete(p.id))); atualizar(); };
  $("#valor-pagar").oninput = atualizar;
  $("#valor-entregue").oninput = atualizar;
  $$("[data-at]").forEach((b) => (b.onclick = () => {
    if (b.dataset.at === "vencido") { sel.clear(); parcelas.filter((p) => p.vencida).forEach((p) => sel.add(p.id)); $("#valor-pagar").value = ""; }
    else if (b.dataset.at === "tudo") $("#valor-pagar").value = "";
    else $("#valor-pagar").value = paraCampo(Math.round(totalSel() / 2));
    atualizar();
  }));
  $$("#formas-rc .chip").forEach((b) => (b.onclick = () => {
    st.forma = b.dataset.f;
    $$("#formas-rc .chip").forEach((x) => x.classList.toggle("on", x === b));
    atualizar();
  }));
  $("#confirmar-rc").onclick = async () => {
    const b = $("#confirmar-rc");
    b.disabled = true;
    try {
      const dados = { contas: [...sel], forma: st.forma, observacao: $("#obs-rc").value };
      if ($("#valor-pagar").value.trim()) dados.valor = $("#valor-pagar").value;
      if (st.forma === "DINHEIRO" && $("#valor-entregue").value.trim()) dados.valor_recebido = $("#valor-entregue").value;
      const baixa = await POST(`/api/clientes/${cid}/baixa`, dados);
      await atualizarCaixa();
      const c = abrirModal("Pagamento registrado", `<div class="sucesso"><div class="ic">${ic("check")}</div><div class="muted">${esc(baixa.cliente)} pagou</div>
        <div class="total-grande">${R(baixa.valor)}</div><div class="muted mt-s">${forma(baixa.forma)}</div>
        ${baixa.troco ? `<div class="destaque-ok mt" style="justify-content:center;gap:12px"><span>Troco</span><b>${R(baixa.troco)}</b></div>` : ""}
        <p class="sec">${baixa.saldo_apos ? `Ainda deve <b>${R(baixa.saldo_apos)}</b>` : `<b class="t-ok">Conta quitada!</b>`}</p></div>
        <div class="rodape" style="justify-content:center"><button class="btn" id="imp">${ic("printer")}Imprimir comprovante</button><button class="btn primario" id="ok" autofocus>Concluir</button></div>`, "460px");
      aoFecharModal = () => renderizar();
      $("#imp", c).onclick = () => imprimir(reciboBaixa(baixa));
      $("#ok", c).onclick = fecharModal;
    } catch (e) { erro(e); b.disabled = false; }
  };
  atualizar();
};

async function escolherClienteParaReceber(el) {
  const devedores = await GET("/api/clientes?devendo=1");
  const total = devedores.reduce((s, c) => s + c.saldo_devedor, 0);
  el.innerHTML = `
    <div class="card mb"><div class="card-b"><h2 class="mb">Quem está pagando?</h2>
      <div class="ac busca grande">${ic("search")}<input id="busca-cli" placeholder="Digite o nome, CPF/CNPJ ou telefone do cliente" autocomplete="off"></div></div></div>
    <div class="card"><div class="card-h"><div><h2>Clientes com conta em aberto</h2><div class="sub">${devedores.length} cliente${devedores.length === 1 ? "" : "s"} · ${R(total)} a receber</div></div></div>
      <div class="card-b flush">${devedores.length ? `<div class="tabela"><table><thead><tr><th>Cliente</th><th>Telefone</th><th class="num">Em aberto</th><th class="num">Vencido</th><th></th></tr></thead><tbody>
      ${devedores.map((c) => `<tr><td><div class="pessoa">${avatar(c.nome)}<div><div class="nome">${esc(c.nome)}</div><span class="sub">${esc(docFmt(c.documento) || "")}</span></div></div></td>
        <td>${esc(c.telefone)}</td><td class="num strong">${R(c.saldo_devedor)}</td><td class="num ${c.valor_vencido ? "t-danger strong" : "muted"}">${R(c.valor_vencido)}</td>
        <td class="acoes"><a class="btn sm primario" href="#receber-cliente/${c.id}">${ic("wallet")}Receber</a></td></tr>`).join("")}</tbody></table></div>`
        : vazio("checkc", "Nenhum cliente devendo", "Quando houver vendas no crediário, elas aparecem aqui.")}</div></div>`;
  autocompletar($("#busca-cli"), {
    buscar: async (t) => (await GET("/api/clientes?busca=" + encodeURIComponent(t))).slice(0, 12),
    item: (c) => `${avatar(c.nome)}<div class="txt"><b>${esc(c.nome)}</b><span>${esc(docFmt(c.documento) || c.telefone || "—")}</span></div>
      <div class="dir">${c.saldo_devedor ? `<b>${R(c.saldo_devedor)}</b><span>em aberto</span>` : "<span>sem débitos</span>"}</div>`,
    escolher: (c) => (location.hash = "receber-cliente/" + c.id),
    minimo: 1, textoVazio: "Nenhum cliente encontrado",
  });
  $("#busca-cli").focus();
}

// ------------------------------------------------------------------ vendas
function filtroPeriodo(estado, aoMudar) {
  const presets = [["hoje", "Hoje"], ["7", "7 dias"], ["30", "30 dias"], ["mes", "Este mês"]];
  const html = `<div class="filtros">${segmentado("periodo", presets, estado.preset)}
    <label class="campo" style="min-width:150px"><span>De</span><input type="date" id="p-ini" value="${estado.inicio}"></label>
    <label class="campo" style="min-width:150px"><span>Até</span><input type="date" id="p-fim" value="${estado.fim}"></label></div>`;
  const ligar = () => {
    aoSegmentar("periodo", (v) => {
      const h = CONFIG.hoje;
      Object.assign(estado, { preset: v, fim: h, inicio: v === "hoje" ? h : v === "mes" ? h.slice(0, 8) + "01" : somarDias(h, -(Number(v) - 1)) });
      aoMudar();
    });
    $("#p-ini").onchange = (e) => { Object.assign(estado, { inicio: e.target.value, preset: "" }); aoMudar(); };
    $("#p-fim").onchange = (e) => { Object.assign(estado, { fim: e.target.value, preset: "" }); aoMudar(); };
  };
  return { html, ligar };
}
const periodoVendas = { preset: "hoje", inicio: "", fim: "" };
paginas.vendas = async (el) => {
  if (!periodoVendas.inicio) periodoVendas.inicio = periodoVendas.fim = CONFIG.hoje;
  const lista = await GET(`/api/vendas?inicio=${periodoVendas.inicio}&fim=${periodoVendas.fim}`);
  const validas = lista.filter((v) => v.status === "CONCLUIDA");
  const liquido = validas.reduce((s, v) => s + v.total - v.total_devolvido, 0);
  const f = filtroPeriodo(periodoVendas, renderizar);
  el.innerHTML = `${f.html}
    <div class="grid g-3 mb">${kpi({ rot: "Vendas no período", val: validas.length, icone: "receipt" })}${kpi({ rot: "Valor líquido", val: R(liquido), icone: "trend", tom: "ok" })}
      ${kpi({ rot: "Canceladas", val: lista.length - validas.length, icone: "x", tom: "danger" })}</div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Pagamento</th><th class="num">Total</th><th>Situação</th><th></th></tr></thead><tbody>
    ${lista.map((v) => `<tr><td class="strong">${v.id}</td><td>${dataBR(v.data)}</td><td>${esc(v.cliente || "Consumidor")}</td>
      <td>${esc((v.formas || "").split(", ").map(forma).join(", "))}</td>
      <td class="num strong">${R(v.total)}${v.total_devolvido ? `<span class="sub t-danger">devolvido ${R(v.total_devolvido)}</span>` : ""}</td>
      <td>${badge(v.status)}</td><td class="acoes"><button class="btn sm ver" data-id="${v.id}">${ic("eye")}Ver</button></td></tr>`).join("")}</tbody></table>`
      : vazio("receipt", "Nenhuma venda no período", "", `<a class="btn sm primario" href="#pdv">Nova venda</a>`)}</div></div>`;
  f.ligar();
  $$(".ver").forEach((b) => (b.onclick = () => verVenda(b.dataset.id).catch(erro)));
};

async function verVenda(id) {
  const v = await GET("/api/vendas/" + id);
  const c = abrirModal(`Venda nº ${v.id}`, `
    <div class="linha entre mb"><div><div class="strong">${esc(v.cliente || "Consumidor")}</div><div class="muted small">${dataBR(v.data)}</div></div>${badge(v.status)}</div>
    ${v.status === "CANCELADA" ? `<div class="aviso-box danger mb">${ic("x")}<div>Cancelada em ${dataBR(v.cancelada_em)}: ${esc(v.motivo_cancelamento)}</div></div>` : ""}
    <div class="card"><div class="tabela"><table class="tbl-compacta"><thead><tr><th>Produto</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th></tr></thead><tbody>
    ${v.itens.map((i) => `<tr><td>${esc(i.descricao)}${i.quantidade_devolvida ? `<span class="sub t-danger">devolvido ${Q(i.quantidade_devolvida)} (${R(i.valor_devolvido)})</span>` : ""}</td>
      <td class="num">${Q(i.quantidade)} ${esc(i.unidade)}</td><td class="num">${R(i.preco_unitario)}</td><td class="num">${R(i.total)}</td></tr>`).join("")}</tbody></table></div></div>
    <div class="grid g-2 mt"><div>
      ${v.pagamentos.map((p) => `<div class="linha-total"><span>${forma(p.forma)}</span><b>${R(p.valor)}</b></div>`).join("")}
      ${v.troco ? `<div class="linha-total"><span>Troco</span><b>${R(v.troco)}</b></div>` : ""}</div>
      <div><div class="linha-total"><span>Subtotal</span><b>${R(v.subtotal)}</b></div>${v.desconto ? `<div class="linha-total"><span>Desconto</span><b>- ${R(v.desconto)}</b></div>` : ""}
      <div class="linha-total grande"><span>Total</span><b>${R(v.total)}</b></div>${v.total_devolvido ? `<div class="linha-total t-danger"><span>Devolvido</span><b>- ${R(v.total_devolvido)}</b></div>` : ""}</div></div>
    ${v.parcelas.length ? `<h3 class="mt mb">Parcelas do crediário</h3><div class="card"><table class="tbl-compacta"><tbody>
      ${v.parcelas.map((p) => `<tr><td>${p.parcela}/${p.total_parcelas}</td><td>vence ${dataBR(p.vencimento)}</td><td class="num">${R(p.valor)}</td><td class="num muted">pago ${R(p.valor_pago)}</td><td>${badge(p.status)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${v.devolucoes.length ? `<h3 class="mt mb">Devoluções</h3>${v.devolucoes.map((d) => `<div class="muted small">${dataBR(d.data)} — ${R(d.valor)}: abatido do crediário ${R(d.valor_abatido)}, devolvido ${R(d.valor_reembolsado)} em ${forma(d.forma_reembolso)} ${d.motivo ? "· " + esc(d.motivo) : ""}</div>`).join("")}` : ""}
    <div class="rodape"><button class="btn" id="imp">${ic("printer")}Imprimir</button>
      ${v.status === "CONCLUIDA" && v.itens.some((i) => i.quantidade > i.quantidade_devolvida) ? `<button class="btn" id="dev">${ic("undo")}Devolução de itens</button>` : ""}
      ${v.status === "CONCLUIDA" ? `<button class="btn perigo" id="canc">${ic("x")}Cancelar venda</button>` : ""}</div>`, "760px");
  $("#imp", c).onclick = () => imprimir(reciboVenda(v));
  if ($("#canc", c)) $("#canc", c).onclick = () => modalForm(`Cancelar venda nº ${v.id}`, `<div class="aviso-box danger larg">${ic("alert")}<div>Os produtos voltam ao estoque, as parcelas são canceladas e o valor recebido sai do caixa.</div></div>
      <label class="campo larg"><span>Motivo do cancelamento</span><input name="motivo" required></label>`,
    (d) => POST(`/api/vendas/${v.id}/cancelar`, d).then(atualizarCaixa), { botao: "Cancelar venda", perigo: true, largura: "520px", msg: "Venda cancelada" });
  if ($("#dev", c)) $("#dev", c).onclick = () => {
    const itens = v.itens.filter((i) => i.quantidade > i.quantidade_devolvida);
    modalForm(`Devolução — venda nº ${v.id}`, `<div class="larg card"><table class="tbl-compacta"><thead><tr><th>Produto</th><th class="num">Pode devolver</th><th class="num">Devolver</th></tr></thead><tbody>
      ${itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade - i.quantidade_devolvida)} ${esc(i.unidade)}</td>
        <td class="num"><input name="item_${i.id}" value="0" class="num" style="width:90px;height:32px" inputmode="decimal"></td></tr>`).join("")}</tbody></table></div>
      <label class="campo"><span>Motivo</span><input name="motivo"></label>
      <label class="campo"><span>Devolver o dinheiro em</span><select name="forma_reembolso">${opcoes((CONFIG.formas_reembolso || []).map((f) => [f, forma(f)]))}</select></label>
      <div class="aviso-box info larg">${ic("info")}<div>Se o cliente ainda deve parte desta compra no crediário, o valor devolvido abate primeiro essa dívida; só o que sobrar é devolvido em dinheiro/PIX.</div></div>`,
    async (d) => {
      const lista = itens.filter((i) => milesimos(d["item_" + i.id]) > 0).map((i) => ({ item_id: i.id, quantidade: d["item_" + i.id] }));
      const r = await POST(`/api/vendas/${v.id}/devolucao`, { itens: lista, motivo: d.motivo, forma_reembolso: d.forma_reembolso });
      await atualizarCaixa();
      avisar(`Devolução de ${R(r.valor)} registrada (abatido ${R(r.valor_abatido)}, devolvido ${R(r.valor_reembolsado)})`);
    }, { botao: "Registrar devolução", largura: "640px" });
  };
}

// --------------------------------------------------------------- orçamentos
let statusOrc = "ABERTO";
paginas.orcamentos = async (el) => {
  const lista = await GET("/api/orcamentos" + (statusOrc ? "?status=" + statusOrc : ""));
  el.innerHTML = `<div class="filtros">${segmentado("st-orc", [["ABERTO", "Em aberto"], ["CONVERTIDO", "Viraram venda"], ["CANCELADO", "Cancelados"], ["", "Todos"]], statusOrc)}
      <a class="btn primario" href="#pdv" style="margin-left:auto">${ic("plus")}Novo orçamento</a></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Validade</th><th class="num">Total</th><th>Situação</th><th></th></tr></thead><tbody>
    ${lista.map((o) => `<tr><td class="strong">${o.id}</td><td>${dataBR(o.data)}</td><td>${esc(o.cliente || o.nome_cliente || "—")}</td>
      <td>${dataBR(o.validade)} ${o.status === "ABERTO" && o.validade < CONFIG.hoje ? badge("VENCIDO") : ""}</td>
      <td class="num strong">${R(o.total)}</td><td>${badge(o.status)}${o.venda_id ? `<span class="sub">venda nº ${o.venda_id}</span>` : ""}</td>
      <td class="acoes"><button class="btn sm ver" data-id="${o.id}">${ic("eye")}Ver</button></td></tr>`).join("")}</tbody></table>`
      : vazio("file", "Nenhum orçamento aqui", "Monte os itens na tela Vender e clique em “Salvar como orçamento”.", `<a class="btn sm primario" href="#pdv">Fazer orçamento</a>`)}</div></div>`;
  aoSegmentar("st-orc", (v) => { statusOrc = v; renderizar(); });
  $$(".ver").forEach((b) => (b.onclick = () => verOrcamento(b.dataset.id).catch(erro)));
};

async function verOrcamento(id) {
  const o = await GET("/api/orcamentos/" + id);
  const c = abrirModal(`Orçamento nº ${o.id}`, `
    <div class="linha entre mb"><div><div class="strong">${esc(o.cliente || o.nome_cliente || "Cliente não informado")}</div>
      <div class="muted small">${dataBR(o.data)} · válido até ${dataBR(o.validade)}</div></div><div class="linha">${o.vencido ? badge("VENCIDO") : ""}${badge(o.status)}</div></div>
    <div class="card"><div class="tabela"><table class="tbl-compacta"><thead><tr><th>Produto</th><th class="num">Qtd</th><th class="num">Unit.</th><th class="num">Total</th><th class="num">Estoque hoje</th></tr></thead><tbody>
    ${o.itens.map((i) => `<tr><td>${esc(i.descricao)}</td><td class="num">${Q(i.quantidade)} ${esc(i.unidade)}</td><td class="num">${R(i.preco_unitario)}</td><td class="num">${R(i.total)}</td>
      <td class="num ${i.estoque < i.quantidade ? "t-danger strong" : "muted"}">${Q(i.estoque)}</td></tr>`).join("")}</tbody></table></div></div>
    <div class="mt" style="max-width:300px;margin-left:auto"><div class="linha-total"><span>Subtotal</span><b>${R(o.subtotal)}</b></div>
      ${o.desconto ? `<div class="linha-total"><span>Desconto</span><b>- ${R(o.desconto)}</b></div>` : ""}<div class="linha-total grande"><span>Total</span><b>${R(o.total)}</b></div></div>
    ${o.observacao ? `<p class="sec">${esc(o.observacao)}</p>` : ""}
    <div class="rodape"><button class="btn" id="imp">${ic("printer")}Imprimir</button>
      ${o.status === "ABERTO" ? `<button class="btn perigo" id="canc">${ic("x")}Cancelar orçamento</button>` : ""}
      ${o.status === "ABERTO" && !o.vencido ? `<button class="btn primario" id="conv">${ic("cart")}Transformar em venda</button>` : ""}</div>`, "760px");
  $("#imp", c).onclick = () => imprimir(reciboOrcamento(o));
  if ($("#canc", c)) $("#canc", c).onclick = async () => {
    if (!(await confirmar("Cancelar orçamento", `Cancelar o orçamento nº ${o.id}?`, { botao: "Cancelar orçamento", perigo: true }))) return;
    try { await POST(`/api/orcamentos/${o.id}/cancelar`); avisar("Orçamento cancelado"); renderizar(); } catch (e) { erro(e); }
  };
  if ($("#conv", c)) $("#conv", c).onclick = () => {
    let cliente = null;
    const c2 = abrirModal(`Venda do orçamento nº ${o.id}`, `<div class="linha entre"><span class="sec">Total combinado</span><span class="total-grande">${R(o.total)}</span></div>
      <div class="campo mt"><span>Cliente</span><div id="cli"></div></div><div class="campo mt"><span>Pagamento</span><div id="pg"></div></div>
      <div class="rodape"><button class="btn" data-c>Voltar</button><button class="btn primario" id="ok">${ic("check")}Finalizar venda</button></div>`, "560px");
    let pag = null;
    seletorCliente($("#cli", c2), { inicial: o.cliente_id, aoMudar: (x) => { cliente = x; if (pag) pag.atualizar(); } });
    pag = widgetPagamento($("#pg", c2), { obterTotal: () => o.total, obterCliente: () => cliente });
    $("[data-c]", c2).onclick = fecharModal;
    $("#ok", c2).onclick = async () => {
      try {
        const venda = await POST(`/api/orcamentos/${o.id}/converter`, { cliente_id: cliente?.id || null, ...pag.dados() });
        await atualizarCaixa();
        const c3 = abrirModal("Venda concluída", `<div class="sucesso"><div class="ic">${ic("check")}</div><div class="muted">Venda nº ${venda.id}</div><div class="total-grande">${R(venda.total)}</div>
          ${venda.troco ? `<div class="destaque-ok mt" style="justify-content:center;gap:12px"><span>Troco</span><b>${R(venda.troco)}</b></div>` : ""}</div>
          <div class="rodape" style="justify-content:center"><button class="btn" id="imp">${ic("printer")}Imprimir comprovante</button><button class="btn primario" id="fim">Fechar</button></div>`, "440px");
        aoFecharModal = () => renderizar();
        $("#imp", c3).onclick = () => imprimir(reciboVenda(venda));
        $("#fim", c3).onclick = fecharModal;
      } catch (e) { erro(e); }
    };
  };
}

// ------------------------------------------------------------------- caixa
const nomeTipo = (t) => t.replace(/_/g, " ").toLowerCase().replace(/^./, (x) => x.toUpperCase());
function tabelaCaixa(s) {
  return `<div class="tabela"><table class="tbl-compacta"><thead><tr><th>Quando</th><th>Tipo</th><th>Forma</th><th>Descrição</th><th class="num">Valor</th></tr></thead><tbody>
    <tr><td>${dataBR(s.abertura)}</td><td>Abertura</td><td>Dinheiro</td><td>Fundo de troco</td><td class="num">${R(s.valor_inicial)}</td></tr>
    ${s.movimentos.map((m) => `<tr><td>${dataBR(m.data)}</td><td>${esc(nomeTipo(m.tipo))}</td>
      <td>${forma(m.forma)}</td><td>${esc(m.descricao)}</td><td class="num strong ${m.valor < 0 ? "t-danger" : ""}">${R(m.valor)}</td></tr>`).join("")}</tbody></table></div>`;
}
function totaisCaixa(s) {
  const t = s.totais_por_forma;
  return `<div class="grid g-4">${kpi({ rot: "Dinheiro na gaveta", val: R(s.saldo_dinheiro), det: `fundo de troco ${R(s.valor_inicial)}`, icone: "banknote", tom: "ok" })}
    ${["PIX", "DEBITO", "CREDITO"].map((f) => kpi({ rot: FORMAS[f].nome, val: R(t[f] || 0), icone: FORMAS[f].icone, tom: "info" })).join("")}</div>`;
}
paginas.caixa = async (el) => {
  const { caixa, sessoes } = await GET("/api/caixa");
  const fechadas = sessoes.filter((s) => s.status === "FECHADO");
  el.innerHTML = `
    ${caixa ? `<div class="linha entre mb"><div><h2 style="font-size:18px">Caixa aberto</h2><div class="muted">desde ${dataBR(caixa.abertura)}${caixa.operador ? " · " + esc(caixa.operador) : ""}</div></div>
        <div class="linha"><button class="btn" id="suprimento">${ic("down")}Suprimento</button><button class="btn" id="sangria">${ic("up")}Sangria</button>
        <button class="btn primario" id="fechar">${ic("lock")}Fechar caixa</button></div></div>
      ${totaisCaixa(caixa)}
      <div class="card mt"><div class="card-h"><h2>Movimentos deste caixa</h2></div>${tabelaCaixa(caixa)}</div>`
    : `<div class="card" style="max-width:520px;margin:0 auto"><div class="card-b" style="padding:28px">
        <div class="vazio" style="padding:0 0 16px"><div class="ic">${ic("lock")}</div><b>O caixa está fechado</b>Informe o dinheiro que está na gaveta para o troco e abra o caixa.</div>
        <form id="abrir" class="form"><label class="campo"><span>Fundo de troco</span><div class="prefixo"><b>R$</b><input name="valor_inicial" value="0,00" class="num" inputmode="decimal"></div></label>
        <label class="campo"><span>Operador</span><input name="operador" placeholder="opcional"></label>
        <button class="btn primario lg larg" type="submit">${ic("unlock")}Abrir caixa</button></form></div></div>`}
    <div class="card mt"><div class="card-h"><h2>Caixas anteriores</h2></div><div class="card-b flush">
    ${fechadas.length ? `<div class="tabela"><table><thead><tr><th>Nº</th><th>Abertura</th><th>Fechamento</th><th>Operador</th><th class="num">Esperado</th><th class="num">Contado</th><th class="num">Diferença</th><th></th></tr></thead><tbody>
    ${fechadas.map((s) => `<tr><td>${s.id}</td><td>${dataBR(s.abertura)}</td><td>${dataBR(s.fechamento)}</td><td>${esc(s.operador)}</td>
      <td class="num">${R(s.valor_esperado)}</td><td class="num">${R(s.valor_contado)}</td>
      <td class="num strong ${s.diferenca < 0 ? "t-danger" : s.diferenca > 0 ? "t-warn" : "t-ok"}">${s.diferenca ? R(s.diferenca) : "Conferido"}</td>
      <td class="acoes"><button class="btn sm ver" data-id="${s.id}">${ic("eye")}Ver</button></td></tr>`).join("")}</tbody></table></div>` : vazio("history", "Nenhum caixa fechado ainda")}</div></div>`;
  $$(".ver").forEach((b) => (b.onclick = async () => {
    try { const s = await GET("/api/caixa/" + b.dataset.id); abrirModal(`Caixa nº ${s.id}`, totaisCaixa(s) + `<div class="card mt">${tabelaCaixa(s)}</div>`, "960px"); } catch (e) { erro(e); }
  }));
  if (!caixa) {
    $("#abrir").onsubmit = async (e) => {
      e.preventDefault();
      try { await POST("/api/caixa/abrir", dadosForm(e.target)); await atualizarCaixa(); avisar("Caixa aberto. Boas vendas!"); renderizar(); } catch (err) { erro(err); }
    };
    return;
  }
  const mov = (tipo, titulo, explic) => () => modalForm(titulo, `<p class="sec larg" style="margin:0">${explic}</p>
    <label class="campo"><span>Valor</span><div class="prefixo"><b>R$</b><input name="valor" required class="num" inputmode="decimal"></div></label><label class="campo"><span>Motivo</span><input name="motivo"></label>`,
  (d) => POST("/api/caixa/" + tipo, d).then(atualizarCaixa), { botao: "Confirmar", largura: "520px", msg: "Lançado no caixa" });
  $("#sangria").onclick = mov("sangria", "Sangria", "Retirada de dinheiro da gaveta (ex.: levar para o cofre ou banco).");
  $("#suprimento").onclick = mov("suprimento", "Suprimento", "Colocar mais dinheiro na gaveta para troco.");
  $("#fechar").onclick = () => modalForm("Fechar caixa", `<p class="sec larg" style="margin:0">Conte o dinheiro da gaveta e informe o total. O sistema mostra se sobrou ou faltou.</p>
    <label class="campo"><span>Dinheiro contado</span><div class="prefixo"><b>R$</b><input name="valor_contado" required class="num" inputmode="decimal"></div></label>
    <label class="campo"><span>Observação</span><input name="observacao"></label>`,
  async (d) => {
    const s = await POST("/api/caixa/fechar", d);
    await atualizarCaixa();
    setTimeout(() => abrirModal("Caixa fechado", `<div class="sucesso"><div class="ic" style="${s.diferenca ? "background:var(--warn-soft);color:var(--warn)" : ""}">${ic(s.diferenca ? "alert" : "check")}</div>
      <div class="grid g-2" style="max-width:340px;margin:0 auto"><div><div class="muted small">Esperado</div><b>${R(s.valor_esperado)}</b></div><div><div class="muted small">Contado</div><b>${R(s.valor_contado)}</b></div></div>
      <p class="strong ${s.diferenca ? "t-danger" : "t-ok"}" style="font-size:18px">${s.diferenca === 0 ? "Caixa conferido, sem diferença." : s.diferenca > 0 ? `Sobra de ${R(s.diferenca)}` : `Falta de ${R(-s.diferenca)}`}</p></div>`, "460px"), 0);
  }, { botao: "Fechar caixa", largura: "520px" });
};

// ----------------------------------------------------------------- produtos
const filtroProd = { busca: "", categoria: "", baixo: false };
function buscaAoVivo(input, aplicar) {
  let t;
  input.oninput = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      aplicar(input.value);
      await renderizar();
      const i = $("#" + input.id);
      if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
    }, 300);
  };
}
paginas.produtos = async (el) => {
  const [lista, cats] = await Promise.all([
    GET(`/api/produtos?busca=${encodeURIComponent(filtroProd.busca)}&categoria=${encodeURIComponent(filtroProd.categoria)}&estoque_baixo=${filtroProd.baixo ? 1 : 0}`),
    GET("/api/produtos/categorias")]);
  el.innerHTML = `<div class="filtros">
      <label class="campo" style="flex:1;min-width:220px"><span>Buscar</span><div class="busca">${ic("search")}<input id="f-busca" value="${esc(filtroProd.busca)}" placeholder="Nome, código ou código de barras"></div></label>
      <label class="campo"><span>Categoria</span><select id="f-cat"><option value="">Todas</option>${opcoes(cats.map((c) => [c, c]), filtroProd.categoria)}</select></label>
      <label class="check" style="height:38px"><input type="checkbox" id="f-baixo" ${filtroProd.baixo ? "checked" : ""}> Só estoque baixo</label>
      <button class="btn primario" id="novo" style="margin-left:auto">${ic("plus")}Novo produto</button></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Produto</th><th>Categoria</th><th class="num">Custo</th><th class="num">Venda</th><th class="num">Margem</th><th class="num">Estoque</th><th></th></tr></thead><tbody>
    ${lista.map((p) => `<tr class="${p.ativo ? "" : "inativo"}"><td><b>${esc(p.nome)}</b> ${p.ativo ? "" : badge("INATIVO")}<span class="sub">${esc(p.codigo)}${p.codigo_barras ? " · " + esc(p.codigo_barras) : ""}${p.localizacao ? " · " + esc(p.localizacao) : ""}</span></td>
      <td>${p.categoria ? `<span class="badge neutro">${esc(p.categoria)}</span>` : ""}</td>
      <td class="num">${R(p.preco_custo)}</td><td class="num strong">${R(p.preco_venda)}</td>
      <td class="num">${p.preco_custo ? (((p.preco_venda - p.preco_custo) / p.preco_custo) * 100).toFixed(1).replace(".", ",") + "%" : "—"}</td>
      <td class="num"><b class="${p.estoque === 0 ? "t-danger" : p.estoque <= p.estoque_minimo ? "t-warn" : ""}">${Q(p.estoque)} ${esc(p.unidade)}</b><span class="sub">mín. ${Q(p.estoque_minimo)}</span></td>
      <td class="acoes"><button class="btn sm icone fantasma ed" data-id="${p.id}" title="Editar" aria-label="Editar">${ic("pencil")}</button>
        <button class="btn sm icone fantasma aj" data-id="${p.id}" title="Inventário (ajustar pela contagem)" aria-label="Inventário">${ic("clipboard")}</button>
        <button class="btn sm icone fantasma pe" data-id="${p.id}" title="Registrar perda/quebra" aria-label="Registrar perda">${ic("alert")}</button>
        <a class="btn sm icone fantasma" href="#movimentos/${p.id}" title="Histórico de movimentação" aria-label="Histórico">${ic("history")}</a></td></tr>`).join("")}</tbody></table>`
      : vazio("package", "Nenhum produto encontrado", "", `<button class="btn sm primario" id="novo2">${ic("plus")}Cadastrar produto</button>`)}</div></div>`;
  buscaAoVivo($("#f-busca"), (v) => (filtroProd.busca = v));
  $("#f-cat").onchange = (e) => { filtroProd.categoria = e.target.value; renderizar(); };
  $("#f-baixo").onchange = (e) => { filtroProd.baixo = e.target.checked; renderizar(); };
  $("#novo").onclick = () => formProduto(null, cats).catch(erro);
  if ($("#novo2")) $("#novo2").onclick = () => formProduto(null, cats).catch(erro);
  const porId = Object.fromEntries(lista.map((p) => [p.id, p]));
  $$(".ed").forEach((b) => (b.onclick = () => formProduto(porId[b.dataset.id], cats).catch(erro)));
  $$(".aj").forEach((b) => (b.onclick = () => {
    const p = porId[b.dataset.id];
    modalForm(`Inventário — ${p.nome}`, `<div class="aviso-box info larg">${ic("info")}<div>No sistema há <b>${Q(p.estoque)} ${esc(p.unidade)}</b>. Informe quanto você contou; a diferença é lançada automaticamente.</div></div>
      <label class="campo"><span>Quantidade contada</span><input name="quantidade" required class="num" inputmode="decimal"></label>
      <label class="campo"><span>Motivo</span><input name="motivo" required value="Contagem de inventário"></label>`,
    (d) => POST(`/api/produtos/${p.id}/ajuste`, d), { botao: "Ajustar estoque", largura: "540px", msg: "Estoque ajustado" });
  }));
  $$(".pe").forEach((b) => (b.onclick = () => {
    const p = porId[b.dataset.id];
    modalForm(`Registrar perda — ${p.nome}`, `<p class="sec larg" style="margin:0">Estoque atual: <b>${Q(p.estoque)} ${esc(p.unidade)}</b></p>
      <label class="campo"><span>Quantidade perdida</span><input name="quantidade" required class="num" inputmode="decimal"></label>
      <label class="campo"><span>Motivo</span><input name="motivo" required placeholder="quebra, avaria, vencido..."></label>`,
    (d) => POST(`/api/produtos/${p.id}/perda`, d), { botao: "Registrar perda", perigo: true, largura: "540px", msg: "Perda registrada" });
  }));
};

async function formProduto(p, cats) {
  const fornecedores = await GET("/api/fornecedores?ativos=1");
  const novo = !p;
  p = p || { unidade: "UN", ativo: 1 };
  const form = modalForm(novo ? "Novo produto" : "Editar produto", `
    <div class="form-sec">Identificação</div>
    <label class="campo larg"><span>Nome / descrição</span><input name="nome" required value="${esc(p.nome)}" placeholder="Ex.: Cimento CP-II 50kg"></label>
    <label class="campo"><span>Código interno <span class="ajuda">(vazio = automático)</span></span><input name="codigo" value="${esc(p.codigo)}"></label>
    <label class="campo"><span>Código de barras</span><input name="codigo_barras" value="${esc(p.codigo_barras)}"></label>
    <label class="campo"><span>Categoria</span><input name="categoria" list="cats" value="${esc(p.categoria)}" placeholder="Ex.: Cimento, Elétrica"><datalist id="cats">${cats.map((x) => `<option value="${esc(x)}">`).join("")}</datalist></label>
    <label class="campo"><span>Unidade de venda</span><select name="unidade">${opcoes(Object.entries(CONFIG.unidades).map(([k, n]) => [k, `${k} — ${n}`]), p.unidade)}</select></label>
    <div class="form-sec">Preços</div>
    <label class="campo"><span>Preço de custo</span><div class="prefixo"><b>R$</b><input name="preco_custo" class="num" value="${p.preco_custo != null ? paraCampo(p.preco_custo) : ""}" inputmode="decimal"></div></label>
    <label class="campo"><span>Margem <span class="ajuda">(calcula o preço de venda)</span></span><div class="prefixo"><b>%</b><input id="margem" class="num" inputmode="decimal"></div></label>
    <label class="campo larg"><span>Preço de venda</span><div class="prefixo"><b>R$</b><input name="preco_venda" required class="num" value="${p.preco_venda != null ? paraCampo(p.preco_venda) : ""}" inputmode="decimal"></div></label>
    <div class="form-sec">Estoque</div>
    ${novo ? `<label class="campo"><span>Estoque inicial</span><input name="estoque_inicial" value="0" class="num" inputmode="decimal"></label>` : ""}
    <label class="campo"><span>Estoque mínimo <span class="ajuda">(avisa quando baixar)</span></span><input name="estoque_minimo" class="num" value="${p.estoque_minimo != null ? qtdCampo(p.estoque_minimo) : "0"}" inputmode="decimal"></label>
    <label class="campo"><span>Localização <span class="ajuda">(corredor/prateleira)</span></span><input name="localizacao" value="${esc(p.localizacao)}"></label>
    <label class="campo"><span>Fornecedor principal</span><select name="fornecedor_id"><option value="">—</option>${opcoes(fornecedores.map((f) => [f.id, f.nome]), p.fornecedor_id)}</select></label>
    ${novo ? "" : `<label class="check larg"><input type="checkbox" name="ativo" ${p.ativo ? "checked" : ""}> Produto ativo (desmarque para parar de vender)</label>`}`,
  (d) => (novo ? POST("/api/produtos", d) : PUT(`/api/produtos/${p.id}`, d)), { msg: "Produto salvo", largura: "680px" });
  const custo = $("[name=preco_custo]", form), venda = $("[name=preco_venda]", form), margem = $("#margem", form);
  const mostrarMargem = () => { const c = centavos(custo.value), v = centavos(venda.value); margem.value = c > 0 && v > 0 ? ((v / c - 1) * 100).toFixed(1).replace(".", ",") : ""; };
  margem.oninput = () => { const c = centavos(custo.value), m = Number(margem.value.replace(",", ".")); if (c > 0 && Number.isFinite(m)) venda.value = paraCampo(Math.round(c * (1 + m / 100))); };
  custo.oninput = mostrarMargem;
  venda.oninput = mostrarMargem;
  mostrarMargem();
}

// ------------------------------------------------------------ movimentações
paginas.movimentos = async (el, pid) => {
  const [lista, produtos] = await Promise.all([GET("/api/movimentos" + (pid ? `?produto_id=${pid}` : "")), GET("/api/produtos")]);
  const TIPOS = { ESTOQUE_INICIAL: ["Estoque inicial", "info"], COMPRA: ["Entrada (compra)", "ok"], VENDA: ["Venda", ""], CANCELAMENTO_VENDA: ["Venda cancelada", "info"],
    DEVOLUCAO: ["Devolução", "info"], AJUSTE: ["Inventário", "warn"], PERDA: ["Perda", "danger"] };
  el.innerHTML = `<div class="filtros"><label class="campo" style="min-width:320px"><span>Produto</span><select id="prod"><option value="">Todos (últimos 300)</option>${opcoes(produtos.map((p) => [p.id, `${p.codigo} — ${p.nome}`]), pid)}</select></label></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Data</th><th>Produto</th><th>Tipo</th><th class="num">Quantidade</th><th class="num">Saldo</th><th>Referência</th></tr></thead><tbody>
    ${lista.map((m) => { const [t, c] = TIPOS[m.tipo] || [m.tipo, ""]; return `<tr><td>${dataBR(m.data)}</td><td>${esc(m.produto)}<span class="sub">${esc(m.codigo)}</span></td>
      <td><span class="badge ${c}">${t}</span></td><td class="num strong ${m.quantidade < 0 ? "t-danger" : "t-ok"}">${m.quantidade > 0 ? "+" : ""}${Q(m.quantidade)} ${esc(m.unidade)}</td>
      <td class="num">${Q(m.saldo_apos)}</td><td>${esc(m.referencia)}${m.observacao ? `<span class="sub">${esc(m.observacao)}</span>` : ""}</td></tr>`; }).join("")}</tbody></table>`
      : vazio("arrows", "Sem movimentações")}</div></div>`;
  $("#prod").onchange = (e) => (location.hash = "movimentos" + (e.target.value ? "/" + e.target.value : ""));
};

// --------------------------------------------------------- entrada de mercadoria
const entrada = { itens: [] };
paginas.compras = async (el) => {
  const [lista, fornecedores] = await Promise.all([GET("/api/compras"), GET("/api/fornecedores?ativos=1")]);
  el.innerHTML = `
    <div class="card"><div class="card-h"><div><h2>Nova entrada de mercadoria</h2><div class="sub">Soma ao estoque, recalcula o custo médio e lança as parcelas em Contas a pagar</div></div></div>
    ${fornecedores.length ? `<div class="card-b"><form id="compra">
      <div class="grid g-4"><label class="campo"><span>Fornecedor</span><select name="fornecedor_id" required>${opcoes(fornecedores.map((f) => [f.id, f.nome]))}</select></label>
        <label class="campo"><span>Nota fiscal</span><input name="nota_fiscal" placeholder="nº da NF"></label>
        <label class="campo"><span>Parcelas a pagar</span><input name="parcelas" type="number" value="1" min="1" max="24"></label>
        <label class="campo"><span>1º vencimento</span><input name="primeiro_vencimento" type="date"></label></div>
      <label class="campo mt"><span>Adicionar produto da nota</span><div class="ac busca">${ic("search")}<input id="e-busca" placeholder="Buscar produto por nome ou código" autocomplete="off"></div></label>
      <div class="card mt"><div class="tabela"><table class="tbl-compacta"><thead><tr><th>Produto</th><th class="num">Quantidade</th><th class="num">Custo unitário</th><th class="num">Total</th><th></th></tr></thead>
        <tbody id="e-itens"></tbody></table></div><div id="e-vazio"></div></div>
      <div class="linha entre mt"><div class="strong" style="font-size:17px" id="e-total"></div><button type="submit" class="btn primario lg">${ic("check")}Lançar entrada</button></div>
    </form></div>` : `<div class="card-b">${vazio("building", "Cadastre um fornecedor primeiro", "", `<a class="btn sm primario" href="#fornecedores">Cadastrar fornecedor</a>`)}</div>`}</div>
    <div class="card mt"><div class="card-h"><h2>Últimas entradas</h2></div><div class="card-b flush">${lista.length ? `<div class="tabela"><table><thead><tr><th>Nº</th><th>Data</th><th>Fornecedor</th><th>NF</th><th class="num">Total</th><th></th></tr></thead><tbody>
    ${lista.map((c) => `<tr><td>${c.id}</td><td>${dataBR(c.data)}</td><td>${esc(c.fornecedor)}</td><td>${esc(c.nota_fiscal)}</td><td class="num strong">${R(c.total)}</td>
      <td class="acoes"><button class="btn sm ver" data-id="${c.id}">${ic("eye")}Ver</button></td></tr>`).join("")}</tbody></table></div>` : vazio("truck", "Nenhuma entrada lançada")}</div></div>`;
  $$(".ver").forEach((b) => (b.onclick = async () => {
    try {
      const c = await GET("/api/compras/" + b.dataset.id);
      abrirModal(`Entrada nº ${c.id} — ${c.fornecedor}`, `<div class="card"><table class="tbl-compacta"><thead><tr><th>Produto</th><th class="num">Qtd</th><th class="num">Custo</th><th class="num">Total</th></tr></thead><tbody>
        ${c.itens.map((i) => `<tr><td>${esc(i.produto)}</td><td class="num">${Q(i.quantidade)} ${esc(i.unidade)}</td><td class="num">${R(i.custo_unitario)}</td><td class="num">${R(i.total)}</td></tr>`).join("")}</tbody></table></div>
        <div class="linha-total grande"><span>Total</span><b>${R(c.total)}</b></div>
        <p class="muted small">Parcelas: ${c.contas.map((p) => `${p.parcela}/${p.total_parcelas} vence ${dataBR(p.vencimento)} ${R(p.valor)} (${STATUS[p.status]?.[0] || p.status})`).join(" · ")}</p>`);
    } catch (e) { erro(e); }
  }));
  if (!fornecedores.length) return;
  const valorItem = (i) => Math.round((centavos(i.custo) || 0) * (milesimos(i.qtd) || 0) / 1000);
  const atualizarTotal = () => ($("#e-total").textContent = "Total da nota: " + R(entrada.itens.reduce((s, i) => s + valorItem(i), 0)));
  function desenhar() {
    $("#e-itens").innerHTML = entrada.itens.map((i, n) => `<tr data-n="${n}"><td><b>${esc(i.produto.nome)}</b><span class="sub">${esc(i.produto.codigo)} · estoque ${Q(i.produto.estoque)} ${esc(i.produto.unidade)}</span></td>
      <td class="num"><input class="e-qtd num" value="${esc(i.qtd)}" style="width:100px;height:32px" inputmode="decimal" aria-label="Quantidade"></td>
      <td class="num"><div class="prefixo" style="width:130px;margin-left:auto"><b>R$</b><input class="e-custo num" value="${esc(i.custo)}" style="height:32px" inputmode="decimal" aria-label="Custo unitário"></div></td>
      <td class="num strong tl">${R(valorItem(i))}</td><td class="acoes"><button type="button" class="btn sm icone fantasma rm" aria-label="Remover">${ic("trash")}</button></td></tr>`).join("");
    $("#e-vazio").innerHTML = entrada.itens.length ? "" : `<div class="vazio">Busque os produtos da nota acima.</div>`;
    $$("#e-itens tr").forEach((tr) => {
      const i = entrada.itens[tr.dataset.n];
      const mudar = () => { i.qtd = $(".e-qtd", tr).value; i.custo = $(".e-custo", tr).value; $(".tl", tr).textContent = R(valorItem(i)); atualizarTotal(); };
      $(".e-qtd", tr).oninput = mudar;
      $(".e-custo", tr).oninput = mudar;
      $(".rm", tr).onclick = () => { entrada.itens.splice(tr.dataset.n, 1); desenhar(); };
    });
    atualizarTotal();
  }
  autocompletarProduto($("#e-busca"), (p) => {
    entrada.itens.push({ produto: p, qtd: "", custo: paraCampo(p.preco_custo) });
    $("#e-busca").value = "";
    desenhar();
    $$(".e-qtd").at(-1).focus();
  });
  $("#compra").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const c = await POST("/api/compras", { ...dadosForm(e.target), itens: entrada.itens.map((i) => ({ produto_id: i.produto.id, quantidade: i.qtd, custo_unitario: i.custo })) });
      entrada.itens = [];
      avisar(`Entrada nº ${c.id} lançada: ${R(c.total)}`);
      renderizar();
    } catch (err) { erro(err); }
  };
  desenhar();
};

// ----------------------------------------------------------------- clientes
let buscaCliente = "";
paginas.clientes = async (el) => {
  const lista = await GET("/api/clientes?busca=" + encodeURIComponent(buscaCliente));
  el.innerHTML = `<div class="filtros"><label class="campo" style="flex:1;min-width:240px"><span>Buscar</span><div class="busca">${ic("search")}<input id="f-busca" value="${esc(buscaCliente)}" placeholder="Nome, CPF/CNPJ ou telefone"></div></label>
      <button class="btn primario" id="novo" style="margin-left:auto">${ic("plus")}Novo cliente</button></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Cliente</th><th>Telefone</th><th class="num">Limite</th><th class="num">Deve</th><th></th></tr></thead><tbody>
    ${lista.map((c) => `<tr class="${c.ativo ? "" : "inativo"}"><td><div class="pessoa">${avatar(c.nome)}<div><div class="nome">${esc(c.nome)}</div><span class="sub">${esc(docFmt(c.documento) || "")}</span></div></div></td>
      <td>${esc(c.telefone)}</td><td class="num">${R(c.limite_credito)}</td>
      <td class="num">${c.saldo_devedor ? `<b class="${c.valor_vencido ? "t-danger" : ""}">${R(c.saldo_devedor)}</b>${c.valor_vencido ? `<span class="sub t-danger">${R(c.valor_vencido)} vencido</span>` : ""}` : `<span class="muted">—</span>`}</td>
      <td class="acoes">${c.saldo_devedor ? `<a class="btn sm primario" href="#receber-cliente/${c.id}">${ic("wallet")}Receber</a>` : ""}
        <button class="btn sm ex" data-id="${c.id}">${ic("eye")}Extrato</button><button class="btn sm icone fantasma ed" data-id="${c.id}" title="Editar" aria-label="Editar">${ic("pencil")}</button></td></tr>`).join("")}</tbody></table>`
      : vazio("users", "Nenhum cliente encontrado", "", `<button class="btn sm primario" id="novo2">${ic("plus")}Cadastrar cliente</button>`)}</div></div>`;
  buscaAoVivo($("#f-busca"), (v) => (buscaCliente = v));
  const porId = Object.fromEntries(lista.map((c) => [c.id, c]));
  $("#novo").onclick = () => formCliente(null);
  if ($("#novo2")) $("#novo2").onclick = () => formCliente(null);
  $$(".ed").forEach((b) => (b.onclick = () => formCliente(porId[b.dataset.id])));
  $$(".ex").forEach((b) => (b.onclick = () => extratoCliente(b.dataset.id).catch(erro)));
};

function formCliente(c) {
  const novo = !c;
  c = c || { ativo: 1 };
  modalForm(novo ? "Novo cliente" : "Editar cliente", `
    <label class="campo larg"><span>Nome</span><input name="nome" required value="${esc(c.nome)}"></label>
    <label class="campo"><span>CPF/CNPJ</span><input name="documento" value="${esc(docFmt(c.documento))}"></label>
    <label class="campo"><span>Telefone / WhatsApp</span><input name="telefone" value="${esc(c.telefone)}"></label>
    <label class="campo"><span>E-mail</span><input name="email" value="${esc(c.email)}"></label>
    <label class="campo"><span>Limite de crediário</span><div class="prefixo"><b>R$</b><input name="limite_credito" class="num" value="${paraCampo(c.limite_credito)}" inputmode="decimal"></div></label>
    <label class="campo larg"><span>Endereço</span><input name="endereco" value="${esc(c.endereco)}"></label>
    ${novo ? "" : `<label class="check larg"><input type="checkbox" name="ativo" ${c.ativo ? "checked" : ""}> Cliente ativo</label>`}`,
  (d) => (novo ? POST("/api/clientes", d) : PUT(`/api/clientes/${c.id}`, d)), { msg: "Cliente salvo" });
}

async function extratoCliente(id) {
  const c = await GET("/api/clientes/" + id);
  const m = abrirModal("Extrato do cliente", `
    <div class="pessoa mb">${avatar(c.nome, "g")}<div><div class="nome" style="font-size:17px">${esc(c.nome)}</div><div class="muted small">${[docFmt(c.documento), c.telefone, c.endereco].filter(Boolean).map(esc).join(" · ")}</div></div></div>
    <div class="grid g-3">${kpi({ rot: "Deve", val: R(c.saldo_devedor), icone: "wallet", tom: "warn" })}${kpi({ rot: "Vencido", val: R(c.valor_vencido), icone: "alert", tom: c.valor_vencido ? "danger" : "ok" })}
      ${kpi({ rot: "Limite livre", val: R(c.credito_disponivel), icone: "card", tom: "info" })}</div>
    ${c.saldo_devedor ? `<div class="linha mt"><a class="btn primario" href="#receber-cliente/${c.id}">${ic("wallet")}Receber pagamento</a></div>` : ""}
    <h3 class="mt mb">Pagamentos</h3><div class="card">${c.baixas.length ? `<table class="tbl-compacta"><tbody>${c.baixas.map((b) => `<tr><td>${dataBR(b.data)}</td><td>${forma(b.forma)}</td>
      <td class="num strong">${R(b.valor)}</td><td>${badge(b.status)}</td></tr>`).join("")}</tbody></table>` : vazio("history", "Nenhum pagamento")}</div>
    <h3 class="mt mb">Compras</h3><div class="card">${c.vendas.length ? `<table class="tbl-compacta"><tbody>${c.vendas.map((v) => `<tr><td>nº ${v.id}</td><td>${dataBR(v.data)}</td>
      <td class="num strong">${R(v.total)}</td><td>${badge(v.status)}</td></tr>`).join("")}</tbody></table>` : vazio("receipt", "Nenhuma compra")}</div>`, "760px");
  $$("a", m).forEach((a) => a.addEventListener("click", fecharModal));
}

// ------------------------------------------------------------- fornecedores
paginas.fornecedores = async (el) => {
  const lista = await GET("/api/fornecedores");
  el.innerHTML = `<div class="filtros"><button class="btn primario" id="novo" style="margin-left:auto">${ic("plus")}Novo fornecedor</button></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Fornecedor</th><th>Telefone</th><th>E-mail</th><th></th></tr></thead><tbody>
    ${lista.map((f) => `<tr class="${f.ativo ? "" : "inativo"}"><td><div class="pessoa">${avatar(f.nome)}<div><div class="nome">${esc(f.nome)}</div><span class="sub">${esc(docFmt(f.documento) || "")}</span></div></div></td>
      <td>${esc(f.telefone)}</td><td>${esc(f.email)}</td><td class="acoes"><button class="btn sm icone fantasma ed" data-id="${f.id}" title="Editar" aria-label="Editar">${ic("pencil")}</button></td></tr>`).join("")}</tbody></table>`
      : vazio("building", "Nenhum fornecedor cadastrado")}</div></div>`;
  const porId = Object.fromEntries(lista.map((f) => [f.id, f]));
  const form = (f) => {
    const novo = !f;
    f = f || { ativo: 1 };
    modalForm(novo ? "Novo fornecedor" : "Editar fornecedor", `
      <label class="campo larg"><span>Nome / razão social</span><input name="nome" required value="${esc(f.nome)}"></label>
      <label class="campo"><span>CPF/CNPJ</span><input name="documento" value="${esc(docFmt(f.documento))}"></label><label class="campo"><span>Telefone</span><input name="telefone" value="${esc(f.telefone)}"></label>
      <label class="campo"><span>E-mail</span><input name="email" value="${esc(f.email)}"></label><label class="campo"><span>Endereço</span><input name="endereco" value="${esc(f.endereco)}"></label>
      ${novo ? "" : `<label class="check larg"><input type="checkbox" name="ativo" ${f.ativo ? "checked" : ""}> Fornecedor ativo</label>`}`,
    (d) => (novo ? POST("/api/fornecedores", d) : PUT(`/api/fornecedores/${f.id}`, d)), { msg: "Fornecedor salvo" });
  };
  $("#novo").onclick = () => form(null);
  $$(".ed").forEach((b) => (b.onclick = () => form(porId[b.dataset.id])));
};

// ---------------------------------------------------------- contas a receber
const filtroReceber = { status: "ABERTA", vencidas: false };
paginas.receber = async (el) => {
  const lista = await GET(`/api/contas-receber?status=${filtroReceber.status}&vencidas=${filtroReceber.vencidas ? 1 : 0}`);
  const soma = lista.reduce((s, c) => s + (c.status === "ABERTA" ? c.restante : 0), 0);
  el.innerHTML = `<div class="filtros">${segmentado("st-rec", [["ABERTA", "Em aberto"], ["PAGA", "Pagas"], ["CANCELADA", "Canceladas"], ["", "Todas"]], filtroReceber.status)}
      <label class="check" style="height:38px"><input type="checkbox" id="f-venc" ${filtroReceber.vencidas ? "checked" : ""}> Só vencidas</label>
      <span class="muted" style="margin-left:auto">Em aberto na lista: <b class="strong" style="color:var(--text)">${R(soma)}</b></span></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Cliente</th><th>Compra</th><th>Parcela</th><th>Vencimento</th><th class="num">Valor</th><th class="num">Resta</th><th>Situação</th><th></th></tr></thead><tbody>
    ${lista.map((c) => `<tr><td class="strong">${esc(c.cliente)}</td><td>nº ${c.venda_id ?? "—"}</td><td>${c.parcela}/${c.total_parcelas}</td>
      <td class="${c.vencida ? "t-danger strong" : ""}">${dataBR(c.vencimento)}</td><td class="num">${R(c.valor)}</td><td class="num strong">${R(c.restante)}</td>
      <td>${c.vencida ? badge("VENCIDA") : badge(c.status)}</td>
      <td class="acoes">${c.status === "ABERTA" ? `<button class="btn sm primario rec" data-id="${c.id}" data-c="${c.cliente_id}">${ic("wallet")}Receber</button>` : ""}</td></tr>`).join("")}</tbody></table>`
      : vazio("checkc", "Nenhuma conta aqui")}</div></div>`;
  aoSegmentar("st-rec", (v) => { filtroReceber.status = v; renderizar(); });
  $("#f-venc").onchange = (e) => { filtroReceber.vencidas = e.target.checked; renderizar(); };
  $$(".rec").forEach((b) => (b.onclick = () => { rc.preselecao = [Number(b.dataset.id)]; location.hash = "receber-cliente/" + b.dataset.c; }));
};

// ------------------------------------------------------------ contas a pagar
const filtroPagar = { status: "ABERTA", vencidas: false };
paginas.pagar = async (el) => {
  const [lista, fornecedores] = await Promise.all([GET(`/api/contas-pagar?status=${filtroPagar.status}&vencidas=${filtroPagar.vencidas ? 1 : 0}`), GET("/api/fornecedores")]);
  const soma = lista.reduce((s, c) => s + (c.status === "ABERTA" ? c.restante : 0), 0);
  el.innerHTML = `<div class="filtros">${segmentado("st-pag", [["ABERTA", "Em aberto"], ["PAGA", "Pagas"], ["CANCELADA", "Canceladas"], ["", "Todas"]], filtroPagar.status)}
      <label class="check" style="height:38px"><input type="checkbox" id="f-venc" ${filtroPagar.vencidas ? "checked" : ""}> Só vencidas</label>
      <span class="muted">Em aberto: <b class="strong" style="color:var(--text)">${R(soma)}</b></span>
      <button class="btn primario" id="nova" style="margin-left:auto">${ic("plus")}Lançar conta</button></div>
    <div class="card"><div class="tabela">${lista.length ? `<table><thead><tr><th>Descrição</th><th>Parcela</th><th>Vencimento</th><th class="num">Valor</th><th class="num">Resta</th><th>Situação</th><th></th></tr></thead><tbody>
    ${lista.map((c) => `<tr><td><b>${esc(c.descricao)}</b>${c.fornecedor ? `<span class="sub">${esc(c.fornecedor)}</span>` : ""}</td><td>${c.parcela}/${c.total_parcelas}</td>
      <td class="${c.vencida ? "t-danger strong" : ""}">${dataBR(c.vencimento)}</td><td class="num">${R(c.valor)}</td><td class="num strong">${R(c.restante)}</td>
      <td>${c.vencida ? badge("VENCIDA") : badge(c.status)}</td>
      <td class="acoes">${c.status === "ABERTA" ? `<button class="btn sm primario pg" data-id="${c.id}">Pagar</button>${c.valor_pago ? "" : `<button class="btn sm icone fantasma cc" data-id="${c.id}" title="Cancelar conta" aria-label="Cancelar conta">${ic("x")}</button>`}` : ""}</td></tr>`).join("")}</tbody></table>`
      : vazio("checkc", "Nenhuma conta aqui")}</div></div>`;
  aoSegmentar("st-pag", (v) => { filtroPagar.status = v; renderizar(); });
  $("#f-venc").onchange = (e) => { filtroPagar.vencidas = e.target.checked; renderizar(); };
  $("#nova").onclick = () => modalForm("Lançar conta a pagar", `
    <label class="campo larg"><span>Descrição</span><input name="descricao" required placeholder="Aluguel, energia, frete..."></label>
    <label class="campo"><span>Valor</span><div class="prefixo"><b>R$</b><input name="valor" required class="num" inputmode="decimal"></div></label>
    <label class="campo"><span>Vencimento</span><input name="vencimento" type="date" required value="${CONFIG.hoje}"></label>
    <label class="campo larg"><span>Fornecedor <span class="ajuda">(opcional)</span></span><select name="fornecedor_id"><option value="">—</option>${opcoes(fornecedores.map((f) => [f.id, f.nome]))}</select></label>`,
  (d) => POST("/api/contas-pagar", d), { botao: "Lançar", msg: "Conta lançada", largura: "560px" });
  const porId = Object.fromEntries(lista.map((c) => [c.id, c]));
  $$(".pg").forEach((b) => (b.onclick = () => {
    const conta = porId[b.dataset.id];
    modalForm(`Pagar — ${conta.descricao}`, `
      <label class="campo"><span>Valor <span class="ajuda">(pode ser parcial)</span></span><div class="prefixo"><b>R$</b><input name="valor" required class="num" value="${paraCampo(conta.restante)}" inputmode="decimal"></div></label>
      <label class="campo"><span>Forma</span><select name="forma">${opcoes((CONFIG.formas_pagamento_conta || []).map((f) => [f, forma(f)]), "PIX")}</select></label>
      <p class="muted small larg" style="margin:0">“Dinheiro do caixa” tira o valor da gaveta do caixa aberto.</p>`,
    (d) => POST(`/api/contas-pagar/${conta.id}/pagar`, d).then(atualizarCaixa), { botao: "Confirmar pagamento", msg: "Pagamento registrado", largura: "520px" });
  }));
  $$(".cc").forEach((b) => (b.onclick = async () => {
    if (!(await confirmar("Cancelar conta", "Cancelar esta conta a pagar?", { botao: "Cancelar conta", perigo: true }))) return;
    try { await POST(`/api/contas-pagar/${b.dataset.id}/cancelar`); avisar("Conta cancelada"); renderizar(); } catch (e) { erro(e); }
  }));
};

// --------------------------------------------------------------- relatórios
const periodoRel = { preset: "mes", inicio: "", fim: "" };
paginas.relatorios = async (el) => {
  if (!periodoRel.inicio) { periodoRel.inicio = CONFIG.hoje.slice(0, 8) + "01"; periodoRel.fim = CONFIG.hoje; }
  const q = `inicio=${periodoRel.inicio}&fim=${periodoRel.fim}`;
  const [r, mais, est] = await Promise.all([GET("/api/relatorios/vendas?" + q), GET("/api/relatorios/mais-vendidos?" + q), GET("/api/relatorios/estoque")]);
  const f = filtroPeriodo(periodoRel, renderizar);
  el.innerHTML = `${f.html}
    <div class="grid g-4">
      ${kpi({ rot: "Faturamento líquido", val: R(r.liquido), det: `bruto ${R(r.bruto)} · descontos ${R(r.descontos)} · devoluções ${R(r.devolucoes)}`, icone: "trend" })}
      ${kpi({ rot: "Lucro bruto", val: R(r.lucro_bruto), det: `custo das mercadorias ${R(r.custo_mercadorias)}`, icone: "chart", tom: r.lucro_bruto < 0 ? "danger" : "ok" })}
      ${kpi({ rot: "Vendas", val: r.quantidade, det: `ticket médio ${R(r.ticket_medio)} · ${r.canceladas} cancelada(s)`, icone: "receipt", tom: "info" })}
      ${kpi({ rot: "Recebido do crediário", val: R(r.recebimentos_crediario), icone: "wallet", tom: "warn" })}
    </div>
    <div class="grid g-2-1 mt">
      <div class="card"><div class="card-h"><h2>Produtos mais vendidos</h2></div><div class="card-b flush">${mais.length ? `<div class="tabela"><table class="tbl-compacta"><thead><tr><th>Produto</th><th class="num">Quantidade</th><th class="num">Valor</th></tr></thead><tbody>
        ${mais.map((p) => `<tr><td>${esc(p.nome)}<span class="sub">${esc(p.codigo)}</span></td><td class="num">${Q(p.quantidade)} ${esc(p.unidade)}</td><td class="num strong">${R(p.valor)}</td></tr>`).join("")}</tbody></table></div>`
        : vazio("package", "Sem vendas no período")}</div></div>
      <div class="pilha">
        <div class="card"><div class="card-h"><h2>Por forma de pagamento</h2></div><div class="card-b">${Object.keys(r.por_forma).length ? listaFormas(r.por_forma) : vazio("receipt", "Sem vendas")}</div></div>
        <div class="card"><div class="card-h"><h2>Estoque</h2></div><div class="card-b"><dl class="lista-dados" style="margin:0">
          <dt>Produtos ativos</dt><dd>${est.produtos}</dd><dt>Valor a preço de custo</dt><dd class="strong">${R(est.valor_custo)}</dd>
          <dt>Valor a preço de venda</dt><dd class="strong">${R(est.valor_venda)}</dd><dt>Abaixo do mínimo</dt><dd class="${est.estoque_baixo.length ? "t-warn strong" : ""}">${est.estoque_baixo.length}</dd>
          <dt>Zerados</dt><dd class="${est.sem_estoque.length ? "t-danger strong" : ""}">${est.sem_estoque.length}</dd></dl></div></div>
      </div>
    </div>
    <div class="card mt"><div class="card-h"><div><h2>Segurança dos dados</h2><div class="sub">Confira se estoque, vendas, caixa e contas batem entre si, e faça cópias de segurança</div></div></div>
      <div class="card-b"><div class="linha"><button class="btn" id="integridade">${ic("shield")}Conferir consistência</button><button class="btn" id="backup">${ic("download")}Fazer backup agora</button></div>
      <div id="res-seg" class="mt-s"></div></div></div>`;
  f.ligar();
  $("#integridade").onclick = async () => {
    try {
      const i = await GET("/api/integridade");
      $("#res-seg").innerHTML = i.ok ? `<div class="aviso-box info">${ic("shield")}<div><b>Tudo confere.</b> Nenhuma diferença encontrada.</div></div>`
        : `<div class="aviso-box danger">${ic("alert")}<div>${i.problemas.map(esc).join("<br>")}</div></div>`;
    } catch (e) { erro(e); }
  };
  $("#backup").onclick = async () => {
    try { const b = await POST("/api/backup"); $("#res-seg").innerHTML = `<div class="aviso-box info">${ic("download")}<div>Backup salvo em <b>${esc(b.arquivo)}</b></div></div>`; } catch (e) { erro(e); }
  };
};

// ===================================================================== casca
function montarMenu() {
  $("#sidebar").innerHTML = `<div class="brand"><div class="brand-logo">${ic("bricks")}</div><div><div class="brand-nome">${esc(CONFIG.nome_loja)}</div><div class="brand-sub">Gestão da loja</div></div></div>
    <nav class="nav">${NAV.map(([g, itens]) => (g ? `<div class="nav-grupo">${g}</div>` : "") + itens.map(([id, nome, icone, atalho]) =>
      `<a href="#${id}" data-p="${id}">${ic(icone)}<span>${nome}</span>${atalho ? `<span class="atalho">${atalho}</span>` : ""}</a>`).join("")).join("")}</nav>
    <div class="side-caixa" id="side-caixa"></div>`;
  $("#menu-btn").innerHTML = ic("menu");
  $("#menu-btn").onclick = () => $("#app").classList.toggle("menu-aberto");
  $("#veu").onclick = () => $("#app").classList.remove("menu-aberto");
  $("#btn-nova-venda").innerHTML = `${ic("cart")}Nova venda<kbd>F2</kbd>`;
}
function temaAtual() {
  const t = document.documentElement.dataset.theme;
  return t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}
function desenharBotaoTema() { $("#tema-btn").innerHTML = ic(temaAtual() === "dark" ? "sun" : "moon"); }
$("#tema-btn").onclick = () => {
  const novo = temaAtual() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = novo;
  try { localStorage.setItem("tema", novo); } catch (_) { /* navegador sem armazenamento: vale só nesta visita */ }
  desenharBotaoTema();
};
async function atualizarCaixa() {
  try {
    CAIXA = (await GET("/api/caixa")).caixa;
    $("#side-caixa").innerHTML = CAIXA
      ? `<div class="status"><span class="ponto on"></span>Caixa aberto</div><div class="det">Na gaveta: ${R(CAIXA.saldo_dinheiro)}</div>`
      : `<div class="status"><span class="ponto"></span>Caixa fechado</div><div class="det"><a href="#caixa">Abrir caixa →</a></div>`;
  } catch (_) { /* servidor indisponível: o aviso aparece na próxima ação */ }
}
function relogio() {
  const d = new Date();
  $("#relogio").textContent = d.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" }) + " · " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

let paginaAtual = null;
async function renderizar() {
  const [nome, param] = (location.hash.slice(1) || "painel").split("/");
  const id = paginas[nome] ? nome : "painel";
  paginaAtual = id;
  $$(".nav a").forEach((a) => a.classList.toggle("ativo", a.dataset.p === id));
  const [t, s] = TITULOS[id];
  $("#titulo-pagina").textContent = t;
  $("#sub-pagina").textContent = s;
  document.title = `${t} · ${CONFIG.nome_loja}`;
  $("#app").classList.remove("menu-aberto");
  const el = $("#conteudo");
  try {
    await paginas[id](el, param);
  } catch (e) {
    el.innerHTML = `<div class="aviso-box danger">${ic("alert")}<div><b>Erro ao carregar:</b> ${esc(e.message)}</div></div>`;
  }
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { fecharModal(); return; }
  if (!$("#modal").classList.contains("oculto")) return;
  if (e.key === "F2") { e.preventDefault(); if (paginaAtual === "pdv") $("#busca")?.focus(); else location.hash = "pdv"; return; }
  if (e.key === "F3") { e.preventDefault(); location.hash = "receber-cliente"; return; }
  const p = paginas[paginaAtual];
  if (p && p.teclas) p.teclas(e);
});
window.addEventListener("hashchange", () => { fecharModal(); renderizar(); window.scrollTo(0, 0); });

(async () => {
  try { CONFIG = await GET("/api/config"); } catch (e) { $("#conteudo").innerHTML = `<div class="aviso-box danger">${ic("alert")}<div>${esc(e.message)}</div></div>`; return; }
  montarMenu();
  desenharBotaoTema();
  relogio();
  setInterval(relogio, 20000);
  await atualizarCaixa();
  renderizar();
})();
