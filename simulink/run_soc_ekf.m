function run_soc_ekf(csv_path, python_result_path)
%RUN_SOC_EKF Simulate the script-built EKF model and cross-validate vs Python.
%   run_soc_ekf()                       % defaults to the synthetic dataset
%   run_soc_ekf('../data/synthetic_discharge.csv', ...
%               '../python-kalman/ekf_soc.csv')
%
%   Builds the model (build_soc_ekf_model.m), feeds it the logged
%   current/voltage, and — if python-kalman/compare_soc.py has been run so
%   ekf_soc.csv exists — overlays both SOC trajectories and reports the max
%   discrepancy. Since both implementations use identical equations,
%   parameters and tuning, agreement should be at floating-point/interp
%   level (well under 0.1 % SOC); anything larger means the two EKFs have
%   diverged and one of them has a bug.

if nargin < 1, csv_path = '../data/synthetic_discharge.csv'; end
if nargin < 2, python_result_path = '../python-kalman/ekf_soc.csv'; end

log = readtable(csv_path);
t = log.time_ms / 1000;              % s
i_a = log.current_mA / 1000;         % A, discharge > 0
v = log.voltage_V;

dt = median(diff(t));
assert(abs(dt - 1.0) < 1e-6, ...
    'dataset sample period is %.3f s but the EKF block assumes DT = 1.0 s', dt);

% From Workspace input signals
assignin('base', 'current_ts', [t, i_a]);
assignin('base', 'voltage_ts', [t, v]);

mdl = build_soc_ekf_model();
set_param(mdl, 'FixedStep', num2str(dt), ...
    'StartTime', '0', 'StopTime', num2str(t(end)));

out = sim(mdl, 'ReturnWorkspaceOutputs', 'on');
soc_sl = out.soc_est(:);
t_sl = (0:numel(soc_sl)-1)' * dt;

fprintf('Simulink EKF: final SOC = %.2f %%\n', 100 * soc_sl(end));

figure('Name', 'Simulink vs Python EKF');
plot(t_sl / 3600, 100 * soc_sl, 'r', 'DisplayName', 'Simulink EKF');
hold on; grid on;

if isfile(python_result_path)
    py = readtable(python_result_path);
    plot(py.time_s / 3600, 100 * py.soc_ekf, 'b--', ...
        'DisplayName', 'Python EKF');
    % Skip the first 5 min: the Python runner records the prior at sample 0
    % while this block updates on every sample, so the trajectories differ
    % by one bookkeeping update until the initial transient decays.
    k0 = ceil(300 / dt);
    n = min(numel(soc_sl), height(py));
    d = max(abs(soc_sl(k0:n) - py.soc_ekf(k0:n))) * 100;
    fprintf('max |Simulink - Python| SOC discrepancy (post-transient): %.4f %%\n', d);
    if d > 0.1
        warning('discrepancy > 0.1 %% SOC — the implementations have diverged');
    end
else
    fprintf(['(%s not found — run python-kalman/compare_soc.py first to ' ...
        'enable the cross-check)\n'], python_result_path);
end

if ismember('true_soc', log.Properties.VariableNames)
    plot(t / 3600, 100 * log.true_soc, 'k:', 'DisplayName', 'true SOC');
end
xlabel('time (h)'); ylabel('SOC (%)');
title('EKF cross-validation: Simulink (script-built) vs Python');
legend('Location', 'best');
end
