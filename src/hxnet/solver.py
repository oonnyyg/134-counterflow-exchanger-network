"""Network assembly, validation and dependency-ordered solving."""
from .errors import NetworkError
from .exchanger import _check_finite, exchange


def _positive(name, value):
    v = _check_finite(name, value)
    if v <= 0.0:
        raise NetworkError(f"{name} must be positive, got {v}")
    return v


def _non_negative(name, value):
    v = _check_finite(name, value)
    if v < 0.0:
        raise NetworkError(f"{name} must be non-negative, got {v}")
    return v


def _parse_sources(spec):
    raw = spec.get("sources")
    if not isinstance(raw, dict) or not raw:
        raise NetworkError("'sources' must be a non-empty object")
    sources = {}
    for name, s in raw.items():
        if not isinstance(s, dict):
            raise NetworkError(f"source {name!r} must be an object")
        try:
            temp = _check_finite(f"source {name!r} temp", s["temp"])
            mdot = _positive(f"source {name!r} mdot", s["mdot"])
            cp = _positive(f"source {name!r} cp", s["cp"])
        except KeyError as k:
            raise NetworkError(f"source {name!r} missing key {k}") from None
        sources[name] = {"temp": temp, "mdot": mdot, "cp": cp}
    return sources


def _parse_exchangers(spec):
    raw = spec.get("exchangers", {})
    if not isinstance(raw, dict):
        raise NetworkError("'exchangers' must be an object")
    exchangers = {}
    for name, e in raw.items():
        if not isinstance(e, dict):
            raise NetworkError(f"exchanger {name!r} must be an object")
        try:
            ua = _non_negative(f"exchanger {name!r} ua", e["ua"])
            in_a, in_b = e["in_a"], e["in_b"]
            out_a, out_b = e["out_a"], e["out_b"]
        except KeyError as k:
            raise NetworkError(f"exchanger {name!r} missing key {k}") from None
        for label, v in (("in_a", in_a), ("in_b", in_b),
                         ("out_a", out_a), ("out_b", out_b)):
            if not isinstance(v, str) or not v:
                raise NetworkError(
                    f"exchanger {name!r} {label} must be a stream name")
        if in_a == in_b:
            raise NetworkError(f"exchanger {name!r} consumes stream {in_a!r} twice")
        if out_a == out_b:
            raise NetworkError(f"exchanger {name!r} produces stream {out_a!r} twice")
        exchangers[name] = {"ua": ua, "in_a": in_a, "in_b": in_b,
                            "out_a": out_a, "out_b": out_b}
    return exchangers


def _validate_topology(sources, exchangers):
    defined = set(sources)
    consumed = {}
    for name, e in exchangers.items():
        for side in ("in_a", "in_b"):
            s = e[side]
            if s in consumed:
                raise NetworkError(
                    f"stream {s!r} is consumed by both "
                    f"{consumed[s]!r} and {name!r}; implicit splitting "
                    f"is not allowed")
            consumed[s] = name
    for name, e in exchangers.items():
        for side in ("out_a", "out_b"):
            s = e[side]
            if s in defined:
                raise NetworkError(f"duplicate stream name {s!r}")
            defined.add(s)
    for name, e in exchangers.items():
        for side in ("in_a", "in_b"):
            if e[side] not in defined:
                raise NetworkError(
                    f"exchanger {name!r} references unknown stream {e[side]!r}")

    # Cycle check: exchanger -> exchanger it depends on.
    producer = {}
    for name, e in exchangers.items():
        producer[e["out_a"]] = name
        producer[e["out_b"]] = name
    deps = {n: set() for n in exchangers}
    for name, e in exchangers.items():
        for side in ("in_a", "in_b"):
            p = producer.get(e[side])
            if p is not None:
                deps[name].add(p)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in deps}

    def visit(node, stack):
        color[node] = GRAY
        for dep in deps[node]:
            if color[dep] == GRAY:
                cycle = " -> ".join(stack + [node, dep])
                raise NetworkError(f"cyclic dependency detected: {cycle}")
            if color[dep] == WHITE:
                visit(dep, stack + [node])
        color[node] = BLACK

    for n in deps:
        if color[n] == WHITE:
            visit(n, [])


def solve_network(spec, ua_overrides=None):
    """Solve a network spec; returns a result dict.

    ua_overrides: optional {exchanger_name: new_ua} applied without
    mutating the caller's spec.
    """
    if not isinstance(spec, dict):
        raise NetworkError("network spec must be a JSON object")
    sources = _parse_sources(spec)
    exchangers = _parse_exchangers(spec)
    _validate_topology(sources, exchangers)
    if ua_overrides:
        for name, ua in ua_overrides.items():
            if name not in exchangers:
                raise NetworkError(f"override targets unknown exchanger {name!r}")
            exchangers[name]["ua"] = _non_negative(
                f"override ua of {name!r}", ua)

    streams = {n: dict(s) for n, s in sources.items()}
    results = {}
    pending = dict(exchangers)
    while pending:
        progressed = False
        for name, e in list(pending.items()):
            a = streams.get(e["in_a"])
            b = streams.get(e["in_b"])
            if a is None or b is None:
                continue
            c_a = a["mdot"] * a["cp"]
            c_b = b["mdot"] * b["cp"]
            t_out_a, t_out_b, duty = exchange(
                a["temp"], c_a, b["temp"], c_b, e["ua"])
            streams[e["out_a"]] = {"temp": t_out_a, "mdot": a["mdot"],
                                   "cp": a["cp"]}
            streams[e["out_b"]] = {"temp": t_out_b, "mdot": b["mdot"],
                                   "cp": b["cp"]}
            hot_side, cold_side = ("a", "b") if a["temp"] > b["temp"] else ("b", "a")
            results[name] = {
                "ua": e["ua"],
                "in_a": e["in_a"], "in_b": e["in_b"],
                "out_a": e["out_a"], "out_b": e["out_b"],
                "t_in_a": a["temp"], "t_in_b": b["temp"],
                "t_out_a": t_out_a, "t_out_b": t_out_b,
                "c_a": c_a, "c_b": c_b,
                "hot_side": hot_side, "cold_side": cold_side,
                "duty_kw": duty,
            }
            del pending[name]
            progressed = True
        if not progressed:
            raise NetworkError("unresolvable exchanger dependencies")

    consumed = set()
    for e in exchangers.values():
        consumed.add(e["in_a"])
        consumed.add(e["in_b"])
    final_outlets = sorted(set(streams) - consumed - set(sources))

    def enthalpy(name):
        s = streams[name]
        return s["mdot"] * s["cp"] * s["temp"]

    source_h = sum(enthalpy(n) for n in sources)
    outlet_h = sum(enthalpy(n) for n in final_outlets)
    return {
        "streams": streams,
        "exchangers": results,
        "final_outlets": final_outlets,
        "total_duty_kw": sum(r["duty_kw"] for r in results.values()),
        "source_enthalpy_kw": source_h,
        "outlet_enthalpy_kw": outlet_h,
        "enthalpy_imbalance_kw": source_h - outlet_h,
    }
