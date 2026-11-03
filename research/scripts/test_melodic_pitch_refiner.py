"""Behavior checks for pitch changes; these do not assert listening quality."""
import unittest
import numpy as np
from melodic_pitch_refiner import refine

def n(a,d,p):return {'start_ms':a,'duration_ms':d,'midi':p,'confidence':0.}
def run(notes,raw,pesto=None,melody=None,conf=None):
    p=np.asarray(raw,float);q=p if pesto is None else np.asarray(pesto,float)
    m=p if melody is None else np.asarray(melody,float)
    c=np.where(q>0,1.,0.) if conf is None else np.asarray(conf,float)
    f=lambda x:np.where(x>0,440*2**((x-69)/12),0.)
    phase=np.cumsum(np.repeat(f(p),160))*2*np.pi/16000
    pcm=(np.sin(phase)*.1).astype(np.float32)
    return refine(notes,pcm,f(p),q,c,f(m))

class PitchBehavior(unittest.TestCase):
    def test_corrobated_wrong_octave_changes_only_pitch(self):
        ns=[n(0,1000,60)];out,_=run(ns,np.ones(100)*72)
        self.assertEqual(out,[n(0,1000,72)])

    def test_genuine_upward_and_downward_octaves_survive(self):
        p=np.r_[np.ones(50)*60,np.ones(50)*72,np.ones(50)*60]
        ns=[n(0,500,60),n(500,500,72),n(1000,500,60)]
        out,_=run(ns,p);self.assertEqual(out,ns)

    def test_one_weak_short_melody_hint_does_not_change_register(self):
        p=np.ones(100)*60;m=np.zeros(100);m[40:49]=72
        ns=[n(0,1000,60)];out,_=run(ns,p,melody=m)
        self.assertEqual(out,ns)

    def test_periodic_vibrato_center_is_independent_of_starting_phase(self):
        for phase in [0,.8,1.7,3.1]:
            p=70+1.3*np.sin(np.arange(150)*.01*2*np.pi*6+phase)
            out,_=run([n(0,1500,71)],p)
            self.assertEqual(out[0]['midi'],70)

    def test_stable_rare_chromatic_note_is_preserved(self):
        ns=[n(k*400,400,69) for k in range(16)]+[n(6400,300,70)]
        p=np.r_[np.ones(640)*69,np.ones(30)*70]
        out,_=run(ns,p);self.assertEqual(out,ns)

    def test_partial_vowel_center_does_not_invent_unanchored_chromatic(self):
        ns=[n(k*400,400,62) for k in range(16)]+[n(6400,500,62)]
        p=np.r_[np.ones(640)*62,62.95+1.1*np.sin(np.arange(50)*.01*2*np.pi*5.5)]
        out,_=run(ns,p);self.assertEqual(out,ns)

    def test_silence_produces_no_new_pitch_evidence(self):
        ns=[n(100,300,69)];out,_=run(ns,np.zeros(100))
        self.assertEqual(out,ns)
        empty,_=run([],np.zeros(100));self.assertEqual(empty,[])

    def test_real_short_note_and_rest_remain_exact(self):
        ns=[n(20,140,72),n(200,90,73),n(330,400,75)]
        p=np.zeros(80);p[2:16]=72;p[20:29]=73;p[33:73]=75
        out,_=run(ns,p);self.assertEqual(out,ns)

    def test_constant_transposition_does_not_change_correction_or_timing(self):
        t=np.arange(120)*.01
        outputs=[]
        for delta in [0,3,7]:
            p=70+delta+1.25*np.sin(2*np.pi*6*t)
            out,_=run([n(0,1200,71+delta)],p);outputs.append(out[0])
        self.assertEqual([o['midi'] for o in outputs],[70,73,77])
        self.assertTrue(all(o['start_ms']==0 and o['duration_ms']==1200 for o in outputs))

if __name__=='__main__':unittest.main(verbosity=2)
