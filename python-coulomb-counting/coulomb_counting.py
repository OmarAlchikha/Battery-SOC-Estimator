#!/usr/bin/env python3
"""Coulomb-counting SOC estimator for logged INA219 current data.

SOC(t) = SOC_0 - (1/Q) * integral( eta * I(t) dt ),   I > 0 = discharge

Reads a CSV with columns `time_ms` (or `time_s`), `current_mA` and optionally
`true_soc` (present in the synthetic dataset). Integrates with the trapezoidal
rule, plots the trajectory, and writes an output CSV with the estimate.

Coulomb counting is *open loop*: it needs the initial SOC handed to it
(--initial-soc) and has no mechanism to correct any error afterwards — see
the drift discussion in this folder's README.

Usage:
    python coulomb_counting.py ../data/synthetic_discharge.csv \
        --capacity-mah 2500 --initial-soc 1.0
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_log(path):
    """Return (t_seconds, current_A, true_soc_or_None) from a logger CSV."""
    df = pd.read_csv(path)
    if "time_s" in df.columns:
        t = df["time_s"].to_numpy(dtype=float)
    else:
        t = df["time_ms"].to_numpy(dtype=float) / 1000.0
    i_a = df["current_mA"].to_numpy(dtype=float) / 1000.0
    true_soc = df["true_soc"].to_numpy(dtype=float) if "true_soc" in df else None
    return t, i_a, true_soc


def coulomb_count(t, current_a, capacity_mah, initial_soc=1.0, eta=1.0):
    """Trapezoidal integration of current into SOC. Discharge current > 0."""
    q_as = capacity_mah * 3.6  # mAh -> ampere-seconds
    dt = np.diff(t)
    charge_as = np.concatenate(
        ([0.0], np.cumsum(0.5 * (current_a[1:] + current_a[:-1]) * dt)))
    return initial_soc - eta * charge_as / q_as


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="logger CSV (time_ms,voltage_V,current_mA[,true_soc])")
    ap.add_argument("--capacity-mah", type=float, default=2500.0,
                    help="assumed cell capacity (default 2500 mAh)")
    ap.add_argument("--initial-soc", type=float, default=1.0,
                    help="assumed SOC at t=0 (default 1.0 = full)")
    ap.add_argument("--eta", type=float, default=1.0,
                    help="coulombic efficiency (default 1.0)")
    ap.add_argument("-o", "--output", default="coulomb_soc.csv")
    ap.add_argument("--plot", default="coulomb_soc.png")
    args = ap.parse_args()

    t, i_a, true_soc = load_log(args.csv)
    soc = coulomb_count(t, i_a, args.capacity_mah, args.initial_soc, args.eta)

    pd.DataFrame({"time_s": t, "soc_coulomb": soc}).to_csv(args.output,
                                                           index=False)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(t / 3600.0, soc * 100, label="coulomb counting", color="tab:blue")
    if true_soc is not None:
        ax.plot(t / 3600.0, true_soc * 100, label="true SOC", color="black",
                linestyle="--", linewidth=1)
        err = (soc - true_soc) * 100
        print(f"final error vs truth: {err[-1]:+.2f} % SOC "
              f"(max |error| {np.max(np.abs(err)):.2f} %)")
    ax.set_xlabel("time (h)")
    ax.set_ylabel("SOC (%)")
    ax.set_title("Coulomb-counting SOC estimate")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.plot, dpi=140)
    print(f"wrote {args.output} and {args.plot}; "
          f"final SOC estimate = {soc[-1]*100:.1f} %")


if __name__ == "__main__":
    main()
