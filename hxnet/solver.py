"""Solve a validated network in dependency order."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Network
from .physics import run_exchanger


@dataclass(frozen=True)
class StreamState:
    name: str
    temp: float  # degC
    mdot: float  # kg/s
    cp: float  # kJ/(kg*K)

    @property
    def capacity(self) -> float:  # kW/K
        return self.mdot * self.cp

    @property
    def enthalpy_flow(self) -> float:  # kW, relative to 0 degC
        return self.capacity * self.temp


@dataclass(frozen=True)
class ExchangerSolution:
    name: str
    ua: float
    in_a: str
    in_b: str
    out_a: str
    out_b: str
    t_a_in: float
    t_b_in: float
    t_a_out: float
    t_b_out: float
    duty: float  # kW
    effectiveness: float
    ntu: float
    a_side: str  # "hot" or "cold"


@dataclass(frozen=True)
class Solution:
    exchangers: tuple[ExchangerSolution, ...]
    streams: dict  # name -> StreamState, sources + all outputs
    final_streams: tuple[str, ...]  # streams never consumed downstream
    source_enthalpy: float  # kW
    final_enthalpy: float  # kW
    enthalpy_imbalance: float  # kW, should be ~0


def solve(net: Network, ua_override: dict | None = None) -> Solution:
    """Solve the network. ua_override maps exchanger name -> new UA.

    The base network object is never mutated; overrides only apply to
    the returned solution.
    """
    ua_override = ua_override or {}
    streams: dict[str, StreamState] = {
        s.name: StreamState(s.name, s.temp, s.mdot, s.cp) for s in net.sources
    }
    solutions: list[ExchangerSolution] = []
    pending = list(net.exchangers)
    while pending:
        for exch in pending[:]:
            if exch.in_a in streams and exch.in_b in streams:
                break
        else:  # pragma: no cover - validation guarantees progress
            raise RuntimeError("unsolvable dependency order")
        pending.remove(exch)
        a = streams[exch.in_a]
        b = streams[exch.in_b]
        ua = ua_override.get(exch.name, exch.ua)
        result, a_is_hot = run_exchanger(
            a.temp, a.capacity, b.temp, b.capacity, ua
        )
        if a_is_hot:
            t_a_out, t_b_out = result.hot_out, result.cold_out
        else:
            t_a_out, t_b_out = result.cold_out, result.hot_out
        # Outputs inherit flow and cp of their parent stream; the
        # identity (out_a <-> in_a, out_b <-> in_b) is preserved.
        streams[exch.out_a] = StreamState(exch.out_a, t_a_out, a.mdot, a.cp)
        streams[exch.out_b] = StreamState(exch.out_b, t_b_out, b.mdot, b.cp)
        solutions.append(
            ExchangerSolution(
                name=exch.name,
                ua=ua,
                in_a=exch.in_a,
                in_b=exch.in_b,
                out_a=exch.out_a,
                out_b=exch.out_b,
                t_a_in=a.temp,
                t_b_in=b.temp,
                t_a_out=t_a_out,
                t_b_out=t_b_out,
                duty=result.duty,
                effectiveness=result.effectiveness,
                ntu=result.ntu,
                a_side="hot" if a_is_hot else "cold",
            )
        )
    consumed = {ref for e in net.exchangers for ref in (e.in_a, e.in_b)}
    final_names = tuple(n for n in streams if n not in consumed)
    source_h = sum(streams[s.name].enthalpy_flow for s in net.sources)
    final_h = sum(streams[n].enthalpy_flow for n in final_names)
    return Solution(
        exchangers=tuple(solutions),
        streams=streams,
        final_streams=final_names,
        source_enthalpy=source_h,
        final_enthalpy=final_h,
        enthalpy_imbalance=final_h - source_h,
    )
