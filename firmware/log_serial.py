#!/usr/bin/env python3
"""Capture the soc_logger firmware's serial stream to a CSV file.

Requires:  pip install pyserial

Usage:
    python log_serial.py /dev/ttyACM0 -o discharge.csv        # Linux
    python log_serial.py COM3 -o discharge.csv                # Windows

Stop with Ctrl-C; the file is flushed after every line so nothing is lost.
"""

import argparse
import sys

try:
    import serial
except ImportError:
    sys.exit("pyserial is required:  pip install pyserial")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port", help="serial port, e.g. /dev/ttyACM0 or COM3")
    ap.add_argument("-o", "--output", default="discharge.csv")
    ap.add_argument("-b", "--baud", type=int, default=115200)
    args = ap.parse_args()

    header_written = False
    n = 0
    with serial.Serial(args.port, args.baud, timeout=5) as ser, \
            open(args.output, "w") as f:
        print(f"logging {args.port} -> {args.output}  (Ctrl-C to stop)")
        try:
            while True:
                line = ser.readline().decode("ascii", errors="replace").strip()
                if not line:
                    continue
                # Keep exactly one header row even if the board resets mid-log.
                if line.startswith("time_ms"):
                    if header_written:
                        continue
                    header_written = True
                elif line.startswith("error"):
                    print(f"firmware reported: {line}", file=sys.stderr)
                    continue
                f.write(line + "\n")
                f.flush()
                n += 1
                if n % 60 == 0:
                    print(f"  {n} lines...", end="\r")
        except KeyboardInterrupt:
            print(f"\nstopped; wrote {n} lines to {args.output}")


if __name__ == "__main__":
    main()
