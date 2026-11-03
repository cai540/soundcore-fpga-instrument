"""Acoustic counterexamples, not claims of accuracy on real performances."""
import unittest
import numpy as np
from native_voice_refinement import (recover_register, absorb_release_duplicates,
    absorb_glide_transients, refine)
from note_probability_fusion import basic_times


def note(start, duration, pitch):
    return {'start_ms': start, 'duration_ms': duration, 'midi': pitch, 'confidence': 0.}


def observations(pitches):
    p = np.asarray(pitches, float)
    frames = len(p)
    evidence = {'rmvpe': 440 * 2 ** ((p - 69) / 12), 'word': np.zeros(frames)}
    pesto = {'midi': p.copy(), 'confidence': np.ones(frames)}
    acoustic = {'rms': np.full(frames, .1), 'flux': np.zeros(frames)}
    boundary = {'novelty': np.zeros(frames), 'strength': np.zeros(frames)}
    return evidence, pesto, acoustic, boundary


def basic(rows, count=300):
    # One activation row per official Basic Pitch source time, not 10 ms.
    times = basic_times(count)
    array = np.zeros((count, 88))
    for start, end, pitch, strength in rows:
        array[(times >= start / 1000) & (times < end / 1000), pitch - 21] = strength
    return {'note': array}


