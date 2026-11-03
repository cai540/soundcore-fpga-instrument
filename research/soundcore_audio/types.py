"""Immutable data shared by observation, decoding and export."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Note:
    start_ms: int
    end_ms: int
    midi: int

    def __post_init__(self):
        if (not all(isinstance(v, (int, np.integer)) for v in (self.start_ms, self.end_ms, self.midi))
                or self.start_ms < 0 or self.end_ms <= self.start_ms or not 1 <= self.midi <= 127):
            raise ValueError('Invalid monophonic note')


@dataclass(frozen=True)
class EncodedAudio:
    segmentation: np.ndarray
    estimation: np.ndarray
    mask: np.ndarray
    source_samples: int
    sample_rate: int
    source_sha256: str

    @property
    def frames(self):
        return int(self.mask.sum())


@dataclass(frozen=True)
class ModelObservation:
    cuts: np.ndarray
    boundary_probability: np.ndarray
    pitch_activation: np.ndarray

    def __post_init__(self):
        cuts = np.asarray(self.cuts)
        boundary = np.asarray(self.boundary_probability, float)
        pitch = np.asarray(self.pitch_activation, float)
        if (cuts.ndim != 1 or len(cuts) < 2 or not np.issubdtype(cuts.dtype, np.integer)
                or cuts[0] != 0 or np.any(np.diff(cuts) <= 0)
                or boundary.shape != (cuts[-1],) or pitch.shape != (len(cuts) - 1, 257)):
            raise ValueError('Complete ordered model observations on the source frame grid required')
        for name, array in [('cuts', cuts), ('boundary_probability', boundary), ('pitch_activation', pitch)]:
            if not np.isfinite(array).all() or (name != 'cuts' and np.any((array < 0) | (array > 1))):
                raise ValueError('Finite valid model probabilities required')
            array = array.copy()
            array.setflags(write=False)
            object.__setattr__(self, name, array)


@dataclass(frozen=True)
class IntervalEvidence:
    start: int
    end: int
    activation: np.ndarray
    f0_likelihood: np.ndarray | None = None
    voiced_probability: float | None = None

    def __post_init__(self):
        p = np.array(self.activation, dtype=float, copy=True)
        if (not isinstance(self.start, (int, np.integer)) or not isinstance(self.end, (int, np.integer))
                or self.start < 0 or self.end <= self.start or p.shape != (257,)
                or not np.isfinite(p).all() or np.any((p < 0) | (p > 1))):
            raise ValueError('Valid interval and pitch probability vector required')
        p.setflags(write=False)
        object.__setattr__(self, 'activation', p)
        voiced = p.max() if self.voiced_probability is None else self.voiced_probability
        if not np.isfinite(voiced) or not 0 <= voiced <= 1:
            raise ValueError('Valid independent voiced probability required')
        object.__setattr__(self, 'voiced_probability', float(voiced))
        if self.f0_likelihood is not None:
            f = np.array(self.f0_likelihood, dtype=float, copy=True)
            if f.shape != (128,) or not np.isfinite(f).all() or np.any((f <= 0) | (f > 1)):
                raise ValueError('Positive finite acoustic pitch likelihood required')
            f.setflags(write=False)
            object.__setattr__(self, 'f0_likelihood', f)


@dataclass(frozen=True)
class DecodeConfig:
    """One score function's coefficients; no special-case correction flags."""
    neural_boundary_weight: float = 1.
    phonetic_boundary_weight: float = 2.
    note_cost: float = .5
    pitch_transition_weight: float = .025
    tonality_weight: float = 1.
    acoustic_pitch_weight: float = 0.
    duration_weight: float = 0.
    likelihood_floor: float = .01
    max_boundary_span: int = 4
    phonetic_tolerance_frames: int = 15

    def __post_init__(self):
        coefficients = (self.neural_boundary_weight, self.phonetic_boundary_weight,
                        self.note_cost, self.pitch_transition_weight, self.tonality_weight,
                        self.acoustic_pitch_weight, self.duration_weight)
        if not all(np.isfinite(v) and v >= 0 for v in coefficients):
            raise ValueError('Finite nonnegative decoding coefficients required')
        if (not 0 < self.likelihood_floor < .5 or not isinstance(self.max_boundary_span, int)
                or not 1 <= self.max_boundary_span <= 8):
            raise ValueError('Invalid likelihood floor or interval search bound')
        if not isinstance(self.phonetic_tolerance_frames, int) or not 0 <= self.phonetic_tolerance_frames <= 25:
            raise ValueError('Invalid acoustic boundary alignment tolerance')
