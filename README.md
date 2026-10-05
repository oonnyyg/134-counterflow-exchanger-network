# Counterflow Exchanger Network Calculator

Offline calculation tool for process heat-recovery studies. Given a JSON
description of source streams and counterflow heat exchangers, it computes
outlet temperatures and duties for the whole network, and compares a
retrofit scenario where one exchanger's UA is replaced. Equipment sizing
and selection are out of scope.

Pure Python 3.12+ standard library; no dependencies.

## Units

| Quantity | Unit |
|---|---|
| Temperature | degC |
| Mass flow | kg/s |
| Specific heat capacity cp | kJ/(kg*K) |
| UA (heat-transfer capability) | kW/K |
| Duty / enthalpy flow | kW |

All numbers must be finite. Mass flow and cp must be positive; UA must be
non-negative.

## Network description (JSON)

```json
{
  "sources": {
    "H1": {"temp": 200.0, "mdot": 2.0, "cp": 2.0},
    "C1": {"temp": 30.0, "mdot": 3.0, "cp": 4.0}
  },
  "exchangers": {
    "E1": {"ua": 40.0, "in_a": "H1", "in_b": "C1",
           "out_a": "H1_mid", "out_b": "C1_out"}
  }
}
```

- Each exchanger consumes exactly two inlet streams and produces two
  outlet streams; outlet streams inherit the mass flow and cp of the
  corresponding inlet stream (identity is never crossed).
- Exchangers may be listed in any order; dependencies are resolved
  automatically (forward references allowed).
- Rejected as errors (no partial output): duplicate stream names, cyclic
  dependencies, references to unknown streams, a stream consumed by more
  than one exchanger (no implicit splitting), non-finite or
  non-positive/negative values.

## Model assumptions

- Steady state, constant cp per stream, no phase change, no heat loss.
- Counterflow effectiveness-NTU method. Capacity rate C = mdot * cp
  (kW/K); NTU = UA / Cmin; effectiveness
  `eps = (1 - e^-NTU(1-Cr)) / (1 - Cr*e^-NTU(1-Cr))` with `Cr = Cmin/Cmax`.
- Equal capacity rates (`Cr == 1`) use the limit form `eps = NTU/(1+NTU)`.
- Zero UA or equal inlet temperatures give zero duty.
- Hot/cold sides are decided per exchanger from the inlet temperatures.
- Duties satisfy the energy balance on both sides simultaneously; no
  temperature clamping is applied.
- Network check: total enthalpy flow of all sources equals that of all
  final outlets (reported as `enthalpy_imbalance_kw`, expected ~0).

## Usage

```sh
PYTHONPATH=src python -m hxnet.cli examples/network.json
PYTHONPATH=src python -m hxnet.cli examples/network.json \
    --replace-ua E1 120 --csv detail.csv --json report.json
```

- Without options, the baseline JSON report is printed to stdout.
- `--replace-ua EXCHANGER UA` solves an independent retrofit scenario
  (the baseline configuration is never mutated), re-propagates all
  affected outlets, and reports per-exchanger baseline/scenario/delta
  duties and outlet temperatures.
- `--csv` writes per-exchanger detail rows (both cases when a scenario
  is requested); `--json` writes the full JSON report.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests
```

Covers chained dependencies with forward references, hot/cold side
swapping, equal capacity rates, validation errors, retrofit propagation
and network enthalpy balance.
