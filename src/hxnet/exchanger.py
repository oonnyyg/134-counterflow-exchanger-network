"""Effectiveness-NTU model for a single counterflow exchanger.

Units: temperatures degC, capacity rates kW/K, UA kW/K, duty kW.
"""
import math

from .errors import NetworkError


def _check_finite(name, value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise NetworkError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise NetworkError(f"{name} must be finite, got {value!r}")
    return float(value)


def effectiveness(ntu, c_ratio):
    """Counterflow effectiveness; uses the limit formula at c_ratio == 1."""
    if c_ratio == 1.0:
        return ntu / (1.0 + ntu)
    e = math.exp(-ntu * (1.0 - c_ratio))
    return (1.0 - e) / (1.0 - c_ratio * e)


def exchange(t_in_a, c_a, t_in_b, c_b, ua):
    """Compute outlet temperatures and duty for one exchanger.

    Returns (t_out_a, t_out_b, duty_kw); duty is heat moved from the
    hot side to the cold side (always >= 0). Hot/cold sides are
    decided by inlet temperatures.
    """
    t_in_a = _check_finite("t_in_a", t_in_a)
    t_in_b = _check_finite("t_in_b", t_in_b)
    c_a = _check_finite("capacity rate of side A", c_a)
    c_b = _check_finite("capacity rate of side B", c_b)
    ua = _check_finite("UA", ua)
    if c_a <= 0.0 or c_b <= 0.0:
        raise NetworkError("capacity rates (m_dot * cp) must be positive")
    if ua < 0.0:
        raise NetworkError("UA must be non-negative")

    if t_in_a == t_in_b or ua == 0.0:
        return t_in_a, t_in_b, 0.0

    c_min = min(c_a, c_b)
    c_max = max(c_a, c_b)
    ntu = ua / c_min
    eps = effectiveness(ntu, c_min / c_max)
    duty = eps * c_min * abs(t_in_a - t_in_b)

    if t_in_a > t_in_b:  # A is hot, B is cold
        t_out_a = t_in_a - duty / c_a
        t_out_b = t_in_b + duty / c_b
    else:  # B is hot, A is cold
        t_out_a = t_in_a + duty / c_a
        t_out_b = t_in_b - duty / c_b
    return t_out_a, t_out_b, duty
