import copy
import unittest

from hxnet.errors import NetworkError
from hxnet.scenario import compare_scenario
from hxnet.solver import solve_network


def chain_spec():
    # Hot stream H1 cooled by C1 in E1, then cooled further by C2 in E2.
    return {
        "sources": {
            "H1": {"temp": 200.0, "mdot": 2.0, "cp": 2.0},
            "C1": {"temp": 30.0, "mdot": 3.0, "cp": 4.0},
            "C2": {"temp": 20.0, "mdot": 5.0, "cp": 4.2},
        },
        "exchangers": {
            "E2": {"ua": 60.0, "in_a": "H1_mid", "in_b": "C2",
                   "out_a": "H1_out", "out_b": "C2_out"},
            "E1": {"ua": 40.0, "in_a": "H1", "in_b": "C1",
                   "out_a": "H1_mid", "out_b": "C1_out"},
        },
    }


class SolverTests(unittest.TestCase):
    def test_forward_reference_chain(self):
        # E2 is listed before E1 but depends on it; must still solve.
        r = solve_network(chain_spec())
        e1 = r["exchangers"]["E1"]
        e2 = r["exchangers"]["E2"]
        self.assertAlmostEqual(e1["t_out_a"], e2["t_in_a"])
        self.assertEqual(r["final_outlets"], ["C1_out", "C2_out", "H1_out"])
        # Outlet streams inherit identity (mdot, cp) of their inlet stream.
        self.assertEqual(r["streams"]["H1_out"]["mdot"], 2.0)
        self.assertEqual(r["streams"]["C2_out"]["cp"], 4.2)

    def test_enthalpy_balance(self):
        r = solve_network(chain_spec())
        self.assertAlmostEqual(r["enthalpy_imbalance_kw"], 0.0, places=9)

    def test_hot_cold_side_detection(self):
        r = solve_network(chain_spec())
        self.assertEqual(r["exchangers"]["E1"]["hot_side"], "a")
        self.assertEqual(r["exchangers"]["E1"]["cold_side"], "b")

    def test_reject_duplicate_stream_name(self):
        spec = chain_spec()
        spec["exchangers"]["E1"]["out_a"] = "C1"
        with self.assertRaises(NetworkError):
            solve_network(spec)

    def test_reject_unknown_source(self):
        spec = chain_spec()
        spec["exchangers"]["E1"]["in_b"] = "NOPE"
        with self.assertRaises(NetworkError):
            solve_network(spec)

    def test_reject_stream_consumed_twice(self):
        spec = chain_spec()
        spec["exchangers"]["E2"]["in_b"] = "C1"
        with self.assertRaises(NetworkError):
            solve_network(spec)

    def test_reject_cycle(self):
        spec = {
            "sources": {"S": {"temp": 100.0, "mdot": 1.0, "cp": 4.0}},
            "exchangers": {
                "E1": {"ua": 1.0, "in_a": "S", "in_b": "y",
                       "out_a": "x", "out_b": "w"},
                "E2": {"ua": 1.0, "in_a": "x", "in_b": "S2",
                       "out_a": "y", "out_b": "z"},
            },
        }
        spec["sources"]["S2"] = {"temp": 10.0, "mdot": 1.0, "cp": 4.0}
        with self.assertRaises(NetworkError):
            solve_network(spec)

    def test_reject_non_finite(self):
        spec = chain_spec()
        spec["sources"]["H1"]["temp"] = float("nan")
        with self.assertRaises(NetworkError):
            solve_network(spec)

    def test_reject_nonpositive_flow(self):
        spec = chain_spec()
        spec["sources"]["H1"]["mdot"] = 0.0
        with self.assertRaises(NetworkError):
            solve_network(spec)


class ScenarioTests(unittest.TestCase):
    def test_retrofit_propagates_downstream(self):
        spec = chain_spec()
        original = copy.deepcopy(spec)
        cmp_r = compare_scenario(spec, "E1", 120.0)
        # Baseline spec untouched.
        self.assertEqual(spec, original)
        per = cmp_r["per_exchanger"]
        self.assertTrue(per["E1"]["changed"])
        self.assertTrue(per["E2"]["changed"])  # downstream affected
        self.assertGreater(per["E1"]["scenario_duty_kw"],
                           per["E1"]["baseline_duty_kw"])
        # E2 sees a cooler H1_mid, so its duty drops.
        self.assertLess(per["E2"]["scenario_duty_kw"],
                        per["E2"]["baseline_duty_kw"])
        # Baseline results identical to solving the spec directly.
        base = solve_network(spec)
        self.assertEqual(cmp_r["baseline"]["total_duty_kw"],
                         base["total_duty_kw"])
        # Enthalpy balance holds in the scenario too.
        self.assertAlmostEqual(
            cmp_r["scenario"]["enthalpy_imbalance_kw"], 0.0, places=9)

    def test_unknown_exchanger_rejected(self):
        with self.assertRaises(NetworkError):
            compare_scenario(chain_spec(), "NOPE", 10.0)


if __name__ == "__main__":
    unittest.main()
