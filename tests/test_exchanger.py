import math
import unittest

from hxnet.errors import NetworkError
from hxnet.exchanger import effectiveness, exchange


class EffectivenessTests(unittest.TestCase):
    def test_equal_capacity_limit(self):
        # eps = NTU / (1 + NTU) when C ratio is 1
        self.assertAlmostEqual(effectiveness(2.0, 1.0), 2.0 / 3.0)

    def test_general_formula(self):
        ntu, cr = 1.5, 0.5
        e = math.exp(-ntu * (1 - cr))
        expected = (1 - e) / (1 - cr * e)
        self.assertAlmostEqual(effectiveness(ntu, cr), expected)

    def test_zero_ntu(self):
        self.assertEqual(effectiveness(0.0, 0.7), 0.0)


class ExchangeTests(unittest.TestCase):
    def test_zero_ua_zero_duty(self):
        ta, tb, q = exchange(100.0, 4.0, 20.0, 4.0, 0.0)
        self.assertEqual((ta, tb, q), (100.0, 20.0, 0.0))

    def test_equal_inlet_temps_zero_duty(self):
        ta, tb, q = exchange(50.0, 4.0, 50.0, 2.0, 100.0)
        self.assertEqual((ta, tb, q), (50.0, 50.0, 0.0))

    def test_energy_balance_both_sides(self):
        ta, tb, q = exchange(150.0, 6.0, 30.0, 3.0, 40.0)
        self.assertAlmostEqual(6.0 * (150.0 - ta), q)
        self.assertAlmostEqual(3.0 * (tb - 30.0), q)

    def test_hot_cold_swap_symmetry(self):
        # Swapping which side is hot must mirror the result.
        ta1, tb1, q1 = exchange(150.0, 6.0, 30.0, 3.0, 40.0)
        ta2, tb2, q2 = exchange(30.0, 3.0, 150.0, 6.0, 40.0)
        self.assertAlmostEqual(q1, q2)
        self.assertAlmostEqual(ta1, tb2)
        self.assertAlmostEqual(tb1, ta2)

    def test_equal_capacity_rates(self):
        # eps = NTU/(1+NTU); C = 4 kW/K both sides, UA = 8 -> NTU = 2
        ta, tb, q = exchange(100.0, 4.0, 20.0, 4.0, 8.0)
        eps = 2.0 / 3.0
        self.assertAlmostEqual(q, eps * 4.0 * 80.0)
        self.assertAlmostEqual(ta, 100.0 - q / 4.0)
        self.assertAlmostEqual(tb, 20.0 + q / 4.0)

    def test_rejects_invalid_numbers(self):
        for bad in (float("nan"), float("inf"), "x", None, True):
            with self.assertRaises(NetworkError):
                exchange(bad, 4.0, 20.0, 4.0, 8.0)
        with self.assertRaises(NetworkError):
            exchange(100.0, -1.0, 20.0, 4.0, 8.0)
        with self.assertRaises(NetworkError):
            exchange(100.0, 4.0, 20.0, 4.0, -5.0)


if __name__ == "__main__":
    unittest.main()
