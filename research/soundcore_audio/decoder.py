"""One MAP decision over note/rest intervals, pitch and phonetic boundaries.

There are no correction passes after this function: false extra attacks,
missing subdivisions, rests and octave choices compete in the same graph.
All coefficients belong to one explicit cost function and can be ablated.
"""
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.signal import find_peaks
from scipy.special import expit, logit, softmax
from .types import DecodeConfig, Note, IntervalEvidence


def interval_candidates(observation, cuts, max_span):
    """Pool fixed observations; never change neural context for an edge.

    This is the geometric mean of the original region likelihoods, weighted
    by owned source time. Native intervals always remain available, including
    a long held vowel or silence containing many weak boundary proposals.
    """
    bounds = np.asarray(observation.cuts)
    edges = {(int(a), int(z)) for a, z in zip(bounds, bounds[1:])}
    for i, start in enumerate(cuts[:-1]):
        edges.update((int(start), int(end)) for end in cuts[i + 1:i + 1 + max_span])
    log_pitch = np.log(np.asarray(observation.pitch_activation).clip(1e-8, 1))
    log_voiced = np.log(observation.pitch_activation.max(axis=1).clip(1e-8, 1))
    result = []
    for a, z in sorted(edges):
        overlap = np.maximum(0, np.minimum(z, bounds[1:]) - np.maximum(a, bounds[:-1]))
        probability = np.exp(overlap @ log_pitch / (z - a))
        voiced = float(np.exp(overlap @ log_voiced / (z - a)))
        result.append(IntervalEvidence(a, z, probability, voiced_probability=voiced))
    return result


def candidate_cuts(observation, phonetic):
    phonetic = np.asarray(phonetic, float)
    if len(phonetic) != len(observation.boundary_probability):
        raise ValueError('Boundary evidence must share the model frame grid')
    if not np.isfinite(phonetic).all() or np.any((phonetic < 0) | (phonetic > 1)):
        raise ValueError('Finite acoustic boundary probabilities required')
    peaks, _ = find_peaks(phonetic, height=.25, prominence=.1, distance=10)
    # Nearby measurements describe one alternative boundary location. Retain
    # both when they differ by >20 ms, so the graph can choose the timing.
    cuts = list(map(int, observation.cuts))
    for peak in peaks:
        if min(abs(np.asarray(cuts) - peak)) > 2:
            cuts.append(int(peak))
    return np.array(sorted(set(cuts)), int)


def tonal_prior(observations):
    """Marginalize recording-derived keys; no key or scale is supplied.

    A chromatic pitch remains eligible. A strong acoustic likelihood can
    outweigh this soft prior; it is never snapped into a seven-note mask.
    """
    histogram = np.zeros(12)
    pitches = np.arange(1, 128)
    for observation in observations:
        duration = np.diff(observation.cuts) * .01
        strength = np.asarray(observation.pitch_activation[:, pitches * 2], float)
        strength /= np.maximum(strength.sum(axis=1, keepdims=True), 1e-9)
        voiced = np.maximum(observation.pitch_activation.max(axis=1) - .2, 0)
        for pitch in pitches:
            histogram[pitch % 12] += np.sum(strength[:, pitch - 1] * voiced * np.minimum(duration, 1.5))
    if histogram.sum() == 0:
        return np.ones(128), {'key_posterior': [1 / 12] * 12, 'class_histogram': histogram.tolist()}
    masks = np.zeros((12, 12))
    for root in range(12):
        masks[root, (np.array([0, 2, 4, 5, 7, 9, 11]) + root) % 12] = 1
    coverage = masks @ (histogram / histogram.sum())
    keys = softmax((coverage - coverage.max()) / .025)
    membership = (keys @ masks).clip(.1, 1.)
    prior = membership[np.arange(128) % 12]
    prior[0] = 1.
    return prior, {'key_posterior': keys.tolist(), 'class_histogram': histogram.tolist()}


