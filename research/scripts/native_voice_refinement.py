"""Combine the useful earlier acoustic refinements with native note events.

One principal singing model owns the schedule. Earlier code supplies broad
phonetic-envelope measurements, complete-note context evidence and periodic
vowel centers. Octaves are categorical alternatives, never arithmetic means.
No supplied lyrics, song identity, reference score or known key is accepted.
"""
import numpy as np
from note_probability_fusion import basic_times
from periodic_vowel_events import collapse_periodic_vowels
from vocal_event_refinement import refine_events

VERSION = 'native-voice-with-protected-legacy-refinements-v1'


def _midi(hz):
    return np.where(hz > 0, 69 + 12 * np.log2(np.maximum(hz, 1) / 440), np.nan)


def _support(values, valid, start, end, target):
    x = values[start:end]
    ok = valid[start:end] & np.isfinite(x)
    return float(np.mean(abs(x[ok] - target) < 1.25)) if np.any(ok) else 0.


def recover_register(notes, views, evidence, pesto, basic):
    """Reuse the former context/register idea with an explicit abstain path.

    A continuity-only proposal cannot lower a genuine high note. Conversely,
    a clear polyphonic note plus two measured continuous observations can
    recover an octave even when the main interval model repeats a low alias.
    Multiple contexts from one model are not independent model votes.
    """
    rm = _midi(evidence['rmvpe'])
    pp = np.asarray(pesto['midi'])
    pc = np.asarray(pesto['confidence'])
    bt = basic_times(len(basic['note']))
    out, audit = [], []
    for i, n in enumerate(notes):
        old = n['midi']
        begin, end = n['start_ms'], n['start_ms'] + n['duration_ms']
        edge = min(40, n['duration_ms'] // 8)
        a, z = max(0, (begin + edge + 9) // 10), min(len(rm), (end - edge + 9) // 10)
        x, y = np.searchsorted(bt, [(begin + edge) / 1000, (end - edge) / 1000])
        bp = np.asarray(basic['note'][x:y]).mean(axis=0) if y > x else np.zeros(88)
        probability = lambda k: float(bp[k - 21]) if 21 <= k <= 108 else 0.
        context = np.asarray([v[i] for v in views], float)
        alternatives = []
        for target in (old - 12, old + 12):
            if not 24 <= target <= 108:
                continue
            count = int(np.sum(abs(context - target) < 1.))
            measured = [_support(rm, np.isfinite(rm), a, z, target),
                        _support(pp, pc > .5, a, z, target)]
            old_prob, new_prob = probability(old), probability(target)
            neighbors = []
            if i and begin - notes[i - 1]['start_ms'] - notes[i - 1]['duration_ms'] < 250:
                neighbors.append(notes[i - 1]['midi'])
            if i + 1 < len(notes) and notes[i + 1]['start_ms'] - end < 250:
                neighbors.append(notes[i + 1]['midi'])
            gain = sum(abs(old - q) - abs(target - q) for q in neighbors)
            bounded = bool(neighbors) and max(abs(target - q) for q in neighbors) <= 5
            reason = None
            if count >= 2 and new_prob > .12 and new_prob >= old_prob * .55 and max(measured) > .2:
                reason = 'whole_note_context_with_acoustic_register_support'
            elif (count >= 1 and new_prob > .12 and new_prob >= old_prob * .4
                  and min(measured) > .1 and bounded and gain >= 12
                  and not any(abs(old - q) == 12 for q in neighbors)):
                reason = 'context_and_two_f0_tracks_reject_isolated_period_alias'
            elif (new_prob > .35 and new_prob > old_prob * 1.15
                  and min(measured) >= .25):
                reason = 'strong_polyphonic_note_and_two_continuous_register_observations'
            # Half-period errors can agree across several local trackers.
            # Preserve the main model's coherent two-sided melodic register
            # when an alternative would create an isolated octave detour,
            # unless both continuous sources and note activity are decisive.
            isolated_detour = (len(neighbors) == 2
                and max(abs(old - q) for q in neighbors) <= 5
                and min(abs(target - q) for q in neighbors) >= 9)
            abstention = None
            if reason and isolated_detour and (min(measured) < .8 or new_prob < .65):
                reason = None
                abstention = 'retain_coherent_main_model_register_over_ambiguous_two_sided_detour'
            alternatives.append({'target': target, 'context_count': count,
                'continuous_support': measured, 'basic_target': new_prob, 'basic_old': old_prob,
                'continuity_gain': gain, 'reason': reason, 'abstention': abstention})
        accepted = [q for q in alternatives if q['reason']]
        choice = max(accepted, key=lambda q: q['basic_target']) if accepted else None
        out.append({**n, 'midi': int(choice['target']) if choice else old})
        audit.append({'start_ms': begin, 'old_midi': old, 'new_midi': out[-1]['midi'],
                      'alternatives': alternatives, 'reason': choice['reason'] if choice else 'retain'})
    return out, audit


def boundary_observation(k, evidence, acoustic, boundary):
    """Missing measurements mean uncertainty, never permission to merge."""
    rms = acoustic['rms']
    if k < 16 or k + 16 >= len(rms):
        return None
    left = float(np.quantile(rms[k - 15:k - 3], .8))
    right = float(np.quantile(rms[k + 3:k + 15], .8))
    return {'word_peak': float(np.max(evidence['word'][k - 6:k + 7])),
            'novelty_peak': float(np.max(boundary['novelty'][k - 3:k + 4])),
            'valley_ratio': float(np.min(rms[k - 3:k + 4])) / max(min(left, right), 1e-9),
            'right_to_left_energy': right / max(left, 1e-9)}


def absorb_glide_transients(notes, evidence, pesto, acoustic, boundary):
    rm = _midi(evidence['rmvpe'])
    pp = np.asarray(pesto['midi'])
    pc = np.asarray(pesto['confidence'])
    out, audit = [], []
    for i, n in enumerate(notes):
        if not out or i + 1 == len(notes):
            out.append(dict(n))
            continue
        left, right = out[-1], notes[i + 1]
        a, z = n['start_ms'], n['start_ms'] + n['duration_ms']
        between = min(left['midi'], right['midi']) < n['midi'] < max(left['midi'], right['midi'])
        stats = boundary_observation(a // 10, evidence, acoustic, boundary)
        if (not between or n['duration_ms'] > 180 or a != left['start_ms'] + left['duration_ms']
                or z != right['start_ms'] or abs(left['midi'] - right['midi']) > 5
                or stats is None or stats['word_peak'] >= .2 or stats['novelty_peak'] >= .04
                or stats['valley_ratio'] <= .8):
            out.append(dict(n))
            continue
        fits = []
        direction = np.sign(right['midi'] - left['midi'])
        for track, valid in ((rm, np.isfinite(rm)), (pp, pc > .5)):
            s, e = (a + 9) // 10, min(len(track), (z + 9) // 10)
            x = track[s:e]
            ok = valid[s:e] & np.isfinite(x)
            if len(x) < 8 or ok.mean() < .8:
                break
            t = np.arange(len(x))[ok] * .01
            value = x[ok]
            slope, intercept = np.polyfit(t, value, 1)
            variance = float(np.mean((value - value.mean()) ** 2))
            explained = 1 - float(np.mean((value - intercept - slope * t) ** 2)) / max(variance, 1e-9)
            drift = float(np.median(value[-max(2, len(value) // 3):]) - np.median(value[:max(2, len(value) // 3)]))
            # A short *flat* chromatic step is an actual candidate note, not
            # a monotonic between-note glide, even without a new consonant.
            if explained < .6 or direction * drift < .65:
                break
            fits.append({'slope_semitones_per_second': float(slope), 'explained': explained, 'drift': drift})
        if len(fits) == 2:
            out[-1]['duration_ms'] += n['duration_ms']
            audit.append({**n, 'reason': 'unarticulated_monotonic_between_note_glide',
                          'boundary': stats, 'two_track_fits': fits})
        else:
            out.append(dict(n))
    return out, audit


def absorb_release_duplicates(notes, evidence, pesto, acoustic, boundary):
    rm = _midi(evidence['rmvpe'])
    pp = np.asarray(pesto['midi'])
    pc = np.asarray(pesto['confidence'])
    out, audit = [], []
    for i, n in enumerate(notes):
        stats = boundary_observation(n['start_ms'] // 10, evidence, acoustic, boundary)
        previous = out[-1] if out else None
        end = n['start_ms'] + n['duration_ms']
        next_gap = notes[i + 1]['start_ms'] - end if i + 1 < len(notes) else 1000
        eligible = (previous is not None and n['midi'] == previous['midi']
            and previous['start_ms'] + previous['duration_ms'] == n['start_ms']
            and previous['duration_ms'] >= 240 and n['duration_ms'] <= 120
            and n['duration_ms'] < previous['duration_ms'] * .35 and next_gap >= 160)
        measured = (stats is not None and stats['word_peak'] < .9 and stats['novelty_peak'] < .065
                    and stats['valley_ratio'] > .8 and stats['right_to_left_energy'] < 1.2)
        a, z = (n['start_ms'] + 9) // 10, min(len(rm), (end + 9) // 10)
        tracks = [('RMVPE', rm, np.isfinite(rm)), ('PESTO', pp, pc > .5)]
        if 'fcpe' in evidence and 'fcpe_confidence' in evidence:
            fc = _midi(evidence['fcpe'])
            tracks.append(('FCPE', fc, evidence['fcpe_confidence'] > .35))
        pitch_support = []
        for name, values, valid in tracks:
            coverage = float(np.mean(valid[a:z])) if z > a else 0.
            if coverage >= .6:
                pitch_support.append({'source': name, 'coverage': coverage,
                    'target_fraction': _support(values, valid, a, z, n['midi'])})
        # A model dropout is not a contrary pitch vote. Two measured tracks
        # are still required; a reliable contradictory source protects the cut.
        supported = len(pitch_support) >= 2 and all(q['target_fraction'] >= .65 for q in pitch_support)
        if eligible and measured and supported:
            out[-1]['duration_ms'] += n['duration_ms']
            audit.append({**n, 'reason': 'unarticulated_same_vowel_release_fragment',
                          'boundary': stats, 'pitch_support': pitch_support})
        else:
            out.append(dict(n))
    return out, audit


def refine(notes, evidence, pesto, acoustic, boundary, views, basic):
    """Trace each change; never bridge an existing rest or add a lyric clock."""
    raw = [dict(n) for n in notes]
    pitched, register = recover_register(raw, views, evidence, pesto, basic)
    # Reuse the old center fitter while disabling its overbroad same-pitch
    # merge. The full native-waveform ablation exposed missing real syllables.
    centered, center_audit = refine_events(pitched, evidence, pesto, acoustic, merge_same_vowel=False)
    glides, glide_audit = absorb_glide_transients(centered, evidence, pesto, acoustic, boundary)
    # Phonetic envelope changes independently protect real syllable boundaries.
    protected = dict(evidence)
    protected['word'] = np.maximum(evidence['word'], np.where(boundary['strength'] >= .12, 1., 0.))
    periodic, periodic_audit = collapse_periodic_vowels(glides, protected, pesto, minimum_fragments=2)
    result, release_audit = absorb_release_duplicates(periodic, evidence, pesto, acoustic, boundary)
    return result, {'version': VERSION, 'register': register, 'centers': center_audit,
        'glide_transients': glide_audit, 'periodic': periodic_audit, 'release_duplicates': release_audit,
        'old_notes': len(raw), 'new_notes': len(result), 'existing_rests_filled': 0,
        'legacy_modules_reused': ['vocal_event_refinement', 'vocal_pitch_center', 'periodic_vowel_events',
                                  'VocalBoundaryEvidence port', 'complete-note context estimator'],
        'reference_lyrics_or_song_identity_used': False, 'real_world_90_percent_verified': False}
