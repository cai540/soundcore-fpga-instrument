"""Structural regressions, separate from independent musical accuracy."""
import ast
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import numpy as np
from soundcore_audio.decoder import decode, interval_candidates, tonal_prior
from soundcore_audio.pitch import interval_likelihood, estimate_center
from soundcore_audio.pipeline import PhraseEvidence, RecordingEvidence, export, load_evidence, save_evidence
from soundcore_audio.types import DecodeConfig, IntervalEvidence, ModelObservation, Note


def activation(pitch=None):
    p = np.full(257, .001)
    if pitch is not None:
        p[pitch * 2] = .99
    return p


def graph(pitches, frames=40, boundary=.99):
    cuts = np.arange(len(pitches) + 1) * frames
    probability = np.full(cuts[-1], .01)
    probability[cuts[1:-1]] = boundary
    obs = ModelObservation(cuts, probability, np.array([activation(p) for p in pitches]))
    intervals = [IntervalEvidence(a, z, activation(p)) for a, z, p in zip(cuts, cuts[1:], pitches)]
    return obs, np.full(cuts[-1], .5), intervals


class DecoderTest(unittest.TestCase):
    config = DecodeConfig(phonetic_boundary_weight=0., tonality_weight=0.)

    def run_graph(self, pitches, **kwargs):
        obs, phone, intervals = graph(pitches, **kwargs)
        return decode(obs, phone, intervals, self.config, np.ones(128))[0]

    def test_real_ninety_ms_note_survives(self):
        self.assertEqual([n.midi for n in self.run_graph([60, 62, 64], frames=9)], [60, 62, 64])

    def test_same_pitch_rearticulations_survive(self):
        obs, phone, edges = graph([60, 60])
        edges.append(IntervalEvidence(0, 80, activation(60)))
        notes, _ = decode(obs, phone, edges, self.config, np.ones(128))
        self.assertEqual([n.midi for n in notes], [60, 60])

    def test_vibrato_island_can_be_one_note(self):
        obs, phone, edges = graph([60, 61, 60], boundary=.05)
        edges.append(IntervalEvidence(0, 120, activation(60)))
        notes, _ = decode(obs, phone, edges, self.config, np.ones(128))
        self.assertEqual(notes, [Note(0, 1200, 60)])

    def test_real_octave_jump_is_not_folded(self):
        self.assertEqual([n.midi for n in self.run_graph([60, 72, 60])], [60, 72, 60])

    def test_real_rest_is_not_bridged(self):
        notes = self.run_graph([60, None, 62])
        self.assertEqual([(n.start_ms, n.end_ms) for n in notes], [(0, 400), (800, 1200)])

    def test_long_native_hold_survives_many_boundary_proposals(self):
        obs, phone, _ = graph([60], frames=600, boundary=.01)
        cuts = np.arange(0, 601, 20)
        edges = interval_candidates(obs, cuts, 4)
        notes, _ = decode(obs, phone, edges, replace(self.config, duration_weight=1), np.ones(128))
        self.assertEqual(notes, [Note(0, 6000, 60)])

    def test_native_observation_not_changed_by_alternative_partitions(self):
        obs, _, _ = graph([60, 62])
        edges = interval_candidates(obs, np.array([0, 10, 20, 40, 50, 80]), 4)
        edge = next(v for v in edges if (v.start, v.end) == (0, 40))
        np.testing.assert_allclose(edge.activation, obs.pitch_activation[0], atol=1e-12)

    def test_coarse_phrase_locator_does_not_drop_early_attack(self):
        from evaluation.transcription.metrics import evaluate
        case = {'id': 'synthetic', 'source_offset_s': 0,
            'phrases': [{'source_span_s': [.01, .8], 'pitches': [60], 'text': 'fixture'}]}
        result = evaluate([Note(0, 500, 60)], case)
        self.assertEqual(result['correct'], 1)

    def test_false_release_in_annotated_vocal_breath_is_counted(self):
        from evaluation.transcription.metrics import evaluate
        case = {'id': 'fixture', 'source_offset_s': 0, 'vocal_spans_s': [[0, 3]],
            'phrases': [{'source_span_s': [.1, .8], 'pitches': [60], 'text': 'fixture'}]}
        result = evaluate([Note(100, 700, 60), Note(1200, 1300, 61), Note(5000, 5100, 62)], case)
        self.assertEqual((result['correct'], result['extra']), (1, 1))
        self.assertEqual(result['strict_note_accuracy'], 0.)

    def test_strict_accuracy_penalizes_wrong_missing_and_extra(self):
        from evaluation.transcription.metrics import summarize
        result = summarize({'correct': 97, 'wrong_pitch': 1, 'missed': 2, 'extra': 1})
        self.assertAlmostEqual(result['strict_note_accuracy'], .96)

    def test_song_gate_rejects_perfect_partial_phrases(self):
        from evaluation.transcription.metrics import song_pitch_gate
        rows = [{'id': str(i), 'recording_id': str(i), 'reference_notes': 100,
                 'strict_note_accuracy': 1., 'complete_vocal_annotation': False} for i in range(3)]
        self.assertFalse(song_pitch_gate(rows)['voice_pitch_gate_passed'])

    def test_song_gate_requires_three_distinct_complete_recordings(self):
        from evaluation.transcription.metrics import song_pitch_gate
        row = {'id': 'fixture', 'recording_id': 'one', 'reference_notes': 100,
               'strict_note_accuracy': .99, 'complete_vocal_annotation': True}
        self.assertFalse(song_pitch_gate([row, row, row])['voice_pitch_gate_passed'])
        rows = [{**row, 'recording_id': str(i), 'strict_note_accuracy': x}
                for i, x in enumerate([.99, .95, .95])]
        self.assertTrue(song_pitch_gate(rows)['voice_pitch_gate_passed'])

    def test_key_inference_is_transposition_equivariant(self):
        source = [60, 64, 67, 62, 65, 69, 71, 72]
        def observation(shift):
            pitches = np.arange(257) * .5
            curves = np.array([np.exp(-.5 * ((pitches - p - shift) / 1.3) ** 2) for p in source])
            cuts = np.arange(len(source) + 1) * 40
            return ModelObservation(cuts, np.full(cuts[-1], .5), curves)
        _, a = tonal_prior([observation(0)])
        _, b = tonal_prior([observation(3)])
        np.testing.assert_allclose(np.roll(a['class_histogram'], 3), b['class_histogram'], atol=1e-12)

    def test_uncertain_pitch_head_does_not_claim_a_certain_key(self):
        pitches = [60, 64, 67, 60, 65, 69, 62, 71]
        grid = np.arange(257) * .5
        def keys(width):
            curves = np.array([np.exp(-.5 * ((grid - p) / width) ** 2) for p in pitches])
            obs = ModelObservation(np.arange(9) * 40, np.full(320, .5), curves)
            return tonal_prior([obs])[1]['key_posterior']
        self.assertLess(max(keys(1.5)), max(keys(.5)))

    def test_pooling_pitch_disagreement_does_not_invent_silence(self):
        obs, _, _ = graph([60, 72])
        edge = next(v for v in interval_candidates(obs, obs.cuts, 4) if (v.start, v.end) == (0, 80))
        self.assertGreater(edge.voiced_probability, .98)
        self.assertLess(edge.activation.max(), .1)

    def test_real_unvoiced_region_retains_low_presence(self):
        obs, _, _ = graph([None, None])
        edge = next(v for v in interval_candidates(obs, obs.cuts, 4) if (v.start, v.end) == (0, 80))
        self.assertLess(edge.voiced_probability, .01)

    def test_transpose_equivariance(self):
        low = self.run_graph([48, 51, 49])
        high = self.run_graph([60, 63, 61])
        self.assertEqual([n.midi + 12 for n in low], [n.midi for n in high])

    def test_strong_chromatic_note_beats_soft_key(self):
        obs, phone, edges = graph([61])
        prior = np.ones(128)
        prior[61] = .1
        notes, _ = decode(obs, phone, edges, replace(self.config, tonality_weight=1), prior)
        self.assertEqual(notes[0].midi, 61)

    def test_periodic_f0_resolves_class_inside_objective(self):
        obs, phone, _ = graph([60])
        p = activation(60)
        p[61 * 2] = .75
        pitch = 61 + .7 * np.sin(2 * np.pi * 6 * np.arange(40) * .01)
        f0 = 440 * 2 ** ((pitch - 69) / 12)
        edge = IntervalEvidence(0, 40, p, interval_likelihood(f0, np.ones(40), 0, 40))
        notes, _ = decode(obs, phone, [edge], replace(self.config, acoustic_pitch_weight=2), np.ones(128))
        self.assertEqual(notes[0].midi, 61)

    def test_acoustic_octave_alias_does_not_change_register(self):
        pitch = 64 + .7 * np.sin(2 * np.pi * 6 * np.arange(40) * .01)
        likelihood = interval_likelihood(440 * 2 ** ((pitch - 69) / 12), np.ones(40), 0, 40)
        self.assertEqual(likelihood[64], likelihood[76])

    def test_incomplete_graph_rejected(self):
        obs, phone, edges = graph([60, 62])
        with self.assertRaises(ValueError):
            decode(obs, phone, edges[:1], self.config)

    def test_configured_missing_observation_rejected(self):
        obs, phone, edges = graph([60])
        with self.assertRaises(ValueError):
            decode(obs, phone, edges, replace(self.config, acoustic_pitch_weight=1))

    def test_observation_cannot_be_changed_by_decoder(self):
        obs, phone, edges = graph([60])
        before = obs.pitch_activation.copy()
        decode(obs, phone, edges, self.config)
        np.testing.assert_array_equal(obs.pitch_activation, before)
        with self.assertRaises(ValueError):
            obs.pitch_activation[0, 0] = 1

    def test_invalid_observation_rejected(self):
        with self.assertRaises(ValueError):
            ModelObservation(np.array([0, 0, 1]), np.ones(1), np.ones((2, 257)))
        with self.assertRaises(ValueError):
            DecodeConfig(max_boundary_span=1.5)
        with self.assertRaises(ValueError):
            Note(0, 200, 60.5)

    def test_archive_roundtrip(self):
        obs, phone, edges = graph([60, 62])
        source = RecordingEvidence(800, 'example', (PhraseEvidence(0, obs, phone, tuple(edges)),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.npz'
            save_evidence(source, path)
            loaded = load_evidence(path)
        np.testing.assert_array_equal(loaded.phrases[0].observation.pitch_activation, obs.pitch_activation)
        self.assertEqual(loaded.phrases[0].intervals[0].voiced_probability, edges[0].voiced_probability)
        self.assertEqual(loaded.source_sha256, source.source_sha256)

    def test_incompatible_observations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.npz'
            np.savez(path, policy='old-correction-pipeline')
            with self.assertRaisesRegex(ValueError, 'Incompatible'):
                load_evidence(path)

    def test_mismatched_archive_does_not_silently_drop_intervals(self):
        obs, phone, edges = graph([60, 62])
        source = RecordingEvidence(800, 'example', (PhraseEvidence(0, obs, phone, tuple(edges)),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.npz'
            save_evidence(source, path)
            with np.load(path, allow_pickle=False) as archive:
                arrays = {name: archive[name] for name in archive.files}
            arrays['0_interval_voiced'] = arrays['0_interval_voiced'][:-1]
            np.savez(path, **arrays)
            with self.assertRaisesRegex(ValueError, 'lengths or shapes'):
                load_evidence(path)

    def test_mixed_acoustic_availability_is_not_silently_lost(self):
        obs, phone, edges = graph([60, 62])
        values = list(edges)
        values[0] = replace(values[0], f0_likelihood=np.ones(128))
        source = RecordingEvidence(800, 'example', (PhraseEvidence(0, obs, phone, tuple(values)),))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'consistently'):
                save_evidence(source, Path(directory) / 'evidence.npz')

    def test_midi_retains_real_silence_and_clock(self):
        import mido
        notes = [Note(130, 280, 60), Note(1920, 2010, 62)]
        with tempfile.TemporaryDirectory() as directory:
            export(notes, directory)
            clock = 0.
            attacks = []
            for message in mido.MidiFile(Path(directory) / 'source_clock.mid'):
                clock += message.time
                if message.type == 'note_on':
                    attacks.append(round(clock * 1000))
        self.assertEqual(attacks, [130, 1920])

    def test_runtime_cannot_import_research_or_references(self):
        for path in Path('soundcore_audio').glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(any(x in (node.module or '').split('.') for x in ['evaluation', 'scripts', 'build', 'songs']))
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.assertFalse(name.name.split('.')[0] in {'evaluation', 'scripts', 'build', 'songs'})

    def test_old_periodic_measurement_not_output_merger(self):
        t = np.arange(100) * .01
        pitch = 70 + 1.4 * np.sin(2 * np.pi * 6 * t + .3)
        fit = estimate_center(t, pitch)
        self.assertTrue(fit['vibrato'])
        self.assertAlmostEqual(fit['center'], 70, places=4)


if __name__ == '__main__':
    unittest.main()
