# signal-jammer

Two-tool suite: acoustic testing/jamming + 2.4GHz ISM RF noise transmission.

## speaker_jammer.py
Audio tones, sweeps, bursts, and noise through your speakers. Needs `numpy` + `sounddevice`
(`pip install numpy sounddevice`), with automatic WAV fallback via OS players.

```
python speaker_jammer.py --devices
python speaker_jammer.py tone 8000 -d 10
python speaker_jammer.py sweep 100 20000 -d 20
python speaker_jammer.py bursts 8000 -d 60
python speaker_jammer.py noise -d 15 --kind pink
python speaker_jammer.py test -d 12
```

## rf_jammer.py
Wideband noise transmission across the 2.4GHz ISM band — covers WiFi ch1-13 and
Bluetooth. Requires a HackRF-compatible SDR and `hackrf_transfer` (hackrf tools).
Generates complex Gaussian IQ noise at 20 Msps and hops channel centers.

```
pip install numpy
python rf_jammer.py --center 2437     # fixed freq, ~20MHz noise bandwidth
python rf_jammer.py                    # hop WiFi ch1-13 + BLE advertising channels
python rf_jammer.py --wifi-only
python rf_jammer.py --bt-only          # full BT hop range 2402-2481 MHz
```

Legal note: intentional RF interference is regulated (FCC Part 15 and equivalents).
Use only on equipment you own, in a shielded environment. A noise source radiates
indiscriminately — it will affect every device in range.

## pc_jammer.py
WiFi deauthentication from your PC — no SDR needed. Uses a monitor-mode WiFi
adapter + aircrack-ng to forge deauth frames. This is what actually drops a
WiFi-controlled drone's link.

```
sudo apt install aircrack-ng
sudo python3 pc_jammer.py scan -i wlan0        # find your drone's BSSID
sudo python3 pc_jammer.py attack -b AA:BB:CC:DD:EE:FF
```

Note: internal laptop WiFi cards usually cannot inject — use a USB adapter
(Alfa AWUS036ACM/ACH, TP-Link Archer T2U). For Bluetooth there is no PC-native
path; BLE spam needs an ESP32 or Ubertooth.

## bt_jammer.py
Bluetooth DoS toolkit — runs on your PC's built-in BT adapter, no extra hardware.
L2CAP echo flood (BTStorm/bluthat equivalent) + BLE connect-flood.

```
sudo apt install bluez
python3 bt_jammer.py scan -t 20                    # find your BT device MAC
python3 bt_jammer.py flood AA:BB:CC:DD:EE:FF -w 8  # L2CAP echo flood (Classic BT)
python3 bt_jammer.py ble-flood AA:BB:CC:DD:EE:FF    # BLE connect churn
```

Limits: `flood` only affects Classic Bluetooth devices (headsets, speakers,
car kits, older phones). BLE-only gadgets ignore L2CAP echo — raw BLE jamming
needs NRF24L01+PA+LNA (HailHound) or btlejack hardware.

## jammer.py — ALL-IN-ONE
Single entry point wrapping all three tools. Default audio freq is 8000 Hz.

```
python3 jammer.py audio tone -f 8000 -d 15        # speaker tone
python3 jammer.py audio sweep -f 100 --freq2 20000 -d 20
python3 jammer.py audio bursts -f 8000 -d 60
python3 jammer.py audio test -d 12                # speaker range test
python3 jammer.py audio noise -d 15 --kind pink

python3 jammer.py bt-scan -t 20                    # find BT device MACs
python3 jammer.py bt-flood AA:BB:CC:DD:EE:FF -w 8  # L2CAP flood
python3 jammer.py bt-ble AA:BB:CC:DD:EE:FF         # BLE connect churn

sudo python3 jammer.py wifi-scan -i wlan0 -t 20   # find WiFi APs
sudo python3 jammer.py wifi-attack -b AA:BB:..    # deauth flood
```