class NativeRefinementTests(unittest.TestCase):
    def test_correct_high_note_is_not_lowered_by_continuity_and_weak_alias(self):
        ns = [note(0, 400, 69), note(400, 400, 77), note(800, 400, 64)]
        e, p, _, _ = observations(np.r_[np.full(40, 69), np.full(40, 65), np.full(80, 64)])
        b = basic([(400, 800, 65, .25), (400, 800, 77, .21)])
        out, _ = recover_register(ns, [np.array([69, 77, 64.])] * 3, e, p, b)
        self.assertEqual(out, ns)

    def test_context_and_measurements_recover_isolated_low_period_alias(self):
        ns = [note(0, 400, 77), note(400, 400, 64), note(800, 400, 74)]
        e, p, _, _ = observations(np.r_[np.full(40, 77), np.tile([64, 64, 76, 76], 10), np.full(80, 74)])
        b = basic([(400, 800, 64, .35), (400, 800, 76, .18)])
        views = [np.array([77, k, 74.]) for k in [64, 76, 64]]
        out, _ = recover_register(ns, views, e, p, b)
        self.assertEqual([n['midi'] for n in out], [77, 76, 74])
        self.assertEqual([(n['start_ms'], n['duration_ms']) for n in ns],
                         [(n['start_ms'], n['duration_ms']) for n in out])

    def test_two_correlated_local_aliases_do_not_override_coherent_main_register(self):
        ns = [note(0, 400, 77), note(400, 400, 76), note(800, 400, 74)]
        e, p, _, _ = observations(np.r_[np.full(40, 77), np.tile([64, 64, 76, 76], 10), np.full(80, 74)])
        b = basic([(400, 800, 64, .45), (400, 800, 76, .18)])
        views = [np.array([77, k, 74.]) for k in [64, 76, 64]]
        out, audit = recover_register(ns, views, e, p, b)
        self.assertEqual(out, ns)
        self.assertIsNotNone(audit[1]['alternatives'][0]['abstention'])

    def test_true_upward_octave_is_allowed_despite_continuity_cost(self):
        ns = [note(0, 400, 60), note(400, 400, 60), note(800, 400, 65)]
        e, p, _, _ = observations(np.r_[np.full(40, 60), np.tile([60, 72], 20), np.full(80, 65)])
        b = basic([(400, 800, 60, .3), (400, 800, 72, .8)])
        out, _ = recover_register(ns, [np.array([60, 60, 65.])] * 3, e, p, b)
        self.assertEqual(out[1]['midi'], 72)

    def test_unarticulated_short_release_is_absorbed_without_filling_rest(self):
        ns = [note(200, 440, 69), note(640, 70, 69), note(1000, 400, 65)]
        e, p, a, b = observations(np.full(200, 69.))
        out, audit = absorb_release_duplicates(ns, e, p, a, b)
        self.assertEqual(out, [note(200, 510, 69), ns[-1]])
        self.assertEqual(out[-1]['start_ms'] - out[0]['start_ms'] - out[0]['duration_ms'], 290)
        self.assertEqual(len(audit), 1)

    def test_real_short_same_pitch_word_has_priority(self):
        ns = [note(200, 440, 69), note(640, 70, 69)]
        for measured in ('word', 'novelty', 'energy'):
            e, p, a, b = observations(np.full(200, 69.))
            if measured == 'word':
                e['word'][64] = 1
            elif measured == 'novelty':
                b['novelty'][64] = .12
            else:
                a['rms'][62:65] = .01
            self.assertEqual(absorb_release_duplicates(ns, e, p, a, b)[0], ns)

    def test_pitch_dropout_can_use_two_other_measured_sources(self):
        ns = [note(200, 440, 69), note(640, 70, 69)]
        e, p, a, b = observations(np.full(200, 69.))
        p['confidence'][:] = 0
        e['fcpe'] = e['rmvpe'].copy()
        e['fcpe_confidence'] = np.ones(200)
        out, audit = absorb_release_duplicates(ns, e, p, a, b)
        self.assertEqual(out, [note(200, 510, 69)])
        self.assertEqual([q['source'] for q in audit[0]['pitch_support']], ['RMVPE', 'FCPE'])
        e.pop('fcpe')
        e.pop('fcpe_confidence')
        self.assertEqual(absorb_release_duplicates(ns, e, p, a, b)[0], ns)

    def test_reliable_pitch_disagreement_protects_release_attack(self):
        ns = [note(200, 440, 69), note(640, 70, 69)]
        e, p, a, b = observations(np.full(200, 69.))
        e['fcpe'] = np.full(200, 440 * 2 ** ((71 - 69) / 12))
        e['fcpe_confidence'] = np.ones(200)
        self.assertEqual(absorb_release_duplicates(ns, e, p, a, b)[0], ns)

    def test_normal_same_pitch_words_survive_even_weak_boundary_measurement(self):
        ns = [note(200, 400, 60), note(600, 370, 60)]
        e, p, a, b = observations(np.full(200, 60.))
        self.assertEqual(absorb_release_duplicates(ns, e, p, a, b)[0], ns)

    def test_distinct_real_90_ms_note_is_preserved(self):
        ns = [note(200, 400, 72), note(600, 90, 73), note(690, 400, 74)]
        e, p, a, b = observations(np.r_[np.full(60, 72), np.full(9, 73), np.full(100, 74)])
        self.assertEqual(absorb_glide_transients(ns, e, p, a, b)[0], ns)

    def test_between_note_continuous_glide_needs_both_observations(self):
        ns = [note(200, 400, 72), note(600, 140, 73), note(740, 400, 74)]
        trajectory = np.r_[np.full(60, 72), np.linspace(72.2, 73.8, 14), np.full(100, 74)]
        e, p, a, b = observations(trajectory)
        out, _ = absorb_glide_transients(ns, e, p, a, b)
        self.assertEqual(out, [note(200, 540, 72), ns[-1]])
        p['midi'][60:74] = 73
        self.assertEqual(absorb_glide_transients(ns, e, p, a, b)[0], ns)

    def test_no_invented_notes_when_input_empty(self):
        e, p, a, b = observations(np.full(100, 69.))
        out, audit = refine([], e, p, a, b, [], basic([]))
        self.assertEqual(out, [])
        self.assertFalse(audit['reference_lyrics_or_song_identity_used'])

    def test_transposition_changes_pitch_but_not_glide_timing(self):
        outputs = []
        for shift in (0, 3, 7):
            ns = [note(200, 400, 65 + shift), note(600, 140, 66 + shift), note(740, 400, 67 + shift)]
            e, p, a, b = observations(np.r_[np.full(60, 65), np.linspace(65.2, 66.8, 14), np.full(100, 67)] + shift)
            outputs.append(absorb_glide_transients(ns, e, p, a, b)[0])
        self.assertEqual([[q['midi'] for q in ns] for ns in outputs], [[65, 67], [68, 70], [72, 74]])
        self.assertTrue(all([(n['start_ms'], n['duration_ms']) for n in ns] == [(200, 540), (740, 400)] for ns in outputs))


if __name__ == '__main__':
    unittest.main(verbosity=2)
