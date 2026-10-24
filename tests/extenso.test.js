// Testes do valor por extenso (rodados pelo tests/test_impressao.py).
const assert = require("assert");
const porExtenso = require("../loja/static/extenso.js");
const casos = {
  0: "zero real", 1: "um centavo", 50: "cinquenta centavos", 100: "um real", 101: "um real e um centavo",
  200: "dois reais", 1050: "dez reais e cinquenta centavos", 1999: "dezenove reais e noventa e nove centavos",
  2100: "vinte e um reais", 10000: "cem reais", 10100: "cento e um reais", 11670: "cento e dezesseis reais e setenta centavos",
  12050: "cento e vinte reais e cinquenta centavos", 100000: "mil reais", 100100: "mil e um reais",
  110000: "mil e cem reais", 115000: "mil cento e cinquenta reais", 123456: "mil duzentos e trinta e quatro reais e cinquenta e seis centavos",
  200000: "dois mil reais", 1000000: "dez mil reais", 2131700: "vinte e um mil trezentos e dezessete reais",
  10000000: "cem mil reais", 100000000: "um milhão de reais", 200000000: "dois milhões de reais",
  100100000: "um milhão e mil reais", 123456789: "um milhão duzentos e trinta e quatro mil quinhentos e sessenta e sete reais e oitenta e nove centavos",
  70000: "setecentos reais", 1400: "quatorze reais", 9900: "noventa e nove reais", 50000000: "quinhentos mil reais",
};
let n = 0;
for (const [c, esperado] of Object.entries(casos)) {
  assert.strictEqual(porExtenso(Number(c)), esperado, `valor ${c}`);
  n++;
}
console.log(`${n} valores por extenso conferidos`);
