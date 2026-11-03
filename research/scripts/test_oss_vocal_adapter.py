"""Behavioral checks on source clocks and measured-pitch arbitration.
These tests cannot certify musical transcription quality.
"""
import unittest,numpy as np
from game_vocal_engine import context_cuts,core_stitch
from oss_vocal_postprocess import central_pitch,f0_grid
from transcribe_vocal_oss import device_fit

def n(s,d,m):return {'start_ms':s,'duration_ms':d,'midi':m,'confidence':0.0}

class AdapterTests(unittest.TestCase):
    def test_context_never_discards_long_silence(self):
        pcm=np.zeros(16000*57,dtype=np.float32);pcm[5*16000:7*16000]=.2
        cuts=context_cuts(pcm)
        self.assertEqual((cuts[0],cuts[-1]),(0,57000))
        self.assertTrue(all(a<z for a,z in zip(cuts,cuts[1:])))
        self.assertEqual(sum(z-a for a,z in zip(cuts,cuts[1:])),57000)

    def test_hard_cut_still_has_exact_clock(self):
        cuts=context_cuts(np.ones(16000*61,dtype=np.float32)*.2)
        self.assertEqual(cuts,[0,18000,36000,54000,61000])

    def test_join_only_two_clipped_halves(self):
        a=core_stitch([], [n(17800,400,72)],0,0,18000)
        b=core_stitch(a,[n(0,600,72)],17800,18000,20000)
        self.assertEqual([(q['start_ms'],q['duration_ms']) for q in b],[(17800,600)])

    def test_keep_real_same_pitch_reattack(self):
        a=core_stitch([], [n(17800,200,72)],0,0,18000)
        b=core_stitch(a,[n(200,300,72)],17800,18000,20000)
        self.assertEqual(len(b),2)

    def test_same_pitch_never_fills_rest(self):
        a=core_stitch([], [n(17800,200,72)],0,0,18000)
        b=core_stitch(a,[n(0,250,0),n(250,300,72)],17800,18000,20000)
        self.assertEqual([q['midi'] for q in b],[72,0,72])

    def test_short_real_note_not_removed(self):
        ns=[n(100,140,72),n(240,180,74)]
        f=np.zeros(50);f[10:24]=523.251;f[24:42]=587.33
        out,_=central_pitch(ns,f)
        self.assertEqual([(x['start_ms'],x['duration_ms'],x['midi']) for x in out],[(100,140,72),(240,180,74)])

    def test_center_does_not_move_time_or_erase_repeats(self):
        ns=[n(100,400,71),n(500,400,71)]
        f=np.ones(100)*523.251
        out,_=central_pitch(ns,f)
        self.assertEqual([(x['start_ms'],x['duration_ms'],x['midi']) for x in out],[(100,400,72),(500,400,72)])

    def test_missing_f0_not_fabricated(self):
        ns=[n(100,500,72)]
        self.assertEqual(central_pitch(ns,np.zeros(100))[0],ns)

    def test_glissando_ambiguous_center_not_overwritten(self):
        ns=[n(100,800,72)];f=440*2**((np.linspace(69,77,100)-69)/12)
        self.assertEqual(central_pitch(ns,f)[0],ns)

    def test_context_f0_uses_core_not_stale_overlap(self):
        trace={'chunks':[{'begin_ms':0,'core_start_ms':0,'core_end_ms':100,'f0':[440]*20},
                         {'begin_ms':50,'core_start_ms':100,'core_end_ms':200,'f0':[880]*20}]}
        out=f0_grid(trace,200)
        np.testing.assert_array_equal(out[:10],440);np.testing.assert_array_equal(out[10:],880)

    def test_pitch_policy_transposition_equivariance(self):
        f=np.ones(100)*523.251;ns=[n(100,600,71)]
        original=central_pitch(ns,f)[0][0]
        shifted=central_pitch([{**q,'midi':q['midi']+3} for q in ns],f*2**(3/12))[0][0]
        self.assertEqual(shifted['midi']-original['midi'],3)

    def test_all35_chromatic_pitches_map_without_loss(self):
        ns=[n(i*100,100,60+i) for i in range(35)]
        fit=device_fit(ns,3500);self.assertTrue(fit['eligible'])
        self.assertEqual([(q['bank_zero_based'],q['pad_zero_based']) for q in fit['notes']],[(i//7,i%7) for i in range(35)])

    def test_out_of_span_does_not_silently_clamp_or_delete(self):
        ns=[n(0,200,40),n(200,200,90)]
        self.assertFalse(device_fit(ns,400)['eligible']);self.assertEqual([q['midi'] for q in ns],[40,90])

    def test_full_song_not_mislabeled_as_current_uploadable(self):
        self.assertFalse(device_fit([n(0,1000,72)],60000)['eligible'])

if __name__=='__main__':unittest.main(verbosity=2)
