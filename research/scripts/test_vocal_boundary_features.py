import unittest
import numpy as np
from vocal_boundary_features import analyze
from syllable_vocal_decoder import acoustic_features


class BoundaryGridTests(unittest.TestCase):
    def test_fractional_millisecond_tail_matches_existing_source_grid(self):
        for tail in [1, 7, 15, 16, 159, 160, 161]:
            size = 32000 + tail
            pcm = (np.sin(np.arange(size) * 2 * np.pi * 440 / 16000) * .1).astype(np.float32)
            rms = acoustic_features(pcm)['rms']
            result = analyze(pcm, rms)
            self.assertEqual(len(result['novelty']), len(rms))
            self.assertTrue(np.isfinite(result['novelty']).all())

    def test_a_different_rate_or_shifted_feature_length_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze(np.zeros(32000, np.float32), np.zeros(190))
        with self.assertRaises(ValueError):
            analyze(np.zeros(32000, np.float32), np.full(200, np.nan))

    def test_silence_is_not_a_phonetic_boundary(self):
        result = analyze(np.zeros(32000, np.float32))
        self.assertTrue(np.all(result['novelty'] == 0))
        self.assertEqual(len(result['candidates']), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
