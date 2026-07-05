# Firmware — INA219 voltage/current logger

Arduino Mega 2560 sketch that samples an INA219 at a fixed 1 Hz rate and
streams timestamped, CSV-friendly lines over serial:

```
time_ms,voltage_V,current_mA
0,4.121,1051.2
1000,4.118,1049.8
...
```

`voltage_V` is the reconstructed cell terminal voltage (bus voltage + shunt
drop), `current_mA` is positive during discharge.

## Build

1. Install the **Adafruit INA219** library (Arduino IDE → Library Manager),
   which pulls in Adafruit BusIO automatically.
2. Open `soc_logger/soc_logger.ino`, select *Arduino Mega 2560*, upload.

## Wiring

| INA219 pin | Connect to |
|------------|-----------------------------------------------|
| VCC        | Mega 5V |
| GND        | Mega GND |
| SDA        | Mega pin 20 (SDA) |
| SCL        | Mega pin 21 (SCL) |
| VIN+       | 18650 **+** terminal |
| VIN-       | Load **+** input |
| —          | Load return → 18650 **−** terminal → Mega GND |

Current must flow **VIN+ → VIN−** during discharge so the sign convention
(discharge = positive) matches the analysis scripts. The cell's negative
terminal and the Mega must share a common ground, otherwise the bus-voltage
reading is meaningless.

## Calibration range

The sketch uses `setCalibration_32V_1A()` (±1 A, ~0.04 mA resolution). Change
to `setCalibration_16V_400mA()` for small loads or `setCalibration_32V_2A()`
for >1 A discharges — one line in `setup()`.

Note the INA219's offset and shunt-tolerance errors are exactly what makes
coulomb counting drift; see the top-level README. If you want to reduce (not
eliminate) that drift, log a few minutes with **no load connected** and
subtract the mean reported current as a static offset in post-processing.

## Capturing a log

Any of:

- `python log_serial.py /dev/ttyACM0 -o discharge.csv` (needs `pip install pyserial`;
  handles board resets and flushes every line)
- Arduino Serial Monitor at 115200 baud → copy/paste to a file
- `screen /dev/ttyACM0 115200 | tee discharge.csv`

The resulting file drops straight into the estimators:

```
python ../python-coulomb-counting/coulomb_counting.py discharge.csv
python ../python-kalman/compare_soc.py discharge.csv
```

## Sample rate

1 Hz is deliberate: a full 18650 discharge takes hours, SOC dynamics are slow,
and 1 Hz keeps files small while integration error stays negligible. The
scheduler in `loop()` advances the deadline by `SAMPLE_PERIOD_MS` each sample
(rather than re-arming from "now"), so the average rate is exact even if an
individual sample runs late. Set `SAMPLE_PERIOD_MS = 100` if you want to
resolve load-pulse edges.
