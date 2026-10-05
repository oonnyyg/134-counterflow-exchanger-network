"""Command line interface: JSON in, CSV detail + JSON report out."""

from __future__ import annotations

import argparse
import csv
import json
import sys

from .model import NetworkError, parse_network
from .scenario import run_scenario
from .solver import Solution, solve


def _solution_rows(sol: Solution, case: str) -> list[dict]:
    rows = []
    for e in sol.exchangers:
        rows.append(
            {
                "case": case,
                "exchanger": e.name,
                "ua_kW_per_K": e.ua,
                "in_a": e.in_a,
                "in_b": e.in_b,
                "t_a_in_C": e.t_a_in,
                "t_b_in_C": e.t_b_in,
                "t_a_out_C": e.t_a_out,
                "t_b_out_C": e.t_b_out,
                "a_side": e.a_side,
                "duty_kW": e.duty,
                "effectiveness": e.effectiveness,
                "ntu": e.ntu,
            }
        )
    return rows


def _solution_dict(sol: Solution) -> dict:
    return {
        "exchangers": [
            {
                "name": e.name,
                "ua_kW_per_K": e.ua,
                "in_a": e.in_a,
                "in_b": e.in_b,
                "t_a_in_C": e.t_a_in,
                "t_b_in_C": e.t_b_in,
                "t_a_out_C": e.t_a_out,
                "t_b_out_C": e.t_b_out,
                "a_side": e.a_side,
                "duty_kW": e.duty,
                "effectiveness": e.effectiveness,
                "ntu": e.ntu,
            }
            for e in sol.exchangers
        ],
        "final_streams": [
            {
                "name": n,
                "temp_C": sol.streams[n].temp,
                "mdot_kg_per_s": sol.streams[n].mdot,
                "cp_kJ_per_kg_K": sol.streams[n].cp,
                "enthalpy_flow_kW": sol.streams[n].enthalpy_flow,
            }
            for n in sol.final_streams
        ],
        "enthalpy_check": {
            "source_enthalpy_flow_kW": sol.source_enthalpy,
            "final_enthalpy_flow_kW": sol.final_enthalpy,
            "imbalance_kW": sol.enthalpy_imbalance,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hxnet",
        description="Offline counterflow heat-exchanger network calculator",
    )
    parser.add_argument("input", help="network JSON file ('-' for stdin)")
    parser.add_argument("--csv", help="write exchanger detail CSV here")
    parser.add_argument("--json", help="write JSON report here (default stdout)")
    args = parser.parse_args(argv)

    try:
        text = sys.stdin.read() if args.input == "-" else open(
            args.input, encoding="utf-8"
        ).read()
        net = parse_network(json.loads(text))
    except (OSError, json.JSONDecodeError, NetworkError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    base = solve(net)
    reports = [run_scenario(net, base, sc) for sc in net.scenarios]

    rows = _solution_rows(base, "base")
    for rep in reports:
        rows += _solution_rows(rep.scenario_solution, rep.name)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["case"])
            writer.writeheader()
            writer.writerows(rows)

    report = {
        "units": {
            "temperature": "degC",
            "mdot": "kg/s",
            "cp": "kJ/(kg*K)",
            "ua": "kW/K",
            "duty": "kW",
        },
        "base": _solution_dict(base),
        "scenarios": [
            {
                "name": rep.name,
                "exchanger": rep.exchanger,
                "base_ua_kW_per_K": rep.base_ua,
                "scenario_ua_kW_per_K": rep.scenario_ua,
                "per_exchanger_diff": [
                    {
                        "exchanger": d.name,
                        "base_duty_kW": d.base_duty,
                        "scenario_duty_kW": d.scenario_duty,
                        "delta_duty_kW": d.delta_duty,
                        "base_t_a_out_C": d.base_t_a_out,
                        "scenario_t_a_out_C": d.scenario_t_a_out,
                        "base_t_b_out_C": d.base_t_b_out,
                        "scenario_t_b_out_C": d.scenario_t_b_out,
                    }
                    for d in rep.diffs
                ],
                "solution": _solution_dict(rep.scenario_solution),
            }
            for rep in reports
        ],
    }
    out = json.dumps(report, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
