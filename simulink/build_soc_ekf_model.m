function mdl = build_soc_ekf_model()
%BUILD_SOC_EKF_MODEL Script-build the SOC EKF as a Simulink model.
%   Constructs (from scratch, no .slx checked in) a discrete-time Simulink
%   model 'soc_ekf' that mirrors python-kalman/kalman_soc.py exactly:
%
%     [current, voltage] --> MATLAB Function block (EKF, OCV-R-RC model)
%                            --> soc_est, v1_est  (To Workspace)
%
%   Inputs are From Workspace blocks fed by run_soc_ekf.m with the logged
%   current/voltage series. The EKF itself lives in a MATLAB Function block
%   with persistent state, so the model is one block deep and diffable as
%   code — which is the point of building it from a script.
%
%   Usage:  mdl = build_soc_ekf_model();  % then see run_soc_ekf.m

mdl = 'soc_ekf';
if bdIsLoaded(mdl)
    close_system(mdl, 0);
end
new_system(mdl);
open_system(mdl);

% ---- solver: fixed-step discrete; sample time comes from the input data ----
set_param(mdl, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete');

% ---- blocks ----
add_block('simulink/Sources/From Workspace', [mdl '/current_in'], ...
    'VariableName', 'current_ts', 'Position', [40 40 140 70]);
add_block('simulink/Sources/From Workspace', [mdl '/voltage_in'], ...
    'VariableName', 'voltage_ts', 'Position', [40 120 140 150]);

add_block('simulink/User-Defined Functions/MATLAB Function', ...
    [mdl '/EKF'], 'Position', [220 60 340 130]);

add_block('simulink/Sinks/To Workspace', [mdl '/soc_out'], ...
    'VariableName', 'soc_est', 'SaveFormat', 'Array', ...
    'Position', [420 40 520 70]);
add_block('simulink/Sinks/To Workspace', [mdl '/v1_out'], ...
    'VariableName', 'v1_est', 'SaveFormat', 'Array', ...
    'Position', [420 120 520 150]);

% ---- EKF body: keep numerically identical to python-kalman/kalman_soc.py ----
ekf_code = strjoin({
'function [soc, v1] = fcn(current_A, voltage_V)'
'% One EKF predict/update per sample. State x = [SOC; V1].'
'% Mirrors python-kalman/kalman_soc.py — keep the two in sync.'
''
'% -------- parameters (must match battery_model.BatteryModel) --------'
'CAP_AS = 2500 * 3.6;      % capacity, ampere-seconds'
'R0   = 0.060;             % ohmic resistance'
'R1   = 0.030;             % polarization resistance'
'TAU1 = 60.0;              % RC time constant'
'ETA  = 1.0;               % coulombic efficiency'
'DT   = 1.0;               % sample period (s); run_soc_ekf.m checks this'
'SOC0 = 0.5;               % same deliberately-wrong start as compare_soc.py'
''
'OCV_SOC = [0.00 0.05 0.10 0.20 0.30 0.40 0.50 0.60 0.70 0.80 0.90 1.00];'
'OCV_V   = [3.00 3.30 3.45 3.55 3.62 3.67 3.72 3.79 3.87 3.97 4.08 4.19];'
''
'persistent x P'
'if isempty(x)'
'    x = [SOC0; 0];'
'    P = diag([0.05, 1e-4]);'
'end'
'Q = diag([1e-10, 1e-8]);'
'R = 2e-4;'
''
'% -------- predict (= coulomb counting + RC state) --------'
'a = exp(-DT / TAU1);'
'x_pred = [x(1) - ETA * current_A * DT / CAP_AS; ...'
'          a * x(2) + R1 * (1 - a) * current_A];'
'F = [1 0; 0 a];'
'P_pred = F * P * F.'' + Q;'
''
'% -------- update against measured terminal voltage --------'
's_cl = min(max(x_pred(1), 0), 1);'
'z_pred = interp1(OCV_SOC, OCV_V, s_cl) - x_pred(2) - R0 * current_A;'
'h = 1e-4;'
'lo = min(max(s_cl - h, 0), 1);'
'hi = min(max(s_cl + h, 0), 1);'
'dOCV = (interp1(OCV_SOC, OCV_V, hi) - interp1(OCV_SOC, OCV_V, lo)) / (hi - lo);'
'H = [dOCV, -1];'
'S = H * P_pred * H.'' + R;'
'K = (P_pred * H.'') / S;'
'x = x_pred + K * (voltage_V - z_pred);'
'P = (eye(2) - K * H) * P_pred;'
'P = 0.5 * (P + P.'');'
'x(1) = min(max(x(1), 0), 1);'
''
'soc = x(1);'
'v1  = x(2);'
}, newline);

% Inject the function body into the MATLAB Function block.
sf = find(sfroot, '-isa', 'Stateflow.EMChart', 'Path', [mdl '/EKF']);
sf.Script = ekf_code;

% ---- wires ----
add_line(mdl, 'current_in/1', 'EKF/1');
add_line(mdl, 'voltage_in/1', 'EKF/2');
add_line(mdl, 'EKF/1', 'soc_out/1');
add_line(mdl, 'EKF/2', 'v1_out/1');

fprintf('built model ''%s'' (not saved to disk; run_soc_ekf.m simulates it)\n', mdl);
end
