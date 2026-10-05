"""Command line interface: solve a network, optionally compare a retrofit."""
import argparse
import csv
import json
import sys

from .errors import NetworkError
from .scenario import compare_scenario
from .solver import solve_network


def _result_rows(result, label):
    rows = []
    for name, r in result["exchangers"].items():
        rows.append({
            "case": label,
            "exchanger": name,
            "ua_kw_per_k": r["ua"],
            "hot_side": r["hot_side"],
            "in_a": r["in_a"], "t_in_a_c": r["t_in_a"],
            "out_a": r["out_a"], "t_out_a_c": r["t_out_a"],
            "in_b": r["in_b"], "t_in_b_c": r["t_in_b"],
            "out_b": r["out_b"], "t_out_b_c": r["t_out_b"],
            "duty_kw": r["duty_kw"],
        })
    return rows


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _report(result):
    return {
        "exchangers": result["exchangers"],
        "final_outlets": {
            n: result["streams"][n] for n in result["final_outlets"]
        },
        "total_duty_kw": result["total_duty_kw"],
        "source_enthalpy_kw": result["source_enthalpy_kw"],
        "outlet_enthalpy_kw": result["outlet_enthalpy_kw"],
        "enthalpy_imbalance_kw": result["enthalpy_imbalance_kw"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="hxnet",
        description="Counterflow heat-exchanger network calculator "
                    "(effectiveness-NTU, degC / kg/s / kJ/kg-K / kW/K).")
    p.add_argument("network", help="JSON network description file")
    p.add_argument("--replace-ua", nargs=2, metavar=("EXCHANGER", "UA"),
                   help="retrofit scenario: replace UA of one exchanger")
    p.add_argument("--csv", metavar="PATH", help="write CSV detail rows")
    p.add_argument("--json", metavar="PATH", help="write JSON report")
    args = p.parse_args(argv)

    try:
        with open(args.network, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read network file: {exc}", file=sys.stderr)
        return 2

    try:
        if args.replace_ua:
            name, ua_text = args.replace_ua
            try:
                new_ua = float(ua_text)
            except ValueError:
                raise NetworkError(f"invalid UA value {ua_text!r}")
            cmp_result = compare_scenario(spec, name, new_ua)
            report = {
                "modified_exchanger": name,
                "baseline": _report(cmp_result["baseline"]),
                "scenario": _report(cmp_result["scenario"]),
                "per_exchanger": cmp_result["per_exchanger"],
                "delta_total_duty_kw": cmp_result["delta_total_duty_kw"],
            }
            rows = (_result_rows(cmp_result["baseline"], "baseline")
                    + _result_rows(cmp_result["scenario"], "scenario"))
        else:
            result = solve_network(spec)
            report = {"baseline": _report(result)}
            rows = _result_rows(result, "baseline")
    except NetworkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.csv:
        _write_csv(args.csv, rows)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    if not args.csv and not args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
