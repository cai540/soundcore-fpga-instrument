"""Playable vocal carriers on a fixed, source-derived articulation graph.

This optional experimental decoder does not recognize lyrics. An observer
supplies automatic unit proposals and immutable acoustic evidence. The graph
assigns source time to each proposal, including rests. Each unit owns one
carrier by default and can never own more than two. Pitch classification is
a separate sequence decision; neither stage edits an already emitted list.
"""
from dataclasses import dataclass
import numpy as np
from .types import Note


def _readonly(value, shape, name, probability=False, integer=False):
    original = np.asarray(value)
    if (original.shape != shape or not np.isfinite(original).all()
            or (integer and not np.issubdtype(original.dtype, np.integer))
            or (probability and np.any((original < 0) | (original > 1)))):
        raise ValueError(f'Invalid {name}')
    result = np.array(original, dtype=int if integer else float, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ArticulationEvidence:
    """Edges use cut indices; times use 10 ms frames on the original clock.

    `carrier` is a time-weighted *mixture* of fixed native pitch vectors,
    not their geometric intersection. This preserves competing modes, but
    overlapping broad native peaks can still yield an incorrect carrier;
    this experimental observation does not guarantee source-pitch accuracy.
    `content_cost` optionally scores within-unit phonetic variation. It is
    independent of the changing sung pitch and is not an output correction.
    """
    cuts: np.ndarray
    edges: np.ndarray
    carrier: np.ndarray
    voiced: np.ndarray
    boundary_cost: np.ndarray
    phone_likelihood: np.ndarray
    pitch_boundary: np.ndarray
    units: tuple[str, ...]
    pause_after: frozenset[int]
    typical_duration_s: float
    source_sha256: str
    content_cost: np.ndarray | None = None

    def __post_init__(self):
        m, n, k = len(self.cuts), len(self.edges), len(self.units)
        if m < 2 or n < 1 or k < 1 or not all(isinstance(u, str) and u for u in self.units):
            raise ValueError('Nonempty source graph and recognized units required')
        arrays = {'cuts': ((m,), False, True), 'edges': ((n, 2), False, True),
                  'carrier': ((n, 128), True, False), 'voiced': ((n,), True, False),
                  'boundary_cost': ((m,), False, False),
                  'phone_likelihood': ((k, n), True, False),
                  'pitch_boundary': ((m,), True, False)}
        for name, (shape, probability, integer) in arrays.items():
            object.__setattr__(self, name, _readonly(getattr(self, name), shape, name, probability, integer))
        if (self.cuts[0] != 0 or np.any(np.diff(self.cuts) <= 0)
                or np.any(self.edges < 0) or np.any(self.edges >= m)
                or np.any(self.edges[:, 1] <= self.edges[:, 0])
                or len(np.unique(self.edges, axis=0)) != n):
            raise ValueError('Complete ordered cuts and unique forward edges required')
        if (not np.isfinite(self.typical_duration_s) or self.typical_duration_s <= 0
                or not isinstance(self.source_sha256, str) or not self.source_sha256
                or any(not isinstance(i, (int, np.integer)) or not 0 <= i <= k for i in self.pause_after)):
            raise ValueError('Valid timing, source provenance and clause indices required')
        object.__setattr__(self, 'units', tuple(self.units))
        object.__setattr__(self, 'pause_after', frozenset(self.pause_after) | {0, k})
        if self.content_cost is not None:
            value = _readonly(self.content_cost, (n,), 'content cost')
            if np.any(value < 0):
                raise ValueError('Content fit costs must be nonnegative')
            object.__setattr__(self, 'content_cost', value)


@dataclass(frozen=True)
class CarrierConfig:
    max_notes_per_unit: int = 1
    duration_weight: float = .4
    phone_weight: float = 0.
    internal_pause_weight: float = 1.
    second_note_cost: float = 1.5
    min_turn_piece_frames: int = 12
    min_turn_semitones: int = 2
    acoustic_pitch_weight: float = 0.
    tonality_weight: float = .5
    transition_weight: float = .05

    def __post_init__(self):
        if type(self.max_notes_per_unit) is not int or self.max_notes_per_unit not in (1, 2):
            raise ValueError('A vocal unit permits exactly one or at most two carriers')
        for name in ('min_turn_piece_frames', 'min_turn_semitones'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError('Positive integer secondary-turn bounds required')
        for name in ('duration_weight', 'phone_weight', 'internal_pause_weight', 'second_note_cost',
                     'acoustic_pitch_weight', 'tonality_weight', 'transition_weight'):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError('Finite nonnegative carrier coefficients required')


@dataclass(frozen=True)
class CarrierResult:
    groups: tuple[tuple[Note, ...], ...]
    partition_cost: float

    @property
    def notes(self):
        return tuple(note for group in self.groups for note in group)


def _partition(evidence, config):
    d, c = evidence, config
    n, m, k = len(d.edges), len(d.cuts), len(d.units)
    seconds = np.diff(d.cuts[d.edges], axis=1).ravel() * .01
    carrier = d.carrier[:, 1:].max(axis=1)
    fit = -np.log(carrier.clip(.001, 1)) * seconds / .3
    if d.content_cost is not None:
        fit = -np.log(d.voiced.clip(.001, 1)) * seconds / .3 + d.content_cost
    cost, middle = fit.copy(), np.full(n, -1, int)
    lookup = {(int(a), int(z)): e for e, (a, z) in enumerate(d.edges)}
    if c.max_notes_per_unit == 2:
        pitch = d.carrier[:, 1:].argmax(axis=1) + 1
        for e, (a, z) in enumerate(d.edges):
            for b in range(a + 1, z):
                left, right = lookup.get((a, b)), lookup.get((b, z))
                if left is None or right is None:
                    continue
                if min(d.cuts[b] - d.cuts[a], d.cuts[z] - d.cuts[b]) < c.min_turn_piece_frames:
                    continue
                if abs(pitch[left] - pitch[right]) < c.min_turn_semitones:
                    continue
                trial = (fit[left] + fit[right] + c.second_note_cost
                         - .25 * np.log(max(float(d.pitch_boundary[b]), .01)))
                if trial < cost[e]:
                    cost[e], middle[e] = trial, b
    cost += c.duration_weight * np.log(seconds / d.typical_duration_s) ** 2
    phones = -c.phone_weight * np.log(d.phone_likelihood.clip(.001, 1))
    return _solve_unit_path(d, c, cost[None, :] + phones,
                            np.broadcast_to(middle, (k, n)))


def _solve_unit_path(d, c, word_cost, middle):
    """One source-time graph shared by pitch inference and locked timing."""
    n, m, k = len(d.edges), len(d.cuts), len(d.units)
    seconds = np.diff(d.cuts[d.edges], axis=1).ravel() * .01
    rest = -np.log((1 - d.voiced).clip(.001, 1)) * seconds / .3
    lookup = {(int(a), int(z)): e for e, (a, z) in enumerate(d.edges)}
    internal = np.array([i not in d.pause_after for i in range(k + 1)])
    score = np.full((k + 1, m), np.inf)
    score[0, 0] = 0.
    previous = np.full((k + 1, m), -1, int)
    used = np.zeros((k + 1, m), bool)
    chosen_middle = np.full((k + 1, m), -1, int)
    outgoing = [[] for _ in range(m)]
    for e, (a, _) in enumerate(d.edges):
        outgoing[a].append(e)
    for a in range(m - 1):
        for e in outgoing[a]:
            z = int(d.edges[e, 1])
            boundary = d.boundary_cost[z]
            trial = (score[:, a] + rest[e] + boundary
                     + c.internal_pause_weight * max(seconds[e] - .1, 0) / .3 * internal)
            better = trial < score[:, z]
            score[better, z], previous[better, z], used[better, z] = trial[better], a, False
            trial = score[:-1, a] + word_cost[:, e] + boundary
            better = trial < score[1:, z]
            indices = np.flatnonzero(better) + 1
            score[indices, z], previous[indices, z] = trial[better], a
            used[indices, z] = True
            chosen_middle[indices, z] = middle[indices - 1, e]
    if not np.isfinite(score[k, -1]):
        raise ValueError('Recognized units cannot form a complete source-time path')
    groups, z, unit = [], m - 1, k
    while z:
        a = int(previous[unit, z])
        if a < 0:
            raise ValueError('Incomplete articulation path')
        if used[unit, z]:
            b = chosen_middle[unit, z]
            groups.append((lookup[a, z],) if b < 0 else (lookup[a, b], lookup[b, z]))
            unit -= 1
        z = a
    if unit != 0 or len(groups) != k:
        raise ValueError('Articulation count changed during decoding')
    return groups[::-1], float(score[k, -1])


def align_carrier_timing(evidence, config, fixed_pitch_groups):
    """Estimate timing while preserving a previously confirmed pitch path.

    The pitch path must come from the same recording (the CLI verifies its
    provenance). There is no output merge or fixed-duration trimming. True
    rests compete in the source graph, and separate same-pitch words retain
    separate attacks. The optional two pitches of a unit stay in that order.
    """
    if not isinstance(evidence, ArticulationEvidence) or not isinstance(config, CarrierConfig):
        raise TypeError('Typed source evidence and explicit configuration required')
    groups = tuple(tuple(g) for g in fixed_pitch_groups)
    if (len(groups) != len(evidence.units)
            or any(not 1 <= len(g) <= config.max_notes_per_unit for g in groups)
            or any(not isinstance(p, (int, np.integer)) or isinstance(p, (bool, np.bool_))
                   or not 1 <= p <= 127 for g in groups for p in g)):
        raise ValueError('One or at most two valid fixed pitches per source unit required')
    d, c = evidence, config
    n, k = len(d.edges), len(d.units)
    seconds = np.diff(d.cuts[d.edges], axis=1).ravel() * .01
    loss = -np.log(d.carrier.clip(.001, 1)) * seconds[:, None] / .3
    duration = c.duration_weight * np.log(seconds / d.typical_duration_s) ** 2
    cost = np.full((k, n), np.inf)
    middle = np.full((k, n), -1, int)
    lookup = {(int(a), int(z)): e for e, (a, z) in enumerate(d.edges)}
    for unit, pitches in enumerate(groups):
        if len(pitches) == 1:
            cost[unit] = loss[:, pitches[0]]
        else:
            first, second = pitches
            for e, (a, z) in enumerate(d.edges):
                for b in range(a + 1, z):
                    left, right = lookup.get((a, b)), lookup.get((b, z))
                    if left is None or right is None:
                        continue
                    value = loss[left, first] + loss[right, second]
                    if value < cost[unit, e]:
                        cost[unit, e], middle[unit, e] = value, b
        cost[unit] += duration - c.phone_weight * np.log(d.phone_likelihood[unit].clip(.001, 1))
    paths, objective = _solve_unit_path(d, c, cost, middle)
    result = []
    for path, pitches in zip(paths, groups):
        if len(path) != len(pitches):
            raise ValueError('Timing graph changed a fixed pitch group')
        result.append(tuple(Note(int(d.cuts[d.edges[e, 0]] * 10),
                                 int(d.cuts[d.edges[e, 1]] * 10), int(pitch))
                            for e, pitch in zip(path, pitches)))
    return CarrierResult(tuple(result), objective)


def decode_carriers(evidence, config, pitch_prior=None, f0_likelihood=None):
    """Assign units once, then classify their bounded carrier sequence.

    F0 evidence, if requested, covers *all* candidate edges before selection.
    Invalid or collapsed automatic unit proposals are not padded into notes.
    The decoder contains no file, song, lyric-reference or clock exceptions.
    """
    if not isinstance(evidence, ArticulationEvidence) or not isinstance(config, CarrierConfig):
        raise TypeError('Typed articulation evidence and explicit configuration required')
    groups, objective = _partition(evidence, config)
    ids = [e for group in groups for e in group]
    prior = np.ones(128) if pitch_prior is None else np.asarray(pitch_prior, float)
    if prior.shape != (128,) or not np.isfinite(prior).all() or np.any(prior <= 0):
        raise ValueError('Positive finite pitch prior required')
    density = np.ones((len(evidence.edges), 128))
    if f0_likelihood is not None:
        density = _readonly(f0_likelihood, density.shape, 'acoustic pitch likelihood', True)
        if np.any(density <= 0):
            raise ValueError('Strictly positive acoustic pitch likelihood required')
    elif config.acoustic_pitch_weight:
        raise ValueError('Configured acoustic pitch evidence is unavailable')
    path = classify_carrier_sequence(evidence.carrier[ids], prior, density[ids],
        config.acoustic_pitch_weight, config.tonality_weight, config.transition_weight)
    result, i = [], 0
    for group in groups:
        notes = []
        for e in group:
            a, z = evidence.cuts[evidence.edges[e]]
            notes.append(Note(int(a * 10), int(z * 10), int(path[i])))
            i += 1
        result.append(tuple(notes))
    return CarrierResult(tuple(result), objective)


def classify_carrier_sequence(activation, prior, acoustic, acoustic_weight, tonal_weight, transition_weight):
    """One exact-register pitch path, shared by both source-unit decoders."""
    activation, prior, acoustic = map(lambda v: np.asarray(v, float), (activation, prior, acoustic))
    if (activation.ndim != 2 or activation.shape[0] < 1 or activation.shape[1] != 128
            or acoustic.shape != activation.shape or prior.shape != (128,)
            or not all(np.isfinite(v).all() for v in (activation, prior, acoustic))
            or np.any((activation < 0) | (activation > 1))
            or np.any((acoustic <= 0) | (acoustic > 1)) or np.any(prior <= 0)
            or any(not np.isfinite(w) or w < 0 for w in (acoustic_weight, tonal_weight, transition_weight))):
        raise ValueError('Finite source pitch likelihoods and nonnegative costs required')
    pitches = np.arange(1, 128)
    emission = (-np.log(activation[:, 1:].clip(.001, 1))
                - acoustic_weight * np.log(acoustic[:, 1:])
                - tonal_weight * np.log(prior[1:]))
    motion = np.minimum(abs(pitches[:, None] - pitches[None, :]), 12) * transition_weight
    score, parents = emission[0].copy(), []
    for row in emission[1:]:
        options = score[:, None] + motion
        parent = options.argmin(axis=0)
        score = options[parent, np.arange(127)] + row
        parents.append(parent)
    state = int(score.argmin())
    path = [state]
    for parent in reversed(parents):
        state = int(parent[state])
        path.append(state)
    return pitches[np.array(path[::-1])]
