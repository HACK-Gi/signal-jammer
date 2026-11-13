#!/usr/bin/env python3
# language: Python 3.8+, file: speaker_jammer.py, target: Linux / Windows / macOS
# Audio jammer + speaker test: continuous tones, sweeps, noise, burst patterns.
# Needs: numpy + sounddevice  (pip install numpy sounddevice)
# Fallback: writes a WAV and plays it with the OS player if sounddevice missing.

import argparse
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

SR = 48000  # sample rate; high enough for ultrasonic content


def envelope(n, fade=0.01):
    """Raised-cosine fade in/out to kill clicks at buffer edges."""
    import numpy as np
    e = np.ones(n, dtype=np.float32)
    f = min(int(SR * fade), n // 4)
    if f > 0:
        ramp = 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, f))
        e[:f] = ramp
        e[-f:] = ramp[::-1]
    return e


def gen_tone(freq, dur, amp):
    import numpy as np
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    return (amp * np.sin(2 * np.pi * freq * t) * envelope(n)).astype(np.float32)


def gen_sweep(f1, f2, dur, amp):
    """Linear chirp. Phase-integrated so instantaneous freq tracks f1->f2."""
    import numpy as np
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    phase = 2 * np.pi * (f1 * t + (f2 - f1) * t * t / (2 * dur))
    return (amp * np.sin(phase) * envelope(n)).astype(np.float32)


def gen_noise(dur, amp, kind="white"):
    import numpy as np
    n = int(SR * dur)
    data = np.random.uniform(-1, 1, n).astype(np.float32)
    if kind == "pink":
        # pink = white noise with magnitude scaled by 1/sqrt(f), via FFT
        X = np.fft.rfft(data)
        freqs = np.fft.rfftfreq(n, 1 / SR)
        freqs[0] = freqs[1]  # avoid divide-by-zero on DC
        data = np.fft.irfft(X / np.sqrt(freqs), n).astype(np.float32)
        data /= np.max(np.abs(data))
    return (amp * data * envelope(n)).astype(np.float32)


def gen_bursts(freq, dur, amp, on_ms=60, off_ms=180, duty_ramp=True):
    """Short tone bursts with silence gaps — disruption pattern for mics/recorders."""
    import numpy as np
    n = int(SR * dur)
    out = np.zeros(n, dtype=np.float32)
    period = on_ms + off_ms
    pos = 0
    while pos < n:
        seg = min(int(SR * on_ms / 1000), n - pos)
        t = np.arange(seg, dtype=np.float32) / SR
        env = envelope(seg, fade=0.002)
        out[pos:pos + seg] = amp * np.sin(2 * np.pi * freq * t) * env
        pos += int(SR * period / 1000)
    return out


def gen_speaker_test(dur, amp):
    """One-second tones stepping 100Hz -> 18kHz, then silence. Tests full range."""
    import numpy as np
    chunks = []
    freqs = [100, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000, 18000]
    per = max(0.4, dur / len(freqs))
    for f in freqs:
        chunks.append(gen_tone(f, per, amp))
        chunks.append(np.zeros(int(SR * 0.15), dtype=np.float32))
    return np.concatenate(chunks)


def write_wav(path, data):
    pcm = (np_clip(data) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def np_clip(data):
    import numpy as np
    return np.clip(data, -1.0, 1.0)


def play_wav_fallback(path):
    """OS-level playback when sounddevice isn't installed."""
    system = sys.platform
    if system == "linux":
        for player in ("paplay", "aplay", "pw-play"):
            if shutil.which(player):
                subprocess.run([player, path], check=False)
                return True
    elif system == "darwin":
        subprocess.run(["afplay", path], check=False)
        return True
    elif system == "win32":
        subprocess.run(["powershell", "-c",
                        f"(New-Object Media.SoundPlayer '{path}').PlaySync()"],
                       check=False)
        return True
    return False


def play(data, device=None):
    try:
        import sounddevice as sd
    except ImportError:
        print("[!] sounddevice not installed — writing WAV and using OS player.")
        print("    for direct playback:  pip install numpy sounddevice")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        write_wav(tmp, data)
        if not play_wav_fallback(tmp):
            print(f"[!] no player found — WAV saved at: {tmp}")
        else:
            os.unlink(tmp)
        return

    kwargs = {}
    if device is not None:
        kwargs["device"] = device
    sd.play(data, samplerate=SR, **kwargs)
    sd.wait()


def list_devices():
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice not installed — cannot list devices.")
        return
    print(sd.query_devices())


def build_signal(args):
    mode = args.mode
    amp = args.amp
    dur = args.duration

    if mode == "tone":
        return gen_tone(args.freq, dur, amp)
    if mode == "sweep":
        return gen_sweep(args.freq, args.freq2, dur, amp)
    if mode == "noise":
        return gen_noise(dur, amp, args.kind)
    if mode == "bursts":
        return gen_bursts(args.freq, dur, amp, args.on_ms, args.off_ms)
    if mode == "test":
        return gen_speaker_test(dur, amp)
    raise SystemExit(f"unknown mode: {mode}")


def main():
    p = argparse.ArgumentParser(
        description="Speaker jammer / audio test tool",
        epilog="examples:\n"
               "  speaker_jammer.py tone 8000 -d 10        # 8kHz tone (default)\n"
               "  speaker_jammer.py sweep 100 20000 -d 20   # full-range chirp\n"
               "  speaker_jammer.py bursts 17000 -d 60      # burst disruption pattern\n"
               "  speaker_jammer.py noise -d 15 --kind pink\n"
               "  speaker_jammer.py test -d 12              # stepped speaker test\n"
               "  speaker_jammer.py --devices               # list audio outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", nargs="?", default="tone",
                   choices=["tone", "sweep", "noise", "bursts", "test"])
    p.add_argument("freq", nargs="?", type=float, default=8000,
                   help="tone/burst frequency Hz (default 8000)")
    p.add_argument("freq2", nargs="?", type=float, default=20000,
                   help="sweep end frequency Hz")
    p.add_argument("-d", "--duration", type=float, default=10.0,
                   help="seconds (default 10)")
    p.add_argument("--amp", type=float, default=0.7,
                   help="amplitude 0.0-1.0 (default 0.7)")
    p.add_argument("--kind", choices=["white", "pink"], default="white")
    p.add_argument("--on-ms", type=int, default=60, help="burst on-time ms")
    p.add_argument("--off-ms", type=int, default=180, help="burst off-time ms")
    p.add_argument("--device", type=int, default=None,
                   help="sounddevice output index (see --devices)")
    p.add_argument("--devices", action="store_true", help="list audio devices")
    args = p.parse_args()

    if args.amp <= 0 or args.amp > 1.0:
        p.error("--amp must be in (0, 1]")
    if args.duration <= 0:
        p.error("--duration must be > 0")

    if args.devices:
        list_devices()
        return

    print(f"[*] {args.mode} for {args.duration}s @ {SR}Hz amp={args.amp}")
    print("[*] Ctrl+C to stop")
    try:
        data = build_signal(args)
        play(data, device=args.device)
    except KeyboardInterrupt:
        print("\n[*] stopped")


if __name__ == "__main__":
    main()
