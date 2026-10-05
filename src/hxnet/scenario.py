"""Retrofit scenario: replace one exchanger's UA and compare downstream."""
from .errors import NetworkError
from .solver import solve_network



def compare_scenario(spec, exchanger_name, new_ua):
    """Solve baseline and a scenario with one exchanger's UA replaced.

    The baseline spec is never mutated. Returns per-exchanger deltas.
    """
    if not isinstance(spec, dict):
        raise NetworkError("network spec must be a JSON object")
    exchangers = spec.get("exchangers", {})
    if exchanger_name not in exchangers:
        raise NetworkError(f"unknown exchanger {exchanger_name!r}")
    baseline = solve_network(spec)
    scenario = solve_network(spec, ua_overrides={exchanger_name: new_ua})

    per_exchanger = {}
    for name, base in baseline["exchangers"].items():
        scen = scenario["exchangers"][name]
        per_exchanger[name] = {
            "baseline_ua": base["ua"],
            "scenario_ua": scen["ua"],
            "baseline_duty_kw": base["duty_kw"],
            "scenario_duty_kw": scen["duty_kw"],
            "delta_duty_kw": scen["duty_kw"] - base["duty_kw"],
            "baseline_out_temps": {
                base["out_a"]: base["t_out_a"],
                base["out_b"]: base["t_out_b"],
            },
            "scenario_out_temps": {
                scen["out_a"]: scen["t_out_a"],
                scen["out_b"]: scen["t_out_b"],
            },
            "changed": (
                scen["duty_kw"] != base["duty_kw"]
                or scen["t_out_a"] != base["t_out_a"]
                or scen["t_out_b"] != base["t_out_b"]
            ),
        }
    return {
        "modified_exchanger": exchanger_name,
        "baseline": baseline,
        "scenario": scenario,
        "per_exchanger": per_exchanger,
        "delta_total_duty_kw": (scenario["total_duty_kw"]
                                - baseline["total_duty_kw"]),
    }