def decode(observation, phonetic, intervals, config=DecodeConfig(), pitch_prior=None, typical_duration=None):
    cuts = candidate_cuts(observation, phonetic)
    frames = int(cuts[-1])
    if pitch_prior is None:
        pitch_prior, _ = tonal_prior([observation])
    pitch_prior = np.asarray(pitch_prior, float)
    if pitch_prior.shape != (128,) or np.any(pitch_prior <= 0):
        raise ValueError('Positive soft pitch prior required')
    if typical_duration is None:
        durations = np.diff(observation.cuts)[observation.pitch_activation.max(axis=1) >= .2] * .01
        typical_duration = float(np.median(durations)) if len(durations) else .3
    if not np.isfinite(typical_duration) or typical_duration <= 0:
        raise ValueError('A positive recording-derived typical note duration required')
    neural = maximum_filter1d(observation.boundary_probability, size=5)
    # Consonant/word boundaries and a pitched vowel's attack are different
    # measured instants. Allow for their local alignment uncertainty,
    # instead of treating a 100 ms offset as evidence of a missing syllable.
    phone = maximum_filter1d(phonetic, size=2 * config.phonetic_tolerance_frames + 1)
    log_odds = (config.neural_boundary_weight * logit(neural.clip(.05, .995))
                + config.phonetic_boundary_weight * logit(phone.clip(.1, .95)))
    probability = expit(log_odds[cuts[1:-1]])
    cut_cost = -np.log(probability.clip(1e-8, 1)) + config.note_cost
    skip_cost = -np.log((1 - probability).clip(1e-8, 1))
    cut_cost = np.r_[0., cut_cost, 0.]
    prefix_skip = np.r_[0., 0., np.cumsum(skip_cost)]
    index = {int(t): i for i, t in enumerate(cuts)}
    edges = {}
    for item in intervals:
        if item.start not in index or item.end not in index or item.end <= item.start:
            continue
        a, z = index[item.start], index[item.end]
        if np.asarray(item.activation).shape != (257,) or not np.isfinite(item.activation).all():
            raise ValueError('Finite GAME interval pitch activations required')
        edges.setdefault(a, []).append((z, item))
    pitches = np.arange(128)
    distance = abs(pitches[:, None] - pitches[None, :]).astype(float)
    transition = distance * config.pitch_transition_weight
    transition[0, :] = transition[:, 0] = 0  # A breath resets the melodic context.
    score = np.full((len(cuts), 128), np.inf)
    score[0, :] = 0.
    previous_node = np.full((len(cuts), 128), -1, int)
    previous_pitch = np.full((len(cuts), 128), -1, int)
    selected_cost = {}
    for a in range(len(cuts) - 1):
        if not np.isfinite(score[a]).any():
            continue
        incoming = score[a, :, None] + transition
        parent_pitch = incoming.argmin(axis=0)
        best_incoming = incoming[parent_pitch, pitches]
        for z, item in edges.get(a, []):
            activity = np.asarray(item.activation, float)
            likelihood = activity[pitches * 2].copy()
            # Disagreement about pitch is not evidence of silence. Presence
            # is pooled from the original voiced observations independently.
            likelihood[0] = 1 - item.voiced_probability
            duration = (item.end - item.start) * .01
            emission = (-np.log(likelihood.clip(config.likelihood_floor, 1))
                        - config.tonality_weight * np.log(pitch_prior)) * (duration / .3)
            if config.acoustic_pitch_weight:
                if item.f0_likelihood is None:
                    raise ValueError('Configured acoustic pitch observation is missing')
                emission -= config.acoustic_pitch_weight * np.log(item.f0_likelihood) * (duration / .3)
            # A soft, recording-relative duration prior competes with the
            # measured boundary likelihood. No short event is deleted or
            # forbidden, and an actual rest receives no duration penalty.
            emission[1:] += config.duration_weight * np.log(duration / typical_duration) ** 2
            boundary = cut_cost[z] + prefix_skip[z] - prefix_skip[a + 1]
            proposal = best_incoming + emission + boundary
            improved = proposal < score[z]
            score[z, improved] = proposal[improved]
            previous_node[z, improved] = a
            previous_pitch[z, improved] = parent_pitch[improved]
            selected_cost[(a, z)] = {'boundary_cost': float(boundary), 'duration_s': duration}
    if not np.isfinite(score[-1]).any():
        raise ValueError('Candidate intervals do not form a complete source-time path')
    pitch = int(score[-1].argmin())
    node = len(cuts) - 1
    path = []
    while node:
        parent = int(previous_node[node, pitch])
        if parent < 0:
            raise RuntimeError('Incomplete decoder backtrace')
        path.append((parent, node, pitch))
        pitch, node = int(previous_pitch[node, pitch]), parent
    path.reverse()
    notes = [Note(int(cuts[a]) * 10, int(cuts[z]) * 10, p) for a, z, p in path if p]
    audit = {'candidate_cuts': cuts.tolist(), 'selected_intervals': [
        {'start_frame': int(cuts[a]), 'end_frame': int(cuts[z]), 'midi': p,
         **selected_cost[(a, z)]} for a, z, p in path],
        'objective': float(score[-1].min()), 'postprocessing_corrections': 0,
        'model_frame_count': frames}
    return notes, audit
