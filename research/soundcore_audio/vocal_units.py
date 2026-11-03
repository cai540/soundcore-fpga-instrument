"""Single carriers on automatic vowel units with immutable native evidence.

The source aligner proposes time ownership. Acoustic vectors are pooled once
from the unchanged native pitch observations. A soft scale prior uses only
corroborated F0 classes; it never folds octaves or excludes chromatic notes.
No song identity, known lyric, reference score or emitted-note repair is used.
"""
from dataclasses import dataclass
import numpy as np
from scipy.special import softmax
from .articulation import classify_carrier_sequence
from .types import Note


@dataclass(frozen=True)
class VocalUnitConfig:
    acoustic_pitch_weight: float = .5
    tonality_weight: float = .5
    transition_weight: float = .05

    def __post_init__(self):
        if any(not np.isfinite(v) or v < 0 for v in
               (self.acoustic_pitch_weight, self.tonality_weight, self.transition_weight)):
            raise ValueError('Finite nonnegative vocal sequence coefficients required')


def source_scale_prior(center_pairs):
    """Marginalize twelve diatonic rotations from agreeing source F0 centres.

    NaN means unavailable. Agreement is modulo octave for this feature only;
    the exact-register classifier remains responsible for choosing an octave.
    This self-consistency is not an accuracy estimate or acceptance score.
    """
    pair = np.asarray(center_pairs, float)
    if (pair.ndim != 2 or pair.shape[1] != 2 or np.isinf(pair).any()
            or np.any(np.isfinite(pair) & ((pair < 1) | (pair > 127)))):
        raise ValueError('Two valid source F0 centres or NaN per unit required')
    delta = (pair[:, 1] - pair[:, 0] + 6) % 12 - 6
    valid = np.isfinite(pair).all(axis=1) & (abs(delta) < .35)
    values = (pair[:, 0] + delta / 2)[valid]
    if len(values) < 5:
        return np.ones(128), {'posterior': [1 / 12] * 12,
                             'corroborated_units': len(values), 'insufficient_consensus': True}
    residual = (np.arange(12)[None, :] - values[:, None] + 6) % 12 - 6
    classes = np.exp(-.5 * (residual / .35) ** 2)
    classes /= classes.sum(axis=1, keepdims=True)
    mask = np.zeros((12, 12))
    for root in range(12):
        mask[root, (np.array([0, 2, 4, 5, 7, 9, 11]) + root) % 12] = 1
    coverage = classes @ mask.T
    scores = np.log((.02 + .98 * coverage).clip(.001, 1)).sum(axis=0)
    posterior = softmax(scores - scores.max())
    membership = .1 + .9 * (posterior @ mask)
    return membership[np.arange(128) % 12], {
        'posterior': posterior.tolist(), 'scores': scores.tolist(),
        'corroborated_units': len(values), 'pitch_class_mass': classes.sum(axis=0).tolist()}


def validate_unit_ranges(ranges, source_frames):
    ranges = np.asarray(ranges)
    if (ranges.ndim != 2 or ranges.shape[1] != 2 or len(ranges) < 1
            or not np.issubdtype(ranges.dtype, np.integer)
            or not isinstance(source_frames, (int, np.integer)) or source_frames < 1
            or np.any(ranges[:, 0] < 0) or np.any(ranges[:, 1] > source_frames)
            or np.any(ranges[:, 1] <= ranges[:, 0])
            or np.any(ranges[1:, 0] < ranges[:-1, 1])):
        raise ValueError('Positive nonoverlapping integer source-unit ranges required')
    return ranges


def pool_native_units(cuts, activation, ranges):
    """Time mixture of fixed native vectors; never reclassify a new partition."""
    cuts, activation = np.asarray(cuts), np.asarray(activation, float)
    if (cuts.ndim != 1 or len(cuts) < 2 or cuts[0] != 0
            or not np.issubdtype(cuts.dtype, np.integer) or np.any(np.diff(cuts) <= 0)
            or activation.shape != (len(cuts) - 1, 257)
            or not np.isfinite(activation).all() or np.any((activation < 0) | (activation > 1))):
        raise ValueError('Complete fixed native pitch observations required')
    ranges = validate_unit_ranges(ranges, int(cuts[-1]))
    # An overlap integral avoids materializing a long frame-by-pitch array.
    overlap = np.maximum(0, np.minimum(ranges[:, 1, None], cuts[None, 1:])
                         - np.maximum(ranges[:, 0, None], cuts[None, :-1]))
    return (overlap @ activation[:, np.arange(128) * 2]
            / (ranges[:, 1] - ranges[:, 0])[:, None])


def decode_vocal_units(ranges, source_frames, activation, acoustic, center_pairs,
                       config=VocalUnitConfig()):
    """One principal carrier per proposed vowel, full source timing retained."""
    if not isinstance(config, VocalUnitConfig):
        raise TypeError('An explicit vocal sequence configuration is required')
    ranges = validate_unit_ranges(ranges, source_frames)
    activation, acoustic = np.asarray(activation, float), np.asarray(acoustic, float)
    centers = np.asarray(center_pairs, float)
    if activation.shape != (len(ranges), 128) or centers.shape != (len(ranges), 2):
        raise ValueError('Each source unit needs its own pitch and F0 evidence')
    if np.any(activation[:, 1:].max(axis=1) < .01):
        raise ValueError('A proposed source unit has no pitched acoustic support')
    prior, info = source_scale_prior(centers)
    path = classify_carrier_sequence(activation, prior, acoustic,
        config.acoustic_pitch_weight, config.tonality_weight, config.transition_weight)
    notes = tuple(Note(int(a * 10), int(z * 10), int(p)) for (a, z), p in zip(ranges, path))
    return notes, info
