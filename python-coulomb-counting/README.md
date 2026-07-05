# Coulomb counting

The textbook SOC estimator: integrate the measured current and subtract it
from an assumed starting charge.

```
SOC(t) = SOC₀ − (1/Q) ∫ η·I(τ) dτ          (I > 0 = discharge)
```

## Run

```
python coulomb_counting.py ../data/synthetic_discharge.csv \
    --capacity-mah 2500 --initial-soc 1.0
```

Outputs `coulomb_soc.csv` (time, SOC) and `coulomb_soc.png`. If the input has
a `true_soc` column (the synthetic dataset does), the plot overlays ground
truth and the script prints the final error.

## The initial SOC assumption

Coulomb counting cannot observe SOC — it only observes *changes* in SOC. You
must supply `SOC₀`, and every percent you get it wrong persists for the whole
log, undiminished. In practice `SOC₀` comes from an OCV lookup after a long
rest (hours, so the cell has fully relaxed), which is exactly the side channel
the Kalman filter formalizes and uses continuously.

## Why it drifts

The integral accumulates every measurement imperfection and never forgets:

1. **Current-sensor offset bias** — the dominant term. A constant offset `b`
   integrates into a *linearly growing* SOC error: `b·t/Q`. A modest 30 mA of
   uncalibrated INA219 offset against a 2500 mAh cell costs 1.2 % SOC per
   hour, unbounded. (This is deliberately baked into the synthetic dataset —
   you can watch it happen.)
2. **Gain error** — shunt-resistor tolerance (~1–2 %) scales all counted
   charge, so the error grows in proportion to charge throughput.
3. **Capacity uncertainty** — `Q` fades with age and varies with temperature
   and rate; using nameplate capacity mis-scales the whole trajectory.
4. **Quantization & missed samples** — anything the ADC or the sample clock
   misses is charge that was never counted.
5. **No correction mechanism** — the defining flaw. The estimator is open
   loop: it never looks at the cell voltage, so no error, once made, can ever
   be removed. Errors 1–4 only ever accumulate.

Zero-mean current *noise* is the one thing it handles well — noise largely
cancels in the integral. It's the *systematic* errors that kill it.

This is exactly the gap the Kalman filter in `../python-kalman` closes: it
keeps the coulomb integral as its prediction step but continuously corrects
it against the measured terminal voltage through the OCV(SOC) relationship.
