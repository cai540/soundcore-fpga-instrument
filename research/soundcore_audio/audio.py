"""Bandlimited input and source-clock phrase partitioning, without note logic."""
from dataclasses import dataclass
from pathlib import Path
import math
import subprocess
import numpy as np
from scipy.special import expit
from scipy.signal import resample_poly


@dataclass(frozen=True)
class Audio:
    samples: np.ndarray
    rate: int

    @property
    def duration_ms(self):
        return round(len(self.samples) * 1000 / self.rate)


@dataclass(frozen=True)
class Chunk:
    first_frame: int
    last_frame: int


def decode(path, rate=44100):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(Path(path)),
        '-ac', '1', '-ar', str(rate), '-f', 'f32le', '-'])
    return validate(np.frombuffer(raw, dtype='<f4').copy(), rate)


def validate(samples, rate):
    x = np.asarray(samples, np.float32)
    if not 8000 <= rate <= 192000 or x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError('Finite mono PCM and a supported sample rate required')
    if not .1 <= len(x) / rate <= 600:
        raise ValueError('Audio must last 0.1 to 600 seconds')
    return Audio(x, int(rate))


def resample(audio, rate):
    if audio.rate == rate:
        return audio
    divisor = math.gcd(audio.rate, rate)
    x = resample_poly(audio.samples, rate // divisor, audio.rate // divisor).astype(np.float32)
    return Audio(x, rate)


def frame_rms(audio, hop_seconds=.01):
    hop = round(audio.rate * hop_seconds)
    frames = math.ceil(len(audio.samples) / hop)
    padded = np.pad(audio.samples, (hop * 2, hop * 4))
    windows = np.lib.stride_tricks.sliding_window_view(padded, hop * 4)[::hop][:frames]
    return np.sqrt(np.mean(windows.astype(float) ** 2, axis=1))


def quiet_posterior(rms):
    """Two log-energy populations; amplitude scaling shifts both equally."""
    x = np.log(np.maximum(rms, 1e-8))
    if len(x) < 50 or np.std(x) < .25:
        return np.zeros(len(x))
    means = np.quantile(x, [.2, .8])
    variances = np.full(2, max(float(np.var(x)) / 2, .1))
    weights = np.full(2, .5)
    for _ in range(30):
        logp = (np.log(weights)[None, :] - .5 * np.log(variances)[None, :]
                - .5 * (x[:, None] - means[None, :]) ** 2 / variances[None, :])
        low = expit(logp[:, 0] - logp[:, 1])
        responsibilities = np.column_stack([low, 1 - low])
        mass = responsibilities.sum(axis=0) + 1e-8
        means = (responsibilities * x[:, None]).sum(axis=0) / mass
        variances = np.maximum((responsibilities * (x[:, None] - means) ** 2).sum(axis=0) / mass, .08)
        weights = mass / mass.sum()
    if means[0] > means[1]:
        means = means[::-1]
        low = 1 - low
    if means[1] - means[0] < .7:
        return np.zeros(len(x))
    return low


def phrase_chunks(audio, max_seconds=24., min_seconds=3., pause_seconds=.2):
    rms = frame_rms(audio)
    quiet = quiet_posterior(rms) > .9
    edges = np.r_[0, np.flatnonzero(quiet[1:] != quiet[:-1]) + 1, len(quiet)]
    gaps = [(int(a), int(z)) for a, z in zip(edges, edges[1:])
            if quiet[a] and z - a >= round(pause_seconds * 100)]
    cuts = [0]
    for a, z in gaps:
        center = (a + z) // 2
        if center - cuts[-1] >= round(min_seconds * 100):
            cuts.append(center)
    if len(rms) - cuts[-1] < round(min_seconds * 100) and len(cuts) > 1:
        cuts.pop()
    cuts.append(len(rms))
    bounded = [0]
    for end in cuts[1:]:
        while end - bounded[-1] > round(max_seconds * 100):
            low = bounded[-1] + round(max_seconds * 50)
            high = bounded[-1] + round(max_seconds * 100)
            bounded.append(low + int(np.argmin(rms[low:high])))
        if end > bounded[-1]:
            bounded.append(end)
    return [Chunk(a, z) for a, z in zip(bounded, bounded[1:])]
