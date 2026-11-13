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
