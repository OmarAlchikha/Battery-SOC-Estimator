#!/usr/bin/env python3
"""Compare Kalman-filter SOC against coulomb counting on the same log.

Runs both estimators on one logger CSV and plots them together (plus ground
truth if the file has a `true_soc` column). To showcase the difference, the
EKF is intentionally started from a *wrong* initial SOC (--ekf-soc0, default
0.5) while coulomb counting gets the correct one — the EKF converges anyway,
and coulomb counting drifts even from a perfect start.

Also writes ekf_soc.csv (time_s, soc, v1) so the Simulink model can
cross-validate against the exact same result.

Usage:
    python compare_soc.py ../data/synthetic_discharge.csv
"""

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "python-coulomb-counting"))
from coulomb_counting import coulomb_count, load_log  # noqa: E402

from battery_model import BatteryModel  # noqa: E402
from kalman_soc import run_filter  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="logger CSV (time_ms,voltage_V,current_mA[,true_soc])")
    ap.add_argument("--capacity-mah", type=float, default=2500.0)
    ap.add_argument("--cc-soc0", type=float, default=1.0,
                    help="initial SOC given to coulomb counting")
    ap.add_argument("--ekf-soc0", type=float, default=0.5,
                    help="(wrong on purpose) initial SOC given to the EKF")
    ap.add_argument("--plot", default="soc_comparison.png")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    t, i_a, true_soc = load_log(args.csv)
    v = df["voltage_V"].to_numpy(dtype=float)

    soc_cc = coulomb_count(t, i_a, args.capacity_mah, args.cc_soc0)

    model = BatteryModel(capacity_mah=args.capacity_mah)
    soc_ekf, v1_ekf = run_filter(t, i_a, v, model=model, soc0=args.ekf_soc0)

    pd.DataFrame({"time_s": t, "soc_ekf": soc_ekf, "v1_ekf": v1_ekf}) \
        .to_csv("ekf_soc.csv", index=False)

    # ---- report ----
    th = t / 3600.0
    if true_soc is not None:
        e_cc = (soc_cc - true_soc) * 100
        e_ekf = (soc_ekf - true_soc) * 100
        half = len(t) // 2  # judge EKF after its convergence transient
        print(f"coulomb counting (correct SOC0={args.cc_soc0}): "
              f"final error {e_cc[-1]:+.2f} %")
        print(f"EKF (wrong SOC0={args.ekf_soc0}):              "
              f"final error {e_ekf[-1]:+.2f} %, "
              f"RMS over 2nd half {np.sqrt(np.mean(e_ekf[half:]**2)):.2f} %")

    # ---- plot ----
    if true_soc is not None:
        fig, (ax, axe) = plt.subplots(2, 1, figsize=(9, 7), sharex=True,
                                      height_ratios=[2, 1])
    else:
        fig, ax = plt.subplots(figsize=(9, 5))

    ax.plot(th, soc_cc * 100, color="tab:blue",
            label=f"coulomb counting (SOC₀={args.cc_soc0:.0%}, correct)")
    ax.plot(th, soc_ekf * 100, color="tab:red",
            label=f"EKF (SOC₀={args.ekf_soc0:.0%}, wrong on purpose)")
    if true_soc is not None:
        ax.plot(th, true_soc * 100, "k--", linewidth=1, label="true SOC")
    ax.set_ylabel("SOC (%)")
    ax.set_title("SOC: coulomb counting vs extended Kalman filter")
    ax.legend()
    ax.grid(alpha=0.3)

    if true_soc is not None:
        axe.plot(th, e_cc, color="tab:blue", label="coulomb counting error")
        axe.plot(th, e_ekf, color="tab:red", label="EKF error")
        axe.axhline(0, color="black", linewidth=0.8)
        axe.set_xlabel("time (h)")
        axe.set_ylabel("error (% SOC)")
        axe.legend()
        axe.grid(alpha=0.3)
        axe.set_ylim(-10, 10)
    else:
        ax.set_xlabel("time (h)")

    fig.tight_layout()
    fig.savefig(args.plot, dpi=140)
    print(f"wrote {args.plot} and ekf_soc.csv")


if __name__ == "__main__":
    main()
