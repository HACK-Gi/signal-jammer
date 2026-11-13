#!/usr/bin/env python3
# language: Python 3.8+, file: rf_jammer.py, target: Linux, needs HackRF + hackrf_transfer
# 2.4GHz ISM-band noise/sweep transmitter. Covers WiFi (ch1-13) and Bluetooth.
# Hardware: HackRF One / GreatFET / any hackrf_transfer-compatible SDR TX.
# Legal: intentional radiated interference is regulated (FCC Part 15 etc.) —
# use only on your own gear in a shielded/test environment.

import argparse
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile

RATE = 20_000_000  # 20 Msps — HackRF max, ~20MHz instantaneous noise bandwidth
BUF_SECONDS = 2.0

# 2.4GHz ISM channel centers
WIFI_CHANNELS = [2412 + 5 * i for i in range(13)]            # ch1-13: 2412..2472 MHz
BT_ADV = [2402, 2426, 2480]                                  # BLE advertising ch 37/38/39
BT_CLASSIC_HOP = [2402 + i for i in range(0, 80)]            # full BT hop range, 1MHz grid


def gen_noise_iq(path, seconds=BUF_SECONDS, rate=RATE):
    """Complex Gaussian noise -> interleaved int8 I/Q file for hackrf_transfer."""
    import numpy as np
    n = int(rate * seconds)
    i = np.clip(np.random.normal(0, 80, n), -128, 127).astype(np.int8)
    q = np.clip(np.random.normal(0, 80, n), -128, 127).astype(np.int8)
    interleaved = np.empty(2 * n, dtype=np.int8)
    interleaved[0::2] = i
    interleaved[1::2] = q
    interleaved.tofile(path)
    return path


def check_hackrf():
    exe = shutil.which("hackrf_transfer")
    if not exe:
        sys.exit("[!] hackrf_transfer not found. Install hackrf tools: "
                 "https://github.com/greatscottgadgets/hackrf/releases")
    return exe


def tx(exe, iq_path, freq_hz, amp=40, gain=30):
    """One hackrf_transfer call = one buffer duration of noise at freq_hz."""
    return subprocess.run(
        [exe, "-t", iq_path, "-f", str(freq_hz), "-s", str(RATE),
         "-a", str(amp), "-x", str(gain)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def center_freqs(args):
    if args.bt_only:
        return BT_CLASSIC_HOP
    if args.wifi_only:
        return WIFI_CHANNELS
    # default: WiFi centers + BLE adv channels, deduped, sorted
    return sorted(set(WIFI_CHANNELS) | set(BT_ADV))


def run(args):
    exe = check_hackrf()
    try:
        import numpy  # noqa: F401 — needed for IQ generation
    except ImportError:
        sys.exit("[!] numpy required: pip install numpy")

    with tempfile.NamedTemporaryFile(suffix=".iq", delete=False) as f:
        iq_path = f.name
    try:
        print(f"[*] generating {BUF_SECONDS}s noise IQ ({RATE/1e6:.0f}Msps)...")
        gen_noise_iq(iq_path)
        freqs = center_freqs(args)
        mode = "SINGLE" if args.center else f"SWEEP x{len(freqs)}"
        print(f"[*] mode={mode} amp={args.amp} gain={args.gain} — Ctrl+C to stop")

        idx = 0
        while True:
            if args.center:
                targets = [args.center * 1_000_000]
            else:
                targets = [freqs[idx % len(freqs)]]
                idx += 1
            for f in targets:
                print(f"    TX {f/1e6:.1f} MHz", flush=True)
                tx(exe, iq_path, f, args.amp, args.gain)
    except KeyboardInterrupt:
        print("\n[*] stopped")
    finally:
        try:
            os.unlink(iq_path)
        except OSError:
            pass


def main():
    p = argparse.ArgumentParser(
        description="2.4GHz ISM noise jammer for HackRF (WiFi + Bluetooth)",
        epilog="examples:\n"
               "  rf_jammer.py --center 2437        # fixed 2437MHz, ~20MHz wide\n"
               "  rf_jammer.py                       # hop WiFi ch1-13 + BLE adv\n"
               "  rf_jammer.py --wifi-only           # WiFi channels only\n"
               "  rf_jammer.py --bt-only             # Bluetooth hop range 2402-2481\n"
               "  rf_jammer.py --amp 60 --gain 40    # hotter output",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--center", type=float, default=None,
                   help="fixed center frequency in MHz (disables hopping)")
    p.add_argument("--wifi-only", action="store_true")
    p.add_argument("--bt-only", action="store_true")
    p.add_argument("--amp", type=int, default=40,
                   help="TX VGA gain 0-127 (default 40)")
    p.add_argument("--gain", type=int, default=30,
                   help="TX IF gain 0-47 (default 30)")
    args = p.parse_args()

    if args.center is not None and not (2400 <= args.center <= 2500):
        p.error("--center must be within 2400-2500 MHz (2.4GHz ISM)")
    if args.wifi_only and args.bt_only:
        p.error("--wifi-only and --bt-only are mutually exclusive")

    run(args)


if __name__ == "__main__":
    main()
