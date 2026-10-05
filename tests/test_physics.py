import math
import unittest

from hxnet.physics import effectiveness, run_exchanger


class TestPhysics(unittest.TestCase):
    def test_equal_capacity_limit(self):
        # Cr = 1: eps = NTU / (1 + NTU)
        self.assertAlmostEqual(effectiveness(2.0, 1.0), 2.0 / 3.0)

    def test_equal_capacity_general_formula_matches_limit(self):
        eps_limit = effectiveness(3.0, 1.0)
        for cr in (0.999999, 1.0 - 1e-9):
            self.assertAlmostEqual(effectiveness(3.0, cr), eps_limit, places=5)

    def test_zero_ua_gives_zero_duty(self):
        res, a_hot = run_exchanger(200.0, 4.0, 50.0, 2.0, 0.0)
        self.assertEqual(res.duty, 0.0)
        self.assertEqual(res.hot_out, 200.0)
        self.assertEqual(res.cold_out, 50.0)

    def test_equal_inlet_temps_give_zero_duty(self):
        res, _ = run_exchanger(100.0, 4.0, 100.0, 2.0, 10.0)
        self.assertEqual(res.duty, 0.0)
        self.assertEqual(res.hot_out, 100.0)
        self.assertEqual(res.cold_out, 100.0)

    def test_energy_balance_both_sides(self):
        res, _ = run_exchanger(180.0, 3.0, 60.0, 5.0, 8.0)
        self.assertAlmostEqual(res.duty, 3.0 * (180.0 - res.hot_out), places=12)
        self.assertAlmostEqual(res.duty, 5.0 * (res.cold_out - 60.0), places=12)

    def test_known_counterflow_value(self):
        # C_hot=2, C_cold=4, UA=6 -> NTU=3, Cr=0.5
        res, _ = run_exchanger(150.0, 2.0, 30.0, 4.0, 6.0)
        e = math.exp(-3.0 * 0.5)
        eps = (1 - e) / (1 - 0.5 * e)
        self.assertAlmostEqual(res.effectiveness, eps)
        self.assertAlmostEqual(res.duty, eps * 2.0 * 120.0)

    def test_equal_capacity_rates_outlets(self):
        # C = 2 both sides, UA = 4 -> NTU = 2, eps = 2/3
        res, _ = run_exchanger(90.0, 2.0, 30.0, 2.0, 4.0)
        self.assertAlmostEqual(res.duty, (2.0 / 3.0) * 2.0 * 60.0)
        self.assertAlmostEqual(res.hot_out, 90.0 - res.duty / 2.0)
        self.assertAlmostEqual(res.cold_out, 30.0 + res.duty / 2.0)


if __name__ == "__main__":
    unittest.main()
