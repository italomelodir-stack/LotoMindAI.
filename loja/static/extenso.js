"use strict";
// Valor por extenso em reais, para recibos: 12050 centavos -> "cento e vinte reais e cinquenta centavos".

(function (raiz) {
  const UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
    "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"];
  const DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"];
  const CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
    "oitocentos", "novecentos"];
  const ESCALAS = [["", ""], ["mil", "mil"], ["milhão", "milhões"], ["bilhão", "bilhões"], ["trilhão", "trilhões"]];

  function ate999(n) {
    if (n === 100) return "cem";
    const partes = [];
    const c = Math.floor(n / 100), r = n % 100;
    if (c) partes.push(CENTENAS[c]);
    if (r) partes.push(r < 20 ? UNIDADES[r] : DEZENAS[Math.floor(r / 10)] + (r % 10 ? " e " + UNIDADES[r % 10] : ""));
    return partes.join(" e ");
  }

  // 1234 -> "mil duzentos e trinta e quatro"; 1100 -> "mil e cem"; 2000000 -> "dois milhões"
  function inteiro(n) {
    if (n === 0) return "zero";
    const grupos = [];
    for (let i = 0; n > 0; i++, n = Math.floor(n / 1000)) {
      const g = n % 1000;
      if (!g) continue;
      const texto = i === 1 && g === 1 ? "mil" : ate999(g) + (i ? " " + ESCALAS[i][g === 1 ? 0 : 1] : "");
      grupos.unshift({ g, i, texto });
    }
    return grupos.map((x, k) => {
      if (k === 0) return x.texto;
      // o último grupo leva "e" quando é menor que cem ou uma centena redonda ("mil e cem", "mil e cinco")
      const ultimo = k === grupos.length - 1;
      return (ultimo && (x.g < 100 || x.g % 100 === 0) ? " e " : " ") + x.texto;
    }).join("");
  }

  function porExtenso(centavos) {
    centavos = Math.round(Math.abs(centavos));
    const reais = Math.floor(centavos / 100), cent = centavos % 100;
    const partes = [];
    if (reais) {
      // "um milhão de reais", "dois milhões de reais"
      const de = reais >= 1e6 && reais % 1e6 === 0 ? " de" : "";
      partes.push(inteiro(reais) + de + (reais === 1 ? " real" : " reais"));
    }
    if (cent) partes.push(inteiro(cent) + (cent === 1 ? " centavo" : " centavos"));
    return partes.length ? partes.join(" e ") : "zero real";
  }

  raiz.porExtenso = porExtenso;
  if (typeof module !== "undefined") module.exports = porExtenso;
})(typeof window !== "undefined" ? window : globalThis);
