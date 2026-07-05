"""OCV-R-RC (first-order Thevenin) battery model for an NMC 18650 cell.

Model choice — why OCV-R-RC rather than plain OCV-R:

An OCV-R model says V = OCV(SOC) − R0·I: the terminal voltage snaps
instantaneously when the load changes. A real 18650 doesn't — charge-transfer
and diffusion dynamics make the voltage relax over tens of seconds after a
load step. Under the pulsed discharge profile we log (and any realistic
load), an OCV-R filter sees that relaxation tail as pure measurement error
and has only two bad options: trust the voltage (SOC estimate gets yanked
around after every load step) or inflate R and barely correct at all. One RC
pair captures the dominant relaxation at the cost of a single extra state,
and its parameters are easy to pull from a pulse test (see below). A second
RC pair mainly refines long-time-constant diffusion and is not worth the
extra identification effort at this stage — so: one RC pair.

Discrete-time model (dt sample period, I > 0 = discharge):

    SOC[k+1] = SOC[k] − η·I[k]·dt / Q
    V1[k+1]  = a·V1[k] + R1·(1−a)·I[k],      a = exp(−dt/τ1)
    V[k]     = OCV(SOC[k]) − V1[k] − R0·I[k]

Parameter identification from a real pulse test:
    R0 = instantaneous voltage step at load on/off, divided by the current step
    R1 = remaining (slow) voltage sag at end of pulse / current
    τ1 = time for ~63 % of the post-pulse recovery
    OCV curve = rested voltage at several SOC levels (or a slow C/25 discharge)
"""

import numpy as np


class BatteryModel:
    # Typical NMC 18650 OCV curve. Replace with your own cell's measured
    # points once you have real rest-voltage data.
    OCV_SOC = np.array([0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
                        0.60, 0.70, 0.80, 0.90, 1.00])
    OCV_V = np.array([3.00, 3.30, 3.45, 3.55, 3.62, 3.67, 3.72,
                      3.79, 3.87, 3.97, 4.08, 4.19])

    def __init__(self, capacity_mah=2500.0, r0=0.060, r1=0.030, tau1=60.0,
                 eta=1.0):
        self.q_as = capacity_mah * 3.6   # capacity in ampere-seconds
        self.r0 = r0
        self.r1 = r1
        self.tau1 = tau1
        self.eta = eta

    def ocv(self, soc):
        return np.interp(soc, self.OCV_SOC, self.OCV_V)

    def docv_dsoc(self, soc, h=1e-4):
        """Slope of the OCV curve — the measurement Jacobian's SOC entry."""
        lo = np.clip(soc - h, 0.0, 1.0)
        hi = np.clip(soc + h, 0.0, 1.0)
        return (self.ocv(hi) - self.ocv(lo)) / (hi - lo)

    def step_state(self, soc, v1, current_a, dt):
        """Propagate [SOC, V1] one sample under current_a (discharge > 0)."""
        a = np.exp(-dt / self.tau1)
        soc_next = soc - self.eta * current_a * dt / self.q_as
        v1_next = a * v1 + self.r1 * (1.0 - a) * current_a
        return soc_next, v1_next

    def terminal_voltage(self, soc, v1, current_a):
        return self.ocv(soc) - v1 - self.r0 * current_a
