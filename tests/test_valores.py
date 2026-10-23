import datetime
import unittest
from decimal import Decimal

from loja import valores as v
from loja.valores import LojaError


class TestDinheiro(unittest.TestCase):
    def test_formatos_aceitos(self):
        casos = {"12,50": 1250, "1.234,56": 123456, "1234.56": 123456, "R$ 7,00": 700, "0,01": 1,
                 "10": 1000, 12.5: 1250, 3: 300, Decimal("0.1"): 10, " 99,9 ": 9990}
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(v.centavos(entrada), esperado)

    def test_float_sem_erro_de_arredondamento(self):
        # 0.1 + 0.2 em float é 0.30000000000000004; aqui tem que dar 30 centavos exatos
        self.assertEqual(v.centavos(0.1) + v.centavos(0.2), v.centavos("0,30"))
        self.assertEqual(v.centavos(19.99), 1999)
        self.assertEqual(v.centavos(1004.99), 100499)

    def test_valores_invalidos(self):
        for entrada in ["", "abc", "1,234", "12,345", None, True, "NaN", "Infinity", "-5", [], "1e400"]:
            with self.subTest(entrada=entrada):
                with self.assertRaises(LojaError):
                    v.centavos(entrada)

    def test_positivo(self):
        with self.assertRaises(LojaError):
            v.centavos("0", positivo=True)
        self.assertEqual(v.centavos("0"), 0)

    def test_quantidade(self):
        self.assertEqual(v.milesimos("2,5"), 2500)
        self.assertEqual(v.milesimos("0,001"), 1)
        self.assertEqual(v.milesimos(3), 3000)
        for ruim in ["0", "-1", "0,0001", "x"]:
            with self.assertRaises(LojaError):
                v.milesimos(ruim)

    def test_multiplicar_arredonda_meio_para_cima(self):
        self.assertEqual(v.multiplicar(239, 2500), 598)   # 5,975 -> 5,98
        self.assertEqual(v.multiplicar(333, 1500), 500)   # 4,995 -> 5,00
        self.assertEqual(v.multiplicar(14500, 750), 10875)
        self.assertEqual(v.multiplicar(3890, 3000), 11670)

    def test_ratear_soma_exata(self):
        for total, pesos in [(1000, [1, 1, 1]), (1, [5, 5]), (99999, [3, 7, 11, 13]), (0, [1, 2]),
                             (12345, [1] * 7), (500, [100000, 1])]:
            partes = v.ratear(total, pesos)
            self.assertEqual(sum(partes), total)
            self.assertTrue(all(p >= 0 for p in partes))
        self.assertEqual(v.ratear(1000, [1, 1, 1]), [334, 333, 333])

    def test_formatacao(self):
        self.assertEqual(v.formatar_reais(123456789), "R$ 1.234.567,89")
        self.assertEqual(v.formatar_reais(5), "R$ 0,05")
        self.assertEqual(v.formatar_reais(-150), "-R$ 1,50")
        self.assertEqual(v.formatar_quantidade(2500), "2,5")
        self.assertEqual(v.formatar_quantidade(3000), "3")


class TestDocumentos(unittest.TestCase):
    def test_cpf_cnpj_validos(self):
        self.assertEqual(v.documento("529.982.247-25"), "52998224725")
        self.assertEqual(v.documento("11.222.333/0001-81"), "11222333000181")
        self.assertIsNone(v.documento(""))
        self.assertIsNone(v.documento(None))

    def test_invalidos(self):
        for d in ["529.982.247-24", "111.111.111-11", "123", "11.222.333/0001-80", "00000000000000"]:
            with self.assertRaises(LojaError):
                v.documento(d)


class TestDatas(unittest.TestCase):
    def test_somar_meses_fim_de_mes(self):
        self.assertEqual(v.somar_meses(datetime.date(2026, 1, 31), 1), datetime.date(2026, 2, 28))
        self.assertEqual(v.somar_meses(datetime.date(2028, 1, 31), 1), datetime.date(2028, 2, 29))
        self.assertEqual(v.somar_meses(datetime.date(2026, 11, 15), 3), datetime.date(2027, 2, 15))
        self.assertEqual(v.somar_meses(datetime.date(2026, 3, 31), 1), datetime.date(2026, 4, 30))

    def test_data_invalida(self):
        with self.assertRaises(LojaError):
            v.data_iso("31/02/2026")


if __name__ == "__main__":
    unittest.main()
