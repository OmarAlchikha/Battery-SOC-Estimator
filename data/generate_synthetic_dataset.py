#!/usr/bin/env python3
"""Generate a synthetic 18650 discharge dataset for pipeline validation.

Simulates a 2500 mAh NMC 18650 cell with a Thevenin (OCV-R-RC) truth model
under a pulsed discharge profile, then corrupts the measurements the way a
real INA219 + Arduino Mega logger would:

  * current: constant offset bias + gain error + white noise + LSB quantization
  * voltage: white noise + 4 mV bus-voltage LSB quantization

The offset bias is the important flaw: coulomb counting integrates it into an
ever-growing SOC error, while the Kalman filter's voltage feedback corrects it.

Output CSV columns (same layout the firmware logs, plus ground truth):
    time_ms      milliseconds since log start
    voltage_V    measured terminal voltage (V)
    current_mA   measured current, positive = discharge (mA)
    true_soc     ground-truth SOC in [0, 1]  (only available in simulation!)

Usage:
    python generate_synthetic_dataset.py [-o synthetic_discharge.csv] [--seed 42]
"""

import argparse
import csv

import numpy as np

# ---------------------------------------------------------------- truth cell
CAPACITY_MAH = 2500.0      # true capacity
R0 = 0.060                 # ohmic resistance (ohm)
R1 = 0.030                 # polarization resistance (ohm)
TAU1 = 60.0                # RC time constant (s)
ETA = 1.0                  # coulombic efficiency on discharge

# Typical NMC 18650 OCV curve (SOC -> open-circuit voltage), interpolated.
OCV_SOC = np.array([0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
                    0.60, 0.70, 0.80, 0.90, 1.00])
OCV_V = np.array([3.00, 3.30, 3.45, 3.55, 3.62, 3.67, 3.72,
                  3.79, 3.87, 3.97, 4.08, 4.19])

# ------------------------------------------------------------- sensor errors
CURRENT_BIAS_MA = 30.0     # INA219 offset error (uncalibrated shunt/offset)
CURRENT_GAIN = 1.02        # 2 % shunt tolerance / gain error
CURRENT_NOISE_MA = 4.0     # white noise, 1-sigma
CURRENT_LSB_MA = 0.1       # quantization after INA219 calibration scaling
VOLTAGE_NOISE_V = 0.008    # white noise, 1-sigma
VOLTAGE_LSB_V = 0.004      # INA219 bus voltage LSB

DT = 1.0                   # sample period (s) — matches firmware default

def ocv(soc):
    return np.interp(soc, OCV_SOC, OCV_V)


def load_profile(t):
    """Pulsed discharge: 1.0 A for 5 min, rest 2 min, repeated (A, discharge>0)."""
    period = 300.0 + 120.0
    return 1.0 if (t % period) < 300.0 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--output", default="synthetic_discharge.csv")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--soc-start", type=float, default=1.00)
    ap.add_argument("--soc-stop", type=float, default=0.15,
                    help="stop the simulation when true SOC falls below this")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)

    soc = args.soc_start
    v1 = 0.0                                   # RC branch voltage
    q_as = CAPACITY_MAH * 3.6                  # capacity in ampere-seconds
    a1 = np.exp(-DT / TAU1)

    rows = []
    t = 0.0
    while soc > args.soc_stop and t < 6 * 3600:
        i_true = load_profile(t)               # A, discharge positive

        # terminal voltage from the truth model
        v_term = ocv(soc) - v1 - R0 * i_true

        # corrupt measurements like the INA219 would
        i_meas_ma = CURRENT_GAIN * i_true * 1000.0 + CURRENT_BIAS_MA \
            + rng.normal(0.0, CURRENT_NOISE_MA)
        i_meas_ma = np.round(i_meas_ma / CURRENT_LSB_MA) * CURRENT_LSB_MA
        v_meas = v_term + rng.normal(0.0, VOLTAGE_NOISE_V)
        v_meas = np.round(v_meas / VOLTAGE_LSB_V) * VOLTAGE_LSB_V

        rows.append((int(t * 1000), f"{v_meas:.3f}", f"{i_meas_ma:.1f}",
                     f"{soc:.5f}"))

        # propagate truth one step
        soc -= ETA * i_true * DT / q_as
        v1 = a1 * v1 + R1 * (1.0 - a1) * i_true
        t += DT

    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_ms", "voltage_V", "current_mA", "true_soc"])
        w.writerows(rows)

    hrs = t / 3600.0
    print(f"wrote {len(rows)} samples ({hrs:.2f} h) to {args.output}; "
          f"final true SOC = {soc:.3f}")


if __name__ == "__main__":
    main()
