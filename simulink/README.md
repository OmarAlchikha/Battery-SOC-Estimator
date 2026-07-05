# Simulink cross-validation

A script-built Simulink equivalent of the Python EKF, used to cross-validate
the two implementations on the same dataset. No `.slx` is checked in — the
model is constructed programmatically by `build_soc_ekf_model.m` (From
Workspace inputs → one MATLAB Function block holding the EKF → To Workspace
outputs), so the whole model lives in reviewable, diffable text.

## Run

In MATLAB (requires Simulink; tested structure targets R2021a+), from this
folder:

```matlab
run_soc_ekf                    % uses ../data/synthetic_discharge.csv
```

or explicitly:

```matlab
run_soc_ekf('../data/synthetic_discharge.csv', '../python-kalman/ekf_soc.csv')
```

Run `python-kalman/compare_soc.py` first — it writes `ekf_soc.csv`, the
Python EKF trajectory that the script overlays and diffs against.

## What "passing" looks like

The MATLAB Function block replicates `kalman_soc.py` line for line: same
state, same OCV table, same parameters, same Q/R tuning, same
deliberately-wrong SOC₀ = 0.5. Both consume identical inputs, so agreement
should be at numerical-precision level; `run_soc_ekf` prints the max SOC
discrepancy (after the first 5 minutes — the two runners bookkeep the very
first sample differently, a transient that decays below 0.01 % SOC) and warns
above **0.1 % SOC**. The block's math was verified by transliterating it back
to Python and diffing against `kalman_soc.py` on the synthetic dataset:
post-transient agreement is < 0.008 % SOC. A larger gap means the two
implementations have drifted apart (parameter edited on one side only, or a
genuine bug) — the parameter blocks in both files are commented to be kept
in sync.

> Note: these scripts were authored without a MATLAB license available in the
> development environment, so they are untested against a live Simulink
> session. The block paths and APIs used (`add_block`, `Stateflow.EMChart`
> script injection, `sim` with `ReturnWorkspaceOutputs`) are standard, but if
> a block path differs in your release, the fix should be one-line.
