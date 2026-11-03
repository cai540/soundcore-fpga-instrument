"""Desktop port of the existing App VocalBoundaryEvidence measurement.

The broad cepstral envelope suppresses pitch harmonics before comparing
before/after vowel formants. A missing novelty peak is *not* proof that a
syllable did not occur. In particular, equal-pitch words need protection.
"""
import numpy as np
from scipy.signal import find_peaks

POLICY = 'app-cepstral-envelope-boundaries-v1'


class WordObserver:
    """Released RWBD acoustic boundary head, independent of note decoding.

    The only conditioning is the pitch observer's measured F0. No lyrics,
    song identifier, transcribed reference or corrected notes are consumed.
    Frontend tensors are exported verbatim from the upstream checkpoint.
    """

    def __init__(self, directory, threads=6):
        from pathlib import Path
        import hashlib
        import json
        import onnxruntime as ort
        self.directory = Path(directory)
        self.metadata = json.loads((self.directory / 'manifest.json').read_text(encoding='utf8'))
        for name, field in [('frontend.npz', 'frontend_sha256'), ('word_boundary.onnx', 'onnx_sha256')]:
            if hashlib.sha256((self.directory / name).read_bytes()).hexdigest() != self.metadata[field]:
                raise ValueError('Word observer artifact checksum mismatch: ' + name)
        with np.load(self.directory / 'frontend.npz', allow_pickle=False) as q:
            self.mel_basis, self.hann = q['mel'], q['hann']
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(self.directory / 'word_boundary.onnx'),
            sess_options=options, providers=['CPUExecutionProvider'])

    def frontend(self, pcm):
        """Match upstream MelNet, including its non-centered source clock."""
        from scipy.fft import rfft
        pcm = np.asarray(pcm, np.float32)
        if pcm.ndim != 1 or not np.isfinite(pcm).all() or len(pcm) < 512:
            raise ValueError('Finite mono 24 kHz PCM required')
        fft, hop = self.metadata['fft_size'], self.metadata['hop_size']
        pad = (fft - hop) // 2
        tail = (-len(pcm)) % hop
        padded = np.pad(pcm.clip(-1, 1), (pad, pad + tail), mode='reflect')
        frames = np.lib.stride_tricks.sliding_window_view(padded, fft)[::hop]
        spectrum = rfft(frames * self.hann, axis=1)
        magnitude = np.sqrt(spectrum.real ** 2 + spectrum.imag ** 2 + 1e-9)
        mel = np.log10(np.maximum(magnitude @ self.mel_basis.T, 1e-5))
        return mel[:, :self.metadata['use_mel_bins']].astype(np.float32)

    def probability(self, pcm, rate, frame_count, f0):
        from .audio import Audio, resample
        signal = resample(Audio(pcm, rate), self.metadata['sample_rate'])
        mel = self.frontend(signal.samples)
        count = len(mel)
        source_seconds = np.arange(count) * self.metadata['hop_size'] / self.metadata['sample_rate']
        f0 = np.asarray(f0, float)
        grid = np.arange(len(f0)) * .01
        voiced = np.interp(source_seconds, grid, (f0 > 0).astype(float)) > .5
        f0 = np.where(voiced, np.interp(source_seconds, grid, f0), 0.)
        mel_pitch = 1127 * np.log1p(f0 / 700)
        lo, hi = 1127 * np.log1p(np.array([self.metadata['pitch_min_hz'], self.metadata['pitch_max_hz']]) / 700)
        coarse = np.where(f0 > 0, (mel_pitch - lo) * (self.metadata['pitch_bins'] - 2) / (hi - lo) + 1, 1)
        coarse = np.floor(coarse.clip(1, self.metadata['pitch_bins'] - 1) + .5).astype(np.int64)
        # Upstream inference pads mel and coarse pitch with zero. Padding UV
        # is zero too; it must not stretch the recording's physical timeline.
        padding = (-count) % 16
        feeds = {'mel': np.pad(mel, ((0, padding), (0, 0)))[None, :],
                 'pitch': np.pad(coarse, (0, padding))[None, :],
                 'uv': np.pad((~voiced).astype(np.int64), (0, padding))[None, :]}
        posterior = self.session.run(None, feeds)[0][0, :count]
        return np.interp(np.arange(frame_count) * .01, source_seconds, posterior).clip(0, 1)


