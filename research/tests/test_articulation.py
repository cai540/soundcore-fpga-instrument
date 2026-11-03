from dataclasses import replace
import unittest
import numpy as np
from soundcore_audio.articulation import ArticulationEvidence, CarrierConfig, decode_carriers, align_carrier_timing


def fixture(pitches, units, frames=20, gaps=()):
    cuts = np.arange(len(pitches) + 1) * frames
    edges = np.array([(a, z) for a in range(len(pitches)) for z in range(a + 1, len(cuts))])
    rows = np.full((len(pitches), 128), .001)
    voiced = np.full(len(pitches), .99)
    for i, pitch in enumerate(pitches):
        if pitch is None:
            voiced[i] = .001
        else:
            rows[i, pitch] = .99
    carrier = np.stack([rows[a:z].mean(axis=0) for a, z in edges])
    presence = np.array([voiced[a:z].mean() for a, z in edges])
    return ArticulationEvidence(cuts, edges, carrier, presence, np.zeros(len(cuts)),
        np.ones((len(units), len(edges))), np.full(len(cuts), .99), tuple(units),
        frozenset(gaps), frames / 100, 'source-only-test')


class ArticulationTests(unittest.TestCase):
    def test_one_unit_turn_is_one_carrier_by_default(self):
        d = fixture([60, 64, 67, 64, 60], ['a'])
        r = decode_carriers(d, CarrierConfig())
        self.assertEqual([len(g) for g in r.groups], [1])
        self.assertEqual((r.notes[0].start_ms, r.notes[0].end_ms), (0, 1000))
        self.assertIn(r.notes[0].midi, [60, 64, 67])

    def test_optional_turn_is_bounded_inside_the_graph(self):
        d = fixture([60, 60, 72, 72], ['a'])
        r = decode_carriers(d, CarrierConfig(max_notes_per_unit=2, second_note_cost=0.))
        self.assertEqual([n.midi for n in r.notes], [60, 72])
        d = fixture([60, 64, 67, 72, 76], ['a'])
        r = decode_carriers(d, CarrierConfig(max_notes_per_unit=2, second_note_cost=0.))
        self.assertLessEqual(len(r.notes), 2)

    def test_same_pitch_different_units_keep_both_attacks(self):
        d = fixture([60, 60], ['a', 'b'])
        r = decode_carriers(d, CarrierConfig())
        self.assertEqual([n.midi for n in r.notes], [60, 60])
        self.assertEqual([n.start_ms for n in r.notes], [0, 200])

    def test_short_real_unit_is_not_removed_by_turn_duration_bound(self):
        d = fixture([60, 62, 64], ['a', 'b', 'c'], frames=8)
        r = decode_carriers(d, CarrierConfig(max_notes_per_unit=2))
        self.assertEqual([n.midi for n in r.notes], [60, 62, 64])
        self.assertEqual([n.end_ms - n.start_ms for n in r.notes], [80, 80, 80])

    def test_real_phrase_silence_is_retained(self):
        d = fixture([60, None, None, 62], ['a', 'b'], gaps=[1])
        r = decode_carriers(d, CarrierConfig())
        self.assertEqual([(n.start_ms, n.end_ms) for n in r.notes], [(0, 200), (600, 800)])

    def test_no_unbounded_setting_or_silent_rounding(self):
        for maximum in (0, 3, 1.5, True):
            with self.assertRaises(ValueError):
                CarrierConfig(max_notes_per_unit=maximum)

    def test_bad_or_incomplete_source_graph_is_rejected(self):
        d = fixture([60, 62], ['a', 'b'])
        with self.assertRaises(ValueError):
            replace(d, cuts=np.array([0., 20., 40.]))
        with self.assertRaises(ValueError):
            replace(d, edges=np.array([[0, 1], [0, 1], [1, 2]]))
        with self.assertRaises(ValueError):
            replace(d, typical_duration_s=float('nan'))
        impossible = replace(d, edges=np.array([[0, 2]]), carrier=d.carrier[[1]], voiced=d.voiced[[1]], phone_likelihood=np.ones((2, 1)))
        with self.assertRaisesRegex(ValueError, 'complete'):
            decode_carriers(impossible, CarrierConfig())

    def test_fixed_observations_stay_immutable(self):
        d = fixture([60, 64], ['a'])
        before = d.carrier.copy()
        decode_carriers(d, CarrierConfig(max_notes_per_unit=2))
        np.testing.assert_array_equal(d.carrier, before)
        with self.assertRaises(ValueError):
            d.carrier[0, 60] = .5

    def test_missing_requested_f0_is_rejected(self):
        d = fixture([60], ['a'])
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            decode_carriers(d, CarrierConfig(acoustic_pitch_weight=1.))

    def test_borrowing_next_units_pitch_does_not_inflate_score(self):
        from evaluation.transcription.character_metrics import compare_groups
        refs=[{'character':c,'allowed_sequences':[[p]]} for c,p in zip('abc',[60,62,64])]
        r=compare_groups(refs,[[60],[64],[67]])
        self.assertEqual(r['correct'],1)
        self.assertEqual(r['wrong_groups'],2)
        self.assertFalse(compare_groups(refs,[[60],[62]])['scorable'])

    def test_repeated_clip_cannot_pass_three_song_gate(self):
        from evaluation.transcription.character_metrics import gate
        r={'id':'one','strict_character_melody_consistency':1.}
        self.assertFalse(gate([r,r,r])['passed'])
        self.assertTrue(gate([{**r,'id':i} for i in ['a','b','c']])['passed'])

    def test_locked_pitch_timing_recovers_nonuniform_source_holds(self):
        d=fixture([60,60,62],['a','b'])
        r=align_carrier_timing(d,CarrierConfig(),[[60],[62]])
        self.assertEqual([(n.midi,n.start_ms,n.end_ms) for n in r.notes],[(60,0,400),(62,400,600)])

    def test_locked_timing_preserves_rest_and_same_pitch_attacks(self):
        d=fixture([60,None,None,60],['a','b'],gaps=[1])
        r=align_carrier_timing(d,CarrierConfig(),[[60],[60]])
        self.assertEqual([(n.midi,n.start_ms,n.end_ms) for n in r.notes],[(60,0,200),(60,600,800)])

    def test_locked_two_note_group_preserves_order(self):
        d=fixture([60,60,64,64],['a'])
        r=align_carrier_timing(d,CarrierConfig(max_notes_per_unit=2),[[60,64]])
        self.assertEqual([(n.midi,n.start_ms,n.end_ms) for n in r.notes],[(60,0,400),(64,400,800)])

    def test_locked_pitch_contract_rejects_wrong_counts_and_noninteger_keys(self):
        d=fixture([60,62],['a','b'])
        for values in ([[60]],[[60,61,62],[62]],[[60.5],[62]],[[True],[62]]):
            with self.assertRaises(ValueError):
                align_carrier_timing(d,CarrierConfig(max_notes_per_unit=2),values)


if __name__ == '__main__':
    unittest.main()
