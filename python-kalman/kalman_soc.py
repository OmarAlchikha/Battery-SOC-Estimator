"""Extended Kalman filter SOC estimator on the OCV-R-RC battery model.

State:        x = [SOC, V1]ᵀ        (V1 = RC-branch polarization voltage)
Input:        u = I (A, discharge > 0)
Measurement:  z = terminal voltage V (V)

Prediction is exactly coulomb counting (plus the RC state); the update step
is what coulomb counting lacks — a voltage-based correction through the
OCV(SOC) relationship. An *extended* KF is needed because the measurement
z = OCV(SOC) − V1 − R0·I is nonlinear in SOC; we linearize with
H = [dOCV/dSOC, −1] at the current estimate. The state transition itself is
already linear:

    F = [[1, 0],
         [0, exp(−dt/τ1)]]
"""

import numpy as np

from battery_model import BatteryModel


class SocEKF:
    def __init__(self, model: BatteryModel, soc0=0.5, p0=None, q=None, r=None):
        """
        soc0 : initial SOC guess (deliberately allowed to be wrong — the
               filter converges to the voltage-consistent value)
        p0   : initial state covariance. Default is confident about V1 (starts
               at 0 after rest) but uncertain about SOC.
        q    : process noise covariance. The SOC entry encodes how much we
               distrust the coulomb integral per step (sensor bias/gain error
               leaking in); the V1 entry encodes RC-model mismatch.
        r    : measurement noise variance (voltage sensor noise + model error).
        """
        self.m = model
        self.x = np.array([soc0, 0.0])
        self.P = np.diag([0.05, 1e-4]) if p0 is None else np.asarray(p0)
        self.Q = np.diag([1e-10, 1e-8]) if q is None else np.asarray(q)
        self.R = 2e-4 if r is None else r

    def step(self, current_a, voltage_v, dt):
        """One predict/update cycle. Returns the updated [SOC, V1] estimate."""
        m = self.m

        # ---- predict (this *is* coulomb counting, plus the RC state) ----
        soc_pred, v1_pred = m.step_state(self.x[0], self.x[1], current_a, dt)
        x_pred = np.array([soc_pred, v1_pred])
        a = np.exp(-dt / m.tau1)
        F = np.array([[1.0, 0.0],
                      [0.0, a]])
        P_pred = F @ self.P @ F.T + self.Q

        # ---- update: correct against measured terminal voltage ----
        z_pred = m.terminal_voltage(soc_pred, v1_pred, current_a)
        H = np.array([m.docv_dsoc(soc_pred), -1.0])
        s = H @ P_pred @ H + self.R                    # innovation variance
        k = (P_pred @ H) / s                           # Kalman gain (2,)
        innov = voltage_v - z_pred
        self.x = x_pred + k * innov
        self.P = (np.eye(2) - np.outer(k, H)) @ P_pred
        # keep covariance symmetric against numerical round-off
        self.P = 0.5 * (self.P + self.P.T)

        self.x[0] = np.clip(self.x[0], 0.0, 1.0)
        return self.x


def run_filter(t, current_a, voltage_v, model=None, soc0=0.5, **kw):
    """Run the EKF over a whole log. Returns (soc_est, v1_est) arrays."""
    model = model or BatteryModel()
    ekf = SocEKF(model, soc0=soc0, **kw)
    n = len(t)
    soc = np.empty(n)
    v1 = np.empty(n)
    soc[0], v1[0] = ekf.x
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        soc[k], v1[k] = ekf.step(current_a[k], voltage_v[k], dt)
    return soc, v1
