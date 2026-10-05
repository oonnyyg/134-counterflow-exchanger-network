"""Scenario comparison: replace one exchanger's UA, repropagate, diff."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Network, Scenario
from .solver import Solution, solve


@dataclass(frozen=True)
class ExchangerDiff:
    name: str
    base_duty: float
    scenario_duty: float
    delta_duty: float
    base_t_a_out: float
    scenario_t_a_out: float
    base_t_b_out: float
    scenario_t_b_out: float


@dataclass(frozen=True)
class ScenarioReport:
    name: str
    exchanger: str
    base_ua: float
    scenario_ua: float
    diffs: tuple[ExchangerDiff, ...]
    base_solution: Solution
    scenario_solution: Solution


def run_scenario(net: Network, base: Solution, sc: Scenario) -> ScenarioReport:
    modified = solve(net, ua_override={sc.exchanger: sc.ua})
    base_by_name = {e.name: e for e in base.exchangers}
    diffs = []
    for mod in modified.exchangers:
        b = base_by_name[mod.name]
        diffs.append(
            ExchangerDiff(
                name=mod.name,
                base_duty=b.duty,
                scenario_duty=mod.duty,
                delta_duty=mod.duty - b.duty,
                base_t_a_out=b.t_a_out,
                scenario_t_a_out=mod.t_a_out,
                base_t_b_out=b.t_b_out,
                scenario_t_b_out=mod.t_b_out,
            )
        )
    base_ua = next(e.ua for e in net.exchangers if e.name == sc.exchanger)
    return ScenarioReport(
        name=sc.name,
        exchanger=sc.exchanger,
        base_ua=base_ua,
        scenario_ua=sc.ua,
        diffs=tuple(diffs),
        base_solution=base,
        scenario_solution=modified,
    )
