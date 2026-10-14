"""Synthesize an original 30-second upbeat background track for the reel.

Usage: python3 make_music.py <out.wav>
"""
import sys
import wave

import numpy as np

SR = 44100
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
BARS = 12  # 12 bars at 96 BPM = 30 s
DUR = BARS * BAR

# I–V–vi–IV in C major, as MIDI notes
CHORDS = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
BASS = [36, 43, 45, 41]
# Simple melody per chord (eighth notes, None = rest)
MELODY = [
    [72, None, 76, 79, 76, None, 74, 72],
    [71, None, 74, 79, 74, None, 71, 67],
    [72, None, 76, 81, 79, None, 76, 72],
    [69, None, 72, 77, 76, 74, 72, None],
]


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def env(n, a=0.01, r=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def tone(m, length, kind="pluck"):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(m)
    if kind == "pluck":
        w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) + 0.1 * np.sin(6 * np.pi * f * t)
        return w * env(n, 0.005, 0.18)
    if kind == "pad":
        w = sum(np.sin(2 * np.pi * f * d * t) for d in (0.997, 1.0, 1.003)) / 3
        a = np.minimum(1, t / 0.4) * np.minimum(1, (length - t) / 0.4)
        return w * a
    if kind == "bass":
        w = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)
        return w * env(n, 0.005, 0.35)


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    freq = 50 + 90 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.12)


def noise_hit(length, decay, seed):
    n = int(length * SR)
    rnd = np.random.default_rng(seed).standard_normal(n)
    hp = np.diff(rnd, prepend=0)  # crude high-pass
    return hp * np.exp(-np.arange(n) / SR / decay)


def add(buf, sig, at, gain):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


def main(out):
    mix = np.zeros(int(DUR * SR) + SR)
    k, hat, clap = kick(), noise_hit(0.05, 0.015, 1), noise_hit(0.2, 0.06, 2)
    for bar in range(BARS):
        c = bar % 4
        t0 = bar * BAR
        intro, outro = bar < 2, bar >= BARS - 1
        for m in CHORDS[c]:
            add(mix, tone(m, BAR, "pad"), t0, 0.07)
        if not intro:
            for b in (0, 1.5, 2, 3.5):
                add(mix, tone(BASS[c], BEAT, "bass"), t0 + b * BEAT, 0.28)
        for e, m in enumerate(MELODY[c]):
            if m is not None and (not intro or e % 2 == 0):
                add(mix, tone(m, BEAT, "pluck"), t0 + e * BEAT / 2, 0.16)
        if not intro and not outro:
            for b in range(4):
                add(mix, k, t0 + b * BEAT, 0.5)
                if b in (1, 3):
                    add(mix, clap, t0 + b * BEAT, 0.12)
            for e in range(8):
                add(mix, hat, t0 + e * BEAT / 2, 0.05 if e % 2 else 0.03)
    mix = mix[: int(DUR * SR)]
    # Simple stereo widening via a short delay, then fades and normalize
    right = np.concatenate([np.zeros(int(0.012 * SR)), mix])[: len(mix)]
    stereo = np.stack([mix * 0.9 + right * 0.1, right * 0.9 + mix * 0.1], axis=1)
    t = np.arange(len(mix)) / SR
    fade = np.minimum(1, t / 1.0) * np.minimum(1, (DUR - t) / 2.5)
    stereo *= fade[:, None]
    stereo = np.tanh(stereo / np.abs(stereo).max() * 1.2) * 0.85
    data = (stereo * 32767).astype("<i2")
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    main(sys.argv[1])
