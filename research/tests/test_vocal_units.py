from dataclasses import replace
import unittest
import numpy as np
from soundcore_audio.vocal_units import VocalUnitConfig,source_scale_prior,pool_native_units,decode_vocal_units


def activation(keys):
    a=np.full((len(keys),128),.001)
    for i,key in enumerate(keys):a[i,key]=.99
    return a


class VocalUnitTests(unittest.TestCase):
    def test_time_weighted_native_pool_including_partial_edges(self):
        native=np.zeros((2,257));native[0,120]=.9;native[1,124]=.8
        pooled=pool_native_units(np.array([0,10,30]),native,np.array([[5,20],[20,30]]))
        np.testing.assert_allclose(pooled[:,60],[.3,0])
        np.testing.assert_allclose(pooled[:,62],[.8*2/3,.8])
        np.testing.assert_array_equal(native[0,120],.9)

    def test_timing_same_pitch_attacks_and_octave_leap_are_preserved(self):
        spans=np.array([[0,8],[8,20],[50,150]])
        notes,_=decode_vocal_units(spans,150,activation([60,60,84]),np.ones((3,128)),np.full((3,2),np.nan))
        self.assertEqual([(n.start_ms,n.end_ms,n.midi) for n in notes],[(0,80,60),(80,200,60),(500,1500,84)])

    def test_weak_or_conflicting_pitch_class_evidence_stays_neutral(self):
        prior,info=source_scale_prior([[60,72],[64,76],[67,79],[np.nan,np.nan]])
        np.testing.assert_array_equal(prior,np.ones(128))
        self.assertTrue(info['insufficient_consensus'])
        prior,_=source_scale_prior([[60,61]]*6)
        np.testing.assert_array_equal(prior,np.ones(128))

    def test_soft_scale_cannot_ban_a_real_chromatic_note(self):
        pairs=np.array([[p,p+12] for p in [60,62,64,65,67,69,71]])
        prior,info=source_scale_prior(pairs)
        self.assertTrue(np.all(prior>=.1))
        self.assertAlmostEqual(sum(info['posterior']),1.)
        spans=np.array([[i*20,(i+1)*20] for i in range(7)])
        notes,_=decode_vocal_units(spans,140,activation([61]*7),np.ones((7,128)),pairs)
        self.assertEqual([n.midi for n in notes],[61]*7)

    def test_invalid_source_ownership_and_unavailable_center_values_rejected(self):
        for spans in (np.array([[1,1]]),np.array([[0.,10.]]),np.array([[0,10],[9,20]]),np.array([[0,21]])):
            with self.assertRaises(ValueError):
                decode_vocal_units(spans,20,activation([60]*len(spans)),np.ones((len(spans),128)),np.full((len(spans),2),np.nan))
        for centers in ([[60,np.inf]],[[0,60]],[[60]]):
            with self.assertRaises(ValueError):source_scale_prior(centers)
        with self.assertRaises(ValueError):VocalUnitConfig(acoustic_pitch_weight=-1)

    def test_decode_does_not_modify_acoustic_evidence(self):
        raw=activation([60,62]);before=raw.copy()
        decode_vocal_units(np.array([[0,20],[20,40]]),40,raw,np.ones((2,128)),np.full((2,2),np.nan))
        np.testing.assert_array_equal(raw,before)

    def test_a_hallucinated_word_over_silence_does_not_become_a_default_tone(self):
        with self.assertRaisesRegex(ValueError,'no pitched acoustic support'):
            decode_vocal_units(np.array([[0,20]]),20,np.zeros((1,128)),
                np.ones((1,128)),np.full((1,2),np.nan))

if __name__=='__main__':unittest.main()
