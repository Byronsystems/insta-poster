"""Synthesise an original, royalty-free soundtrack for a Reel.

Usage:
  python music.py out.wav 19.5 [impact_seconds] [drums_in_seconds] [minor|major]

A minor-key (moody) or major-key (upbeat) bed at 120 BPM: soft pads, sub bass, kick and hats,
with a riser into an impact hit so a big moment in the video can land on it.
"""
import sys
import wave

import numpy as np

SR = 44100
BPM = 120
BEAT = 60 / BPM
MINOR = [  # Am, F, C, G as frequencies (root + triad an octave up)
    [110.00, 220.00, 261.63, 329.63],
    [87.31, 174.61, 220.00, 261.63],
    [130.81, 261.63, 329.63, 392.00],
    [98.00, 196.00, 246.94, 293.66],
]
MAJOR = [  # C, G, Am, F
    [130.81, 261.63, 329.63, 392.00],
    [98.00, 196.00, 246.94, 293.66],
    [110.00, 220.00, 261.63, 329.63],
    [87.31, 174.61, 220.00, 261.63],
]


def env(n, attack, release):
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0, 1, a)
    e[n - r:] *= np.linspace(1, 0, r)
    return e


def pad(freq, n, detune):
    t = np.arange(n) / SR
    # a few soft harmonics instead of a filtered saw
    return sum(np.sin(2 * np.pi * freq * h * (1 + detune) * t) / h ** 1.6 for h in range(1, 6))


def kick(n=int(0.45 * SR)):
    t = np.arange(n) / SR
    freq = 45 + 85 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 7)


def hat(rng, n=int(0.06 * SR)):
    noise = np.diff(rng.standard_normal(n + 1))  # crude high-pass
    return noise * np.exp(-np.arange(n) / SR * 70) * 0.25


def place(track, sound, at):
    i = int(at * SR)
    end = min(len(track), i + len(sound))
    if i < end:
        track[i:end] += sound[:end - i]


def compose(seconds, impact=None, drums_in=2.0, chords=MINOR):
    rng = np.random.default_rng(7)
    n = int(seconds * SR)
    left, right = np.zeros(n), np.zeros(n)
    bar = 4 * BEAT

    # pads + sub bass, one chord per bar
    for b in range(int(seconds / bar) + 1):
        chord = chords[b % len(chords)]
        start, length = b * bar, int(bar * SR)
        e = env(length, 0.35, 0.4)
        for side, detune in ((left, -0.002), (right, 0.002)):
            place(side, sum(pad(f, length, detune) for f in chord[1:]) * e * 0.05, start)
        t = np.arange(length) / SR
        pump = 1 - 0.6 * np.exp(-(t % BEAT) * 9)  # sidechain-style breathing
        sub = np.sin(2 * np.pi * chord[0] / 2 * t) * env(length, 0.02, 0.1) * pump * 0.22
        place(left, sub, start)
        place(right, sub, start)

    # drums
    beat_t = drums_in
    while beat_t < seconds - 1.0:
        k = kick() * 0.55
        place(left, k, beat_t)
        place(right, k, beat_t)
        for off, pan in ((0, 0.6), (BEAT / 2, 1.0)):
            h = hat(rng)
            place(left, h * pan, beat_t + off)
            place(right, h * (1.6 - pan), beat_t + off)
        beat_t += BEAT

    # riser into an impact
    if impact:
        rise = int(1.6 * SR)
        noise = np.diff(rng.standard_normal(rise + 1)) * np.linspace(0, 1, rise) ** 2 * 0.12
        place(left, noise, impact - 1.6)
        place(right, noise, impact - 1.6)
        t = np.arange(int(1.5 * SR)) / SR
        boom = np.sin(2 * np.pi * (40 + 60 * np.exp(-t * 10)) * t) * np.exp(-t * 3) * 0.7
        place(left, boom, impact)
        place(right, boom, impact)

    # simple room reverb
    for side in (left, right):
        wet = np.zeros(n)
        for delay, gain in ((0.031, .3), (0.053, .25), (0.089, .2), (0.137, .15), (0.211, .1)):
            d = int(delay * SR)
            wet[d:] += side[:-d] * gain
        side += wet

    stereo = np.stack([left, right], axis=1)
    stereo *= env(n, 0.8, 1.5)[:, None]
    stereo /= np.abs(stereo).max() / 0.89
    return stereo


def save(path, stereo):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    out, seconds, *rest = sys.argv[1:]
    impact = float(rest[0]) if rest else None
    drums_in = float(rest[1]) if len(rest) > 1 else 2.0
    chords = MAJOR if len(rest) > 2 and rest[2] == "major" else MINOR
    save(out, compose(float(seconds), impact, drums_in, chords))
    print(out)
