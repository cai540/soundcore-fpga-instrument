"""Estimate the center of an actually observed vocal vibrato before rounding.

No lyric, scale/key or target pitch is used. Linear motion alone and flat
multi-note plateaus are not grounds for sinusoidal demodulation.
"""
import numpy as np


class PitchObserver:
    """Original RMVPE salience and local F0, with no note editing."""

    def __init__(self, directory, cache, threads=6):
        from pathlib import Path
        import hashlib
        import json
        import onnxruntime as ort
        self.directory, self.cache = Path(directory), Path(cache)
        self.metadata = json.loads((self.directory / 'manifest.json').read_text(encoding='utf8'))
        for name, field in [('frontend.npz', 'frontend_sha256'), ('pitch.onnx', 'onnx_sha256')]:
            if hashlib.sha256((self.directory / name).read_bytes()).hexdigest() != self.metadata[field]:
                raise ValueError('Pitch observer checksum mismatch: ' + name)
        with np.load(self.directory / 'frontend.npz', allow_pickle=False) as q:
            self.mel_basis, self.hann = q['mel'], q['hann']
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(self.directory / 'pitch.onnx'),
            sess_options=options, providers=['CPUExecutionProvider'])

    def frontend(self, pcm):
        from scipy.fft import rfft
        pcm = np.asarray(pcm, np.float32)
        fft, hop = self.metadata['fft_size'], self.metadata['hop_size']
        padded = np.pad(pcm, (fft // 2, (fft + 1) // 2))
        frames = np.lib.stride_tricks.sliding_window_view(padded, fft)[::hop]
        magnitude = abs(rfft(frames * self.hann, axis=1))
        return np.log(np.maximum(magnitude @ self.mel_basis.T, 1e-5)).T.astype(np.float32)

    def observe(self, pcm, rate):
        from .audio import Audio, resample
        wave = resample(Audio(pcm, rate), self.metadata['sample_rate']).samples
        # F0 owns a fixed source-time core with surrounding acoustic context.
        # Breath-based melody partitioning must not change its pitch register.
        rate = self.metadata['sample_rate']
        frames = (len(wave) + 159) // 160
        f0, confidence = np.zeros(frames), np.zeros(frames)
        for a in range(0, frames, 2000):
            z = min(frames, a + 2000)
            left, right = max(0, a - 120), min(frames, z + 120)
            f, c = self._observe(wave[left * 160:min(len(wave), right * 160)])
            f0[a:z], confidence[a:z] = f[a - left:z - left], c[a - left:z - left]
        return f0, confidence

    def _observe(self, wave):
        import hashlib
        from .game import _write_npz
        key = hashlib.sha256(wave.tobytes() + self.metadata['onnx_sha256'].encode()
            + self.metadata['frontend_sha256'].encode() + b':frontend-v1').hexdigest()
        path = self.cache / 'f0' / (key + '.npz')
        if path.exists():
            with np.load(path, allow_pickle=False) as q:
                return q['f0'], q['confidence']
        mel = self.frontend(wave)
        frames = mel.shape[1]
        padded = np.pad(mel, ((0, 0), (0, (-frames) % 32)))
        salience = self.session.run(None, {'mel': padded[None, :]})[0][0, :frames]
        bins = np.arange(self.metadata['pitch_bins'])[None, :]
        local = salience * (abs(bins - salience.argmax(axis=1)[:, None]) <= 4)
        cents = bins * self.metadata['cents_step'] + self.metadata['cents_origin']
        pitch = (local * cents).sum(axis=1) / np.maximum(local.sum(axis=1), 1e-9)
        confidence = salience.max(axis=1)
        f0 = np.where(confidence >= .03, 10 * 2 ** (pitch / 1200), 0.)
        _write_npz(path, f0=f0, confidence=confidence)
        return f0, confidence


def interval_likelihood(f0, confidence, start, end):
    """A robust vowel-center measurement; never decides or changes a note.

    The previously validated regression measures an observed sustained
    vibrato. This feature describes pitch class only: a periodic detector's
    octave alias must not force the interval classifier into another octave.
    A glide or an unconfirmed periodic fit carries no center observation.
    """
    f0 = np.asarray(f0[start:end], float)
    confidence = np.asarray(confidence[start:end], float)
    valid = (f0 > 0) & np.isfinite(f0) & (confidence >= .03)
    fraction = float(np.mean(valid)) if len(valid) else 0.
    likelihood = np.ones(128)
    if np.count_nonzero(valid) >= 3:
        pitch = 69 + 12 * np.log2(f0[valid] / 440)
        weights = confidence[valid]
        times = np.flatnonzero(valid) * .01
        fit = estimate_center(times, pitch, weights)
        if fit.get('vibrato'):
            residual = (np.arange(128) - fit['center'] + 6) % 12 - 6
            likelihood = .1 + .9 * np.exp(-.5 * residual ** 2 / .4 ** 2)
    likelihood[0] = max(.1, 1 - fraction)
    return likelihood


def scale_center(f0, confidence, start, end, threshold):
    """One conservative F0 class observation, or None when under-supported.

    A validated periodic fit removes observed vibrato. Otherwise the median
    is an observation for soft source-scale estimation, not a forced note.
    Short or largely unvoiced units remain present in the note classifier.
    """
    f = np.asarray(f0[start:end], float)
    weights = np.asarray(confidence[start:end], float)
    valid = (f > 0) & np.isfinite(f) & np.isfinite(weights) & (weights >= threshold)
    if valid.sum() < 8 or valid.mean() < .6:
        return None
    pitches = 69 + 12 * np.log2(f[valid] / 440)
    fit = estimate_center(np.flatnonzero(valid) * .01, pitches, weights[valid])
    center = fit['center'] if fit.get('vibrato') else float(np.median(pitches))
    return center if np.isfinite(center) and 1 <= center <= 127 else None

def estimate_center(times,pitches,weights=None):
    t=np.asarray(times,float);p=np.asarray(pitches,float)
    w=np.ones(len(p)) if weights is None else np.asarray(weights,float)
    valid=np.isfinite(p)&np.isfinite(t)&(w>0);t=t[valid];p=p[valid];w=w[valid]
    if len(p)<8:return {'center':None,'vibrato':False,'reason':'insufficient'}
    mean=float(np.average(p,weights=w));fallback={'center':mean,'vibrato':False,'reason':'no_periodic_evidence'}
    if len(p)<24 or t[-1]-t[0]<.25:return fallback
    # Integer plateau sequences may repeat, but they are actual notes rather
    # than a continuous oscillating vocal pitch.
    motion=np.mean(abs(np.diff(p))>.025)
    if motion<.45:return fallback
    t=t-(t[0]+t[-1])/2;root=np.sqrt(w);base=np.column_stack([np.ones(len(t)),t])
    linear=np.linalg.lstsq(base*root[:,None],p*root,rcond=None)[0]
    variance=float(np.average((p-base@linear)**2,weights=w))
    if variance<.025:return fallback
    best=None
    for hz in np.arange(3.5,9.01,.25):
        if hz*(t[-1]-t[0])<1.3:continue
        x=np.column_stack([np.ones(len(t)),t,np.sin(2*np.pi*hz*t),np.cos(2*np.pi*hz*t)])
        coef=np.linalg.lstsq(x*root[:,None],p*root,rcond=None)[0]
        error=float(np.average((p-x@coef)**2,weights=w));amplitude=float(np.hypot(coef[2],coef[3]))
        explained=1-error/variance
        train=np.arange(len(t))%2==0
        check=np.linalg.lstsq(x[train]*root[train,None],p[train]*root[train],rcond=None)[0]
        cv=float(np.average((p[~train]-x[~train]@check)**2,weights=w[~train]))
        if explained<.6 or cv>variance*.5 or not .15<=amplitude<=2.5:continue
        if abs(coef[1])*(t[-1]-t[0])>1.5:continue
        score=error+.025*(hz-6)**2
        if best is None or score<best[0]:
            best=(score,{'center':float(coef[0]),'vibrato':True,'frequency_hz':float(hz),
                         'amplitude_semitones':amplitude,'slope':float(coef[1]),'explained':explained,
                         'cross_validated_error':cv,'raw_mean':mean})
    return best[1] if best else fallback
