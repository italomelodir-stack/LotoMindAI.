"""Conversão e formatação de valores monetários, quantidades e documentos.

Dinheiro é sempre guardado em centavos (int) e quantidades em milésimos (int),
para que nenhuma conta dependa de ponto flutuante.
"""
import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class LojaError(Exception):
    """Erro de regra de negócio, com mensagem pronta para mostrar ao usuário."""


class NaoEncontrado(LojaError):
    """Registro inexistente."""


def _decimal(valor, campo):
    if isinstance(valor, bool) or valor is None:
        raise LojaError(f"{campo}: valor inválido")
    if isinstance(valor, Decimal):
        d = valor
    elif isinstance(valor, int):
        d = Decimal(valor)
    elif isinstance(valor, float):
        d = Decimal(repr(valor))
    elif isinstance(valor, str):
        s = valor.strip().replace("R$", "").replace(" ", "")
        if not s:
            raise LojaError(f"{campo}: informe um valor")
        if "," in s:
            # formato brasileiro: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        try:
            d = Decimal(s)
        except InvalidOperation:
            raise LojaError(f"{campo}: '{valor}' não é um número válido") from None
    else:
        raise LojaError(f"{campo}: valor inválido")
    if not d.is_finite():
        raise LojaError(f"{campo}: valor inválido")
    return d


def _escalar(valor, campo, fator, casas, minimo):
    d = _decimal(valor, campo) * fator
    if d != d.to_integral_value():
        raise LojaError(f"{campo}: use no máximo {casas} casas decimais")
    n = int(d)
    if n < minimo:
        if minimo > 0:
            raise LojaError(f"{campo}: deve ser maior que zero")
        raise LojaError(f"{campo}: não pode ser negativo")
    if n > 10**13:
        raise LojaError(f"{campo}: valor alto demais")
    return n


def centavos(valor, campo="Valor", positivo=False):
    """Converte '1.234,56', '1234.56', 1234.56 ou Decimal em centavos (int)."""
    return _escalar(valor, campo, 100, 2, 1 if positivo else 0)


def milesimos(valor, campo="Quantidade", positivo=True):
    """Converte uma quantidade ('2,5', 2.5, '3') em milésimos (int)."""
    return _escalar(valor, campo, 1000, 3, 1 if positivo else 0)


def multiplicar(preco_centavos, qtd_milesimos):
    """Preço unitário x quantidade, arredondado ao centavo (meio para cima)."""
    d = Decimal(preco_centavos) * Decimal(qtd_milesimos) / Decimal(1000)
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def proporcao(valor, parte, todo):
    """valor * parte / todo, arredondado ao centavo."""
    d = Decimal(valor) * Decimal(parte) / Decimal(todo)
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def ratear(total, pesos):
    """Divide `total` proporcionalmente aos pesos; a soma das partes é exatamente `total`."""
    soma = sum(pesos)
    if soma <= 0:
        raise LojaError("Rateio impossível: pesos zerados")
    partes = [total * p // soma for p in pesos]
    falta = total - sum(partes)
    ordem = sorted(range(len(pesos)), key=lambda i: (total * pesos[i]) % soma, reverse=True)
    for i in ordem[:falta]:
        partes[i] += 1
    return partes


def formatar_reais(c):
    sinal = "-" if c < 0 else ""
    c = abs(c)
    inteiro = f"{c // 100:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{c % 100:02d}"


def formatar_quantidade(m):
    s = f"{Decimal(m) / 1000:f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def somar_meses(data, meses):
    mes = data.month - 1 + meses
    ano = data.year + mes // 12
    mes = mes % 12 + 1
    for dia in range(data.day, 27, -1):
        try:
            return datetime.date(ano, mes, dia)
        except ValueError:
            continue
    return datetime.date(ano, mes, min(data.day, 28))


def data_iso(valor, campo="Data"):
    if isinstance(valor, datetime.date):
        return valor
    try:
        return datetime.date.fromisoformat(str(valor).strip())
    except ValueError:
        raise LojaError(f"{campo}: data inválida (use AAAA-MM-DD)") from None


def so_digitos(texto):
    return "".join(ch for ch in str(texto or "") if ch.isdigit())


def _cpf_valido(d):
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[n]):
            return False
    return True


def _cnpj_valido(d):
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, n in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(d[i]) * pesos[i] for i in range(n))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(d[n]):
            return False
    return True


def documento(texto):
    """Valida CPF ou CNPJ. Retorna só os dígitos, ou None se vazio."""
    d = so_digitos(texto)
    if not d:
        return None
    if len(d) == 11 and _cpf_valido(d):
        return d
    if len(d) == 14 and _cnpj_valido(d):
        return d
    raise LojaError(f"CPF/CNPJ inválido: {texto}")
