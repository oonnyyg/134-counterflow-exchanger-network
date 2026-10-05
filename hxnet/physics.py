"""Counterflow exchanger physics via the effectiveness-NTU method.

Units: temperatures in degC, capacity rates (m_dot * cp) in kW/K,
UA in kW/K, heat duty in kW. Only differences of temperature matter,
so degC is interchangeable with K here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangerResult:
    hot_out: float  # degC
    cold_out: float  # degC
    duty: float  # kW, positive = heat moved from hot side to cold side
    effectiveness: float
    ntu: float
    c_hot: float  # kW/K
    c_cold: float  # kW/K


def effectiveness(ntu: float, c_ratio: float) -> float:
    """Counterflow effectiveness. c_ratio = Cmin/Cmax in [0, 1]."""
    if ntu == 0.0:
        return 0.0
    if c_ratio == 1.0:
        # Equal capacity rates: limiting form of the general formula.
        return ntu / (1.0 + ntu)
    e = math.exp(-ntu * (1.0 - c_ratio))
    return (1.0 - e) / (1.0 - c_ratio * e)


def run_exchanger(
    t_a_in: float,
    c_a: float,
    t_b_in: float,
    c_b: float,
    ua: float,
) -> tuple[ExchangerResult, bool]:
    """Solve one exchanger.

    Returns (result, a_is_hot). The hot/cold side is decided by the
    inlet temperatures; equal inlet temperatures give zero duty.
    """
    if t_a_in == t_b_in or ua == 0.0:
        c_hot, c_cold = c_a, c_b
        return (
            ExchangerResult(t_a_in, t_b_in, 0.0, 0.0, 0.0, c_hot, c_cold),
            True,
        )
    if t_a_in > t_b_in:
        t_hot_in, c_hot, t_cold_in, c_cold = t_a_in, c_a, t_b_in, c_b
        a_is_hot = True
    else:
        t_hot_in, c_hot, t_cold_in, c_cold = t_b_in, c_b, t_a_in, c_a
        a_is_hot = False
    c_min = min(c_hot, c_cold)
    c_max = max(c_hot, c_cold)
    ntu = ua / c_min
    eps = effectiveness(ntu, c_min / c_max)
    duty = eps * c_min * (t_hot_in - t_cold_in)
    hot_out = t_hot_in - duty / c_hot
    cold_out = t_cold_in + duty / c_cold
    result = ExchangerResult(hot_out, cold_out, duty, eps, ntu, c_hot, c_cold)
    return result, a_is_hot
