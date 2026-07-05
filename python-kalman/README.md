# Kalman-filter SOC estimator

Extended Kalman filter over an **OCV-R-RC** (first-order Thevenin) model.

```
State:        x = [SOC, V1]         V1 = RC polarization voltage
Prediction:   SOC ← SOC − η·I·dt/Q            (this IS coulomb counting)
              V1  ← e^(−dt/τ1)·V1 + R1(1−e^(−dt/τ1))·I
Measurement:  V = OCV(SOC) − V1 − R0·I        (nonlinear in SOC → EKF)
Jacobian:     H = [dOCV/dSOC, −1]
```

## Run

```
python compare_soc.py ../data/synthetic_discharge.csv
```

Produces `soc_comparison.png` (both estimators + ground truth + error traces)
and `ekf_soc.csv` (used by `/simulink` for cross-validation). On the synthetic
dataset:

| estimator | initial SOC | final error |
|---|---|---|
| coulomb counting | 100 % (correct) | ≈ −5 % and growing |
| EKF | 50 % (**wrong on purpose**) | ≈ ±0.5 % |

![comparison](soc_comparison.png)

## Why OCV-R-RC instead of plain OCV-R

An OCV-R model makes terminal voltage respond instantly to load changes. A
real 18650 relaxes over tens of seconds after a load step (charge transfer +
diffusion). Under a pulsed load, an OCV-R filter must interpret that
relaxation tail as measurement error, forcing a bad trade: a high Kalman gain
lets every load step yank the SOC estimate, a low gain throws away the
voltage correction that is the entire point. One RC pair models the dominant
relaxation for the price of one extra, easily-identified state. A second RC
pair mostly refines slow diffusion behaviour — not worth the identification
effort here. Full argument in `battery_model.py`'s docstring, which also
describes how to pull R0/R1/τ1 from a real pulse test.

## Why the EKF fixes coulomb counting

The EKF's *prediction* step is literally the coulomb counter, so it inherits
all of its errors — but the *update* step compares predicted terminal voltage
against the measured one and pulls SOC toward the voltage-consistent value
through the OCV(SOC) slope. Current-sensor bias still pushes the estimate off
truth every step, but the voltage feedback pushes back, so the error stays
**bounded** instead of growing linearly. The same mechanism erases a wrong
initial SOC within minutes.

## Tuning knobs (in `kalman_soc.py`)

- `Q[0,0]` (SOC process noise): how much you distrust the coulomb integral.
  Bigger → leans harder on voltage (faster correction, noisier estimate).
- `Q[1,1]`: RC-model mismatch allowance.
- `R`: voltage measurement variance (sensor noise **plus** OCV/model error).
- `P0[0,0]`: initial SOC uncertainty; large values make initial convergence
  fast.

One caveat that carries over to real data: the NMC OCV curve is flat around
40–60 % SOC, so the voltage carries little SOC information there
(`dOCV/dSOC` small → small gain) and the filter temporarily behaves more
like a pure coulomb counter. That's visible as slightly slower correction
mid-discharge and is expected.
