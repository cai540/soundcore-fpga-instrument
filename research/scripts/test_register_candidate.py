"""Musical invariants; these tests do not assert real-song accuracy."""
import unittest
import numpy as np
from context_register_decoder import refine_context_register
from sustained_note_components import recover_components
from recording_motif_consensus import refine_repeats
from note_probability_fusion import basic_times


def n(s,d,p):return {'start_ms':s,'duration_ms':d,'midi':p,'confidence':0.}


def evidence(pitches):
    p=np.asarray(pitches,float);T=len(p);f=440*2**((p-69)/12)
    e={'rmvpe':f};pe={'midi':p,'confidence':np.ones(T)}
    cr={'f0':f,'argmax_f0':f,'periodicity':np.ones(T)}
    times=basic_times(int(T*.01/.0115)+20);bp=np.ones((len(times),88))*.03
    for i,t in enumerate(times):
        k=min(T-1,max(0,round(t*100)));pitch=int(np.floor(p[k]+.5))
        if 21<=pitch<=108:bp[i,pitch-21]=.85
    return e,pe,cr,{'note':bp}


class RegisterBehavior(unittest.TestCase):
    def test_supported_wrong_octave_recovered_without_midpoint(self):
        ns=[n(0,500,72),n(500,500,60),n(1000,500,72)]
        e,p,c,b=evidence(np.ones(150)*72);views=[np.ones(3)*72 for _ in range(3)]
        out,_=refine_context_register(ns,views,e,p,c,b,{'enabled':False})
        self.assertEqual([q['midi'] for q in out],[72,72,72])
        self.assertEqual([(q['start_ms'],q['duration_ms']) for q in out],[(0,500),(500,500),(1000,500)])

    def test_real_up_and_down_octaves_survive(self):
        ns=[n(0,500,60),n(500,500,72),n(1000,500,60)]
        e,p,c,b=evidence(np.r_[np.ones(50)*60,np.ones(50)*72,np.ones(50)*60])
        out,_=refine_context_register(ns,[np.array([60,72,60])]*3,e,p,c,b,{'enabled':False})
        self.assertEqual(out,ns)

    def test_constant_vibrato_does_not_create_a_run_of_attacks(self):
        raw=72+1.15*np.sin(np.arange(200)*.01*2*np.pi*5.5)
        e,p,c,b=evidence(raw);ns=[n(0,2000,72)]
        out,_=recover_components(ns,[np.array([72.])]*3,e,p,b,{'enabled':False})
        self.assertEqual(out,ns)

    def test_real_sustained_melodic_components_are_recovered(self):
        e,p,c,b=evidence(np.repeat([72,74,72,69],35));ns=[n(0,1400,72)]
        out,_=recover_components(ns,[np.array([72.])]*3,e,p,b,{'enabled':False})
        self.assertEqual([q['midi'] for q in out],[72,74,72,69])
        self.assertEqual(sum(q['duration_ms'] for q in out),1400)

    def test_supported_stable_chromatic_is_not_forced_into_scale(self):
        e,p,c,b=evidence(np.repeat([72,73,75],40));ns=[n(0,1200,72)]
        out,_=recover_components(ns,[np.array([72.])]*3,e,p,b,{'enabled':True,'pitch_classes':[0,2,4,5,7,9,11]})
        self.assertEqual([q['midi'] for q in out],[72,73,75])

    def test_same_pitch_words_and_short_notes_remain_separate(self):
        ns=[n(0,400,72),n(400,140,72),n(580,90,74)]
        e,p,c,b=evidence(np.r_[np.ones(58)*72,np.ones(9)*74])
        out,_=recover_components(ns,[np.array([72,72,74])]*3,e,p,b,{'enabled':False})
        self.assertEqual(out,ns)

    def test_empty_recognition_does_not_invent_notes(self):
        e,p,c,b=evidence(np.ones(20)*60)
        out,_=refine_context_register([],[],e,p,c,b,{'enabled':False});self.assertEqual(out,[])
        out,_=recover_components([],[],e,p,b,{'enabled':False});self.assertEqual(out,[])
        out,_=refine_repeats([],b,c);self.assertEqual(out,[])

    def test_transposition_keeps_component_times(self):
        outputs=[]
        for shift in [0,3,7]:
            e,p,c,b=evidence(np.repeat(np.array([65,69,67])+shift,40))
            out,_=recover_components([n(0,1200,65+shift)],[np.array([65+shift])]*3,e,p,b,{'enabled':False})
            outputs.append(out)
        for delta,out in zip([0,3,7],outputs):
            self.assertEqual([q['midi'] for q in out],[65+delta,69+delta,67+delta])
            self.assertEqual([(q['start_ms'],q['duration_ms']) for q in out],[(q['start_ms'],q['duration_ms']) for q in outputs[0]])

if __name__=='__main__':unittest.main(verbosity=2)
