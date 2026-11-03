"""Musically relevant invariants, independent of song names and references."""
import unittest
import numpy as np
from syllable_vocal_decoder import decode_syllables,acoustic_features,PITCHES

def note(start,dur,p):return {'start_ms':start,'duration_ms':dur,'midi':p,'confidence':0.0}

def case(pitches,word_at=(),rms=None):
    p=np.asarray(pitches,float);T=len(p)
    voiced=p>0;hz=np.where(voiced,440*2**((p-69)/12),0)
    evidence={'rmvpe':hz,'fcpe':hz,'fcpe_confidence':voiced.astype(float)*.95,'word':np.zeros(T)}
    flux=np.zeros(T)
    for k in word_at:evidence['word'][k]=.999;flux[k]=.35
    features={'rms':np.ones(T)*.1 if rms is None else rms,'flux':flux,
              'harmonic':np.zeros((T,len(PITCHES))),'octave_penalty':np.zeros((T,len(PITCHES)))}
    return np.ones(T*160,dtype=np.float32)*.1,evidence,features

class SyllableTests(unittest.TestCase):
    def test_one_sustained_vowel_vibrato_does_not_become_fast_notes(self):
        T=200;p=72+.75*np.sin(np.arange(T)*.01*2*np.pi*5)
        pcm,e,f=case(p)
        fragmented=[note(k*100,100,72+[0,1,0,-1][k%4]) for k in range(20)]
        ns,a=decode_syllables(pcm,e,fragmented,f)
        self.assertEqual(len(ns),1);self.assertEqual(ns[0]['midi'],72);self.assertEqual(ns[0]['duration_ms'],2000)

    def test_repeated_words_same_pitch_keep_separate_attacks(self):
        pcm,e,f=case(np.ones(120)*69,[40,80])
        ns,_=decode_syllables(pcm,e,[note(0,1200,69)],f)
        self.assertEqual([(n['start_ms'],n['duration_ms']) for n in ns],[(0,400),(400,400),(800,400)])

    def test_real_140ms_syllables_are_not_removed_by_smoothing(self):
        pcm,e,f=case(np.r_[np.ones(14)*69,np.ones(14)*71,np.ones(14)*72],[14,28])
        ns,_=decode_syllables(pcm,e,[note(0,140,69),note(140,140,71),note(280,140,72)],f)
        self.assertEqual([n['midi'] for n in ns],[69,71,72]);self.assertEqual(sum(n['duration_ms'] for n in ns),420)

    def test_real_40ms_rest_stays_a_rest(self):
        pcm,e,f=case(np.r_[np.ones(50)*69,np.zeros(4),np.ones(50)*69])
        ns,_=decode_syllables(pcm,e,[note(0,500,69),note(540,500,69)],f)
        self.assertEqual([(n['start_ms'],n['duration_ms']) for n in ns],[(0,500),(540,500)])

    def test_tracker_dropout_over_audible_held_note_is_not_a_new_attack(self):
        pcm,e,f=case(np.r_[np.ones(45)*69,np.zeros(8),np.ones(47)*69])
        ns,_=decode_syllables(pcm,e,[note(0,1000,69)],f)
        self.assertEqual(len(ns),1);self.assertEqual(ns[0]['duration_ms'],1000)

    def test_pitch_jump_of_real_octave_is_allowed(self):
        pcm,e,f=case(np.r_[np.ones(60)*60,np.ones(60)*72],[60])
        ns,_=decode_syllables(pcm,e,[note(0,600,60),note(600,600,72)],f)
        self.assertEqual([n['midi'] for n in ns],[60,72])

    def test_rare_clear_chromatic_note_is_not_forced_into_common_pitch_class(self):
        pcm,e,f=case(np.r_[np.ones(400)*69,np.ones(20)*70,np.ones(60)*69],[400,420])
        ns,_=decode_syllables(pcm,e,[note(0,4000,69),note(4000,200,70),note(4200,600,69)],f)
        self.assertEqual([n['midi'] for n in ns],[69,70,69])

    def test_unvoiced_audio_cannot_become_low_ghost_note(self):
        pcm,e,f=case(np.zeros(120))
        ns,_=decode_syllables(pcm,e,[note(0,1200,42)],f)
        self.assertEqual(ns,[])

    def test_constant_transposition_does_not_change_boundaries(self):
        p=np.r_[np.ones(40)*65,np.ones(40)*67,np.ones(40)*69]
        outputs=[]
        for delta in [0,3]:
            pcm,e,f=case(p+delta,[40,80])
            ns,_=decode_syllables(pcm,e,[note(i*400,400,int(p[i*40]+delta)) for i in range(3)],f)
            outputs.append(ns)
        self.assertEqual([(n['start_ms'],n['duration_ms']) for n in outputs[0]],[(n['start_ms'],n['duration_ms']) for n in outputs[1]])
        self.assertTrue(all(b['midi']-a['midi']==3 for a,b in zip(*outputs)))

    def test_harmonic_evidence_penalizes_missing_odd_subharmonic(self):
        sr=16000;t=np.arange(sr)/sr
        # A real 523Hz fundamental has no 261Hz odd partials. Lowering its
        # detected octave needs a penalty; this is a physical waveform test.
        pcm=(.3*np.sin(2*np.pi*523.251*t)).astype(np.float32)
        f=acoustic_features(pcm);wrong=np.where(PITCHES==60)[0][0];right=np.where(PITCHES==72)[0][0]
        self.assertGreater(np.median(f['octave_penalty'][10:-10,wrong]),2.)
        self.assertLess(np.median(f['octave_penalty'][10:-10,right]),.1)

if __name__=='__main__':unittest.main(verbosity=2)