def analyze(pcm, rms=None):
    pcm = np.asarray(pcm, dtype=np.float32)
    if pcm.ndim != 1 or not np.isfinite(pcm).all():
        raise ValueError('Finite mono 16 kHz PCM required')
    frames = (len(pcm) + 159) // 160
    if rms is not None:
        # The existing extractors timestamp through whole milliseconds, then
        # ceil to 10 ms. For an end such as 253960.625 ms they deliberately
        # omit the <1 ms final cell. Use their measured cells without padding
        # or stretching the entire feature track by one frame.
        whole_ms_frames = (len(pcm) // 16 + 9) // 10
        if len(rms) not in (frames, whole_ms_frames):
            raise ValueError('RMS must share the source 10 ms frame grid')
        frames = len(rms)
    if not frames:
        return {key: np.empty(0) for key in ('novelty', 'strength', 'candidates')}
    # Match the App's 512-sample centered window and 1024-point FFT.
    padded = np.pad(pcm, (256, 512))
    windows = np.lib.stride_tricks.sliding_window_view(padded, 512)[::160][:frames]
    if rms is None:
        energy_pad = np.pad(pcm, (160, 320))
        ew = np.lib.stride_tricks.sliding_window_view(energy_pad, 320)[::160][:frames]
        rms = np.sqrt(np.mean(ew.astype(float) ** 2, axis=1))
    rms = np.asarray(rms, float)
    if len(rms) != frames or not np.isfinite(rms).all():
        raise ValueError('RMS must share the source 10 ms frame grid')
    low, high = 2595 * np.log10(1 + np.array([100., 7500.]) / 700)
    edges = 700 * (10 ** (np.linspace(low, high, 22) / 2595) - 1)
    hz = np.arange(513) * 16000 / 1024
    filters = np.maximum(0, np.minimum(
        (hz[None, :] - edges[:-2, None]) / (edges[1:-1] - edges[:-2])[:, None],
        (edges[2:, None] - hz[None, :]) / (edges[2:] - edges[1:-1])[:, None]))
    envelope = np.empty((frames, 20), float)
    for start in range(0, frames, 512):
        end = min(frames, start + 512)
        spectrum = np.fft.rfft(windows[start:end] * np.hanning(512), n=1024)
        cepstrum = np.fft.irfft(np.log(abs(spectrum) ** 2 + 1e-12), n=1024)
        cepstrum[:, 25:-24] = 0
        broad = np.exp(np.fft.rfft(cepstrum).real)
        band = broad @ filters.T
        envelope[start:end] = band / (band.sum(axis=1, keepdims=True) + 1e-12)
    prefix = np.vstack([np.zeros(20), np.cumsum(envelope, axis=0)])
    floor = max(.0025, float(rms.max()) * .035)
    voiced = np.r_[0, np.cumsum(rms > floor)]
    novelty = np.zeros(frames)
    for i in range(frames):
        ls, le, rs, re = max(0, i - 18), max(0, i - 3), min(frames, i + 4), min(frames, i + 19)
        if le - ls < 7 or re - rs < 7:
            continue
        if voiced[min(frames, i + 13)] - voiced[max(0, i - 12)] < .45 * 25:
            continue
        a = (prefix[le] - prefix[ls]) / (le - ls)
        b = (prefix[re] - prefix[rs]) / (re - rs)
        a /= a.sum() + 1e-12
        b /= b.sum() + 1e-12
        middle = (a + b) / 2
        novelty[i] = max(0., float(.5 * np.sum(a * np.log((a + 1e-12) / (middle + 1e-12)))
                                   + .5 * np.sum(b * np.log((b + 1e-12) / (middle + 1e-12)))))
    peaks, _ = find_peaks(novelty, height=.04, prominence=.025, distance=18)
    strength = np.zeros(frames)
    for k in peaks:
        grid = np.arange(max(0, k - 16), min(frames, k + 17))
        value = np.clip((novelty[k] - .025) / .10, 0, .9)
        strength[grid] = np.maximum(strength[grid], value * np.exp(-.5 * ((grid - k) / 8) ** 2))
    return {'novelty': novelty, 'strength': strength, 'candidates': peaks}
