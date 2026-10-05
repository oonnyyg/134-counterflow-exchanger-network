"""Network definition, parsing and validation.

JSON schema (all numbers must be finite):

{
  "sources": [
    {"name": "H1", "temp": 200.0, "mdot": 2.0, "cp": 2.0}
  ],
  "exchangers": [
    {"name": "E1", "ua": 10.0,
     "in_a": "H1", "in_b": "C1",
     "out_a": "H1_E1", "out_b": "C1_E1"}
  ],
  "scenarios": [
    {"name": "E2-upgrade", "exchanger": "E2", "ua": 25.0}
  ]
}

Exchanger inputs may reference sources or outputs of other exchangers
(forward references allowed; solved in dependency order). Each stream
may be consumed at most once: no implicit splitting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


class NetworkError(ValueError):
    """Raised for any invalid network description."""


@dataclass(frozen=True)
class Source:
    name: str
    temp: float  # degC
    mdot: float  # kg/s
    cp: float  # kJ/(kg*K)

    @property
    def capacity(self) -> float:  # kW/K
        return self.mdot * self.cp


@dataclass(frozen=True)
class Exchanger:
    name: str
    ua: float  # kW/K
    in_a: str
    in_b: str
    out_a: str
    out_b: str


@dataclass(frozen=True)
class Scenario:
    name: str
    exchanger: str
    ua: float  # kW/K, replacement value


@dataclass(frozen=True)
class Network:
    sources: tuple[Source, ...]
    exchangers: tuple[Exchanger, ...]
    scenarios: tuple[Scenario, ...]


def _finite(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NetworkError(f"{field}: expected a number, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise NetworkError(f"{field}: value must be finite, got {value!r}")
    return value


def _name(value, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise NetworkError(f"{field}: expected a non-empty string")
    return value


def parse_network(data: dict) -> Network:
    if not isinstance(data, dict):
        raise NetworkError("top level must be a JSON object")
    sources = []
    for i, raw in enumerate(data.get("sources", [])):
        try:
            sources.append(
                Source(
                    name=_name(raw.get("name"), "name"),
                    temp=_finite(raw.get("temp"), "temp"),
                    mdot=_finite(raw.get("mdot"), "mdot"),
                    cp=_finite(raw.get("cp"), "cp"),
                )
            )
        except NetworkError as exc:
            raise NetworkError(f"sources[{i}]: {exc}") from exc
        if sources[-1].mdot <= 0:
            raise NetworkError(f"sources[{i}]: mdot must be positive")
        if sources[-1].cp <= 0:
            raise NetworkError(f"sources[{i}]: cp must be positive")
    exchangers = []
    for i, raw in enumerate(data.get("exchangers", [])):
        try:
            exchangers.append(
                Exchanger(
                    name=_name(raw.get("name"), "name"),
                    ua=_finite(raw.get("ua"), "ua"),
                    in_a=_name(raw.get("in_a"), "in_a"),
                    in_b=_name(raw.get("in_b"), "in_b"),
                    out_a=_name(raw.get("out_a"), "out_a"),
                    out_b=_name(raw.get("out_b"), "out_b"),
                )
            )
        except NetworkError as exc:
            raise NetworkError(f"exchangers[{i}]: {exc}") from exc
        if exchangers[-1].ua < 0:
            raise NetworkError(f"exchangers[{i}]: ua must be non-negative")
    scenarios = []
    for i, raw in enumerate(data.get("scenarios", [])):
        try:
            scenarios.append(
                Scenario(
                    name=_name(raw.get("name"), "name"),
                    exchanger=_name(raw.get("exchanger"), "exchanger"),
                    ua=_finite(raw.get("ua"), "ua"),
                )
            )
        except NetworkError as exc:
            raise NetworkError(f"scenarios[{i}]: {exc}") from exc
        if scenarios[-1].ua < 0:
            raise NetworkError(f"scenarios[{i}]: ua must be non-negative")
    network = Network(
        tuple(sources), tuple(exchangers), tuple(scenarios)
    )
    _validate(network)
    return network


def _validate(net: Network) -> None:
    stream_names: set[str] = set()
    for src in net.sources:
        if src.name in stream_names:
            raise NetworkError(f"duplicate stream name: {src.name!r}")
        stream_names.add(src.name)
    exch_names: set[str] = set()
    for exch in net.exchangers:
        if exch.name in exch_names:
            raise NetworkError(f"duplicate exchanger name: {exch.name!r}")
        exch_names.add(exch.name)
        for out in (exch.out_a, exch.out_b):
            if out in stream_names:
                raise NetworkError(f"duplicate stream name: {out!r}")
            stream_names.add(out)
        if exch.in_a == exch.in_b:
            raise NetworkError(
                f"exchanger {exch.name!r} consumes stream {exch.in_a!r} twice"
            )
    consumed: set[str] = set()
    for exch in net.exchangers:
        for ref in (exch.in_a, exch.in_b):
            if ref not in stream_names:
                raise NetworkError(
                    f"exchanger {exch.name!r}: unknown stream {ref!r}"
                )
            if ref in consumed:
                raise NetworkError(
                    f"stream {ref!r} is consumed more than once "
                    "(implicit splitting is not allowed)"
                )
            consumed.add(ref)
    # Cycle check: an exchanger may only consume streams defined by
    # sources or by exchangers already solved (Kahn's algorithm).
    available = {src.name for src in net.sources}
    pending = list(net.exchangers)
    while pending:
        progressed = False
        for exch in pending[:]:
            if exch.in_a in available and exch.in_b in available:
                available.add(exch.out_a)
                available.add(exch.out_b)
                pending.remove(exch)
                progressed = True
        if not progressed:
            names = ", ".join(e.name for e in pending)
            raise NetworkError(f"cyclic dependency among exchangers: {names}")
    for sc in net.scenarios:
        if sc.exchanger not in exch_names:
            raise NetworkError(
                f"scenario {sc.name!r}: unknown exchanger {sc.exchanger!r}"
            )
