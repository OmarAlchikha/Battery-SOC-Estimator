/*
 * soc_logger.ino — 18650 voltage/current logger for SOC estimation
 *
 * Board:   Arduino Mega 2560
 * Sensor:  INA219 (I2C, default address 0x40)
 * Library: Adafruit INA219 (install via Library Manager)
 *
 * Wiring (Mega):
 *   INA219 VCC  -> 5V
 *   INA219 GND  -> GND
 *   INA219 SDA  -> pin 20 (SDA)
 *   INA219 SCL  -> pin 21 (SCL)
 *   INA219 VIN+ -> 18650 positive terminal
 *   INA219 VIN- -> load (so conventional discharge current flows VIN+ -> VIN-,
 *                  which the INA219 reports as POSITIVE)
 *   Load return -> 18650 negative terminal / common GND
 *
 * The bus-voltage pin measures VIN- to GND, i.e. the cell voltage *after* the
 * shunt. The shunt drop (shunt_mV) is logged too, so the analysis scripts can
 * reconstruct the true terminal voltage as:  V_cell = bus_V + shunt_mV/1000.
 *
 * Serial output (115200 baud), CSV-friendly, one line per sample:
 *   time_ms,voltage_V,current_mA
 *
 * A header line is printed once at boot so a captured stream is directly
 * loadable by pandas. Capture with the provided log_serial.py, the Arduino
 * Serial Monitor, or e.g.:  screen /dev/ttyACM0 115200 | tee discharge.csv
 */

#include <Wire.h>
#include <Adafruit_INA219.h>

Adafruit_INA219 ina219;

// Sample period in ms. 1000 ms (1 Hz) is plenty for a multi-hour discharge
// and keeps log files small; drop to 100 ms if you want to resolve pulse edges.
const unsigned long SAMPLE_PERIOD_MS = 1000;

unsigned long nextSampleAt = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial) {}

  if (!ina219.begin()) {
    Serial.println("error,INA219 not found - check wiring/address");
    while (true) { delay(1000); }
  }

  // 32V/1A calibration: +/-1 A range with ~40 uA current resolution.
  // Use setCalibration_16V_400mA() for finer resolution if your discharge
  // current stays below 400 mA, or setCalibration_32V_2A() above 1 A.
  ina219.setCalibration_32V_1A();

  Serial.println("time_ms,voltage_V,current_mA");
  nextSampleAt = millis();
}

void loop() {
  unsigned long now = millis();
  if ((long)(now - nextSampleAt) < 0) {
    return;
  }
  // Schedule from the previous deadline (not from `now`) so the average rate
  // stays exact even when a sample runs late.
  nextSampleAt += SAMPLE_PERIOD_MS;

  float shunt_mV = ina219.getShuntVoltage_mV();
  float bus_V = ina219.getBusVoltage_V();
  float current_mA = ina219.getCurrent_mA();

  // Reconstruct cell terminal voltage (bus pin sits on the load side of the
  // shunt, so add the shunt drop back).
  float cell_V = bus_V + shunt_mV / 1000.0f;

  Serial.print(now);
  Serial.print(',');
  Serial.print(cell_V, 3);
  Serial.print(',');
  Serial.println(current_mA, 1);
}
