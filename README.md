# Counterflow Exchanger Network Calculator

Offline check tool for process heat-recovery studies. Given a set of
source streams and counterflow exchangers connected in series, it
computes every outlet temperature and heat duty, and compares
single-exchanger retrofit scenarios against the base case. Pure Python
standard library; no equipment sizing is performed.

## Units

| Quantity | Unit |
|---|---|
| Temperature | degC (only differences matter, equivalent to K) |
| Mass flow `mdot` | kg/s |
| Specific heat `cp` | kJ/(kg*K) |
| Heat capacity rate `C = mdot * cp` | kW/K |
| Exchanger capability `ua` | kW/K |
| Heat duty | kW |

All numbers must be finite. `mdot` and `cp` must be positive;
`ua` must be non-negative.

## Model assumptions

- Steady state, constant `cp` per stream, no phase change, no heat loss.
- Each exchanger is counterflow and solved with the
  effectiveness-NTU method: `NTU = UA / Cmin`,
  `eps = (1 - exp(-NTU(1-Cr))) / (1 - Cr*exp(-NTU(1-Cr)))` with
  `Cr = Cmin/Cmax`; for `Cr = 1` the limit `eps = NTU/(1+NTU)` is used.
- Hot/cold sides are decided per exchanger from the inlet temperatures.
  Equal inlet temperatures or `ua = 0` give zero duty.
- `Q = eps * Cmin * (T_hot_in - T_cold_in)`; outlet temperatures follow
  from the energy balance on each side, so both sides always balance.
- Each exchanger output inherits the mass flow and `cp` of its parent
  stream; identities are never crossed (`out_a` belongs to `in_a`).
- Every stream may be consumed at most once (no implicit splitting).
  Duplicate names, cycles, unknown references and double consumption
  are rejected before any calculation; invalid input produces no
  partial results.

## Input format

See `examples/network.json`. Exchangers may reference streams defined
later in the file (forward references); the network is solved in
dependency order. A `scenarios` entry replaces the `ua` of exactly one
exchanger; all affected downstream outlets are repropagated and
compared per exchanger against the base case, which is never modified.

## Usage

```
python -m hxnet examples/network.json --csv detail.csv --json report.json
python -m hxnet examples/network.json          # JSON report to stdout
```

The JSON report includes per-exchanger results for the base case and
each scenario, per-exchanger duty/outlet differences, and a whole
network enthalpy check (sum of source enthalpy flows vs. sum of final
outlet enthalpy flows, relative to 0 degC).

## Tests

```
python -m unittest discover -s tests
```

Covers chained dependencies with forward references, hot/cold side
swapping, equal capacity rates, zero-duty degenerate cases, and all
validation rejections.
