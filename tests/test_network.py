import unittest

from hxnet.model import NetworkError, parse_network
from hxnet.scenario import run_scenario
from hxnet.solver import solve


def chain_network():
    # Forward reference: E2 is listed before E1 but consumes E1's output.
    return parse_network(
        {
            "sources": [
                {"name": "H", "temp": 200.0, "mdot": 2.0, "cp": 2.0},
                {"name": "C", "temp": 30.0, "mdot": 4.0, "cp": 2.0},
                {"name": "C2", "temp": 40.0, "mdot": 3.0, "cp": 2.0},
            ],
            "exchangers": [
                {"name": "E2", "ua": 5.0, "in_a": "H_E1", "in_b": "C2",
                 "out_a": "H_E2", "out_b": "C_E2"},
                {"name": "E1", "ua": 10.0, "in_a": "H", "in_b": "C",
                 "out_a": "H_E1", "out_b": "C_E1"},
            ],
            "scenarios": [
                {"name": "bigger-E2", "exchanger": "E2", "ua": 20.0},
                {"name": "bigger-E1", "exchanger": "E1", "ua": 30.0},
            ],
        }
    )


class TestChainedNetwork(unittest.TestCase):
    def test_forward_reference_solved_in_dependency_order(self):
        sol = solve(chain_network())
        self.assertEqual([e.name for e in sol.exchangers], ["E1", "E2"])

    def test_downstream_propagation_and_balance(self):
        sol = solve(chain_network())
        e1, e2 = sol.exchangers
        # E2 consumes E1's hot outlet.
        self.assertAlmostEqual(e2.t_a_in, e1.t_a_out)
        # Energy balance on every exchanger, both sides.
        for e in sol.exchangers:
            a, b = sol.streams[e.in_a], sol.streams[e.in_b]
            oa, ob = sol.streams[e.out_a], sol.streams[e.out_b]
            self.assertAlmostEqual(
                a.enthalpy_flow + b.enthalpy_flow,
                oa.enthalpy_flow + ob.enthalpy_flow,
                places=9,
            )
        # Whole-network enthalpy check.
        self.assertAlmostEqual(sol.enthalpy_imbalance, 0.0, places=9)
        self.assertEqual(set(sol.final_streams), {"H_E2", "C_E1", "C_E2"})

    def test_scenario_repropagates_downstream(self):
        net = chain_network()
        base = solve(net)
        rep = run_scenario(net, base, net.scenarios[0])
        diff = {d.name: d for d in rep.diffs}
        # Bigger UA on E2 raises its duty; upstream E1 is unaffected.
        self.assertGreater(diff["E2"].delta_duty, 0.0)
        self.assertAlmostEqual(diff["E1"].base_duty, diff["E1"].scenario_duty)
        # Downstream outlet of E2 changes.
        self.assertNotAlmostEqual(
            diff["E2"].base_t_a_out, diff["E2"].scenario_t_a_out
        )
        # Base configuration is not modified.
        self.assertEqual(net.exchangers[0].ua, 5.0)
        self.assertAlmostEqual(
            rep.scenario_solution.enthalpy_imbalance, 0.0, places=9
        )

    def test_upstream_change_repropagates_downstream(self):
        net = chain_network()
        base = solve(net)
        rep = run_scenario(net, base, net.scenarios[1])
        diff = {d.name: d for d in rep.diffs}
        # Changing E1 alters E1's duty and E2's hot inlet downstream.
        self.assertGreater(diff["E1"].delta_duty, 0.0)
        self.assertNotAlmostEqual(diff["E2"].base_duty, diff["E2"].scenario_duty)


class TestSideSwap(unittest.TestCase):
    def test_hot_cold_side_by_inlet_temperature(self):
        net = parse_network(
            {
                "sources": [
                    {"name": "A", "temp": 20.0, "mdot": 1.0, "cp": 4.0},
                    {"name": "B", "temp": 150.0, "mdot": 1.0, "cp": 2.0},
                ],
                "exchangers": [
                    {"name": "E1", "ua": 5.0, "in_a": "A", "in_b": "B",
                     "out_a": "A_out", "out_b": "B_out"}
                ],
            }
        )
        sol = solve(net)
        (e,) = sol.exchangers
        # A is the cold side even though it is connected to port a.
        self.assertEqual(e.a_side, "cold")
        self.assertGreater(sol.streams["A_out"].temp, 20.0)
        self.assertLess(sol.streams["B_out"].temp, 150.0)
        # Identities are not crossed: A_out keeps A's flow and cp.
        self.assertEqual(sol.streams["A_out"].capacity, 4.0)
        self.assertEqual(sol.streams["B_out"].capacity, 2.0)


class TestValidation(unittest.TestCase):
    def _bad(self, data, fragment):
        with self.assertRaises(NetworkError) as ctx:
            parse_network(data)
        self.assertIn(fragment, str(ctx.exception))

    def test_duplicate_stream(self):
        self._bad(
            {"sources": [
                {"name": "A", "temp": 1, "mdot": 1, "cp": 1},
                {"name": "A", "temp": 2, "mdot": 1, "cp": 1},
            ]},
            "duplicate stream",
        )

    def test_unknown_source(self):
        self._bad(
            {"sources": [{"name": "A", "temp": 1, "mdot": 1, "cp": 1}],
             "exchangers": [{"name": "E", "ua": 1, "in_a": "A", "in_b": "X",
                             "out_a": "o1", "out_b": "o2"}]},
            "unknown stream",
        )

    def test_double_consumption_rejected(self):
        self._bad(
            {"sources": [
                {"name": "A", "temp": 1, "mdot": 1, "cp": 1},
                {"name": "B", "temp": 2, "mdot": 1, "cp": 1},
            ],
             "exchangers": [
                 {"name": "E1", "ua": 1, "in_a": "A", "in_b": "B",
                  "out_a": "o1", "out_b": "o2"},
                 {"name": "E2", "ua": 1, "in_a": "A", "in_b": "o1",
                  "out_a": "o3", "out_b": "o4"},
             ]},
            "more than once",
        )

    def test_cycle_rejected(self):
        self._bad(
            {"sources": [
                {"name": "A", "temp": 1, "mdot": 1, "cp": 1},
                {"name": "B", "temp": 2, "mdot": 1, "cp": 1},
            ],
             "exchangers": [
                 {"name": "E1", "ua": 1, "in_a": "A", "in_b": "o4",
                  "out_a": "o1", "out_b": "o2"},
                 {"name": "E2", "ua": 1, "in_a": "o2", "in_b": "B",
                  "out_a": "o3", "out_b": "o4"},
             ]},
            "cyclic",
        )

    def test_non_finite_rejected(self):
        self._bad(
            {"sources": [{"name": "A", "temp": "hot", "mdot": 1, "cp": 1}]},
            "expected a number",
        )

    def test_negative_ua_rejected(self):
        self._bad(
            {"sources": [
                {"name": "A", "temp": 1, "mdot": 1, "cp": 1},
                {"name": "B", "temp": 2, "mdot": 1, "cp": 1},
            ],
             "exchangers": [{"name": "E", "ua": -1, "in_a": "A", "in_b": "B",
                             "out_a": "o1", "out_b": "o2"}]},
            "non-negative",
        )


if __name__ == "__main__":
    unittest.main()
