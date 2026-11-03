"""Behavioral counterexamples; not an estimate of transcription accuracy."""
import unittest,numpy as np
from monophonic_note_lattice import build_hypotheses,decode_lattice
from transcription_event_consensus import merge_corroborated_sustain
from phonetic_event_refinement import acoustic_character_attacks
from local_lyric_alignment import characters_from_chunks
from note_probability_fusion import basic_times

def note(a,z,p):return {'start_ms':a,'duration_ms':z-a,'midi':p,'confidence':0.}
def data(ns,length=3000,attacks=()):
    t=(length+9)//10;e={'rmvpe':np.zeros(t),'word':np.zeros(t)}
    p={'midi':np.zeros(t),'confidence':np.ones(t)}
    ac={'rms':np.ones(t)*.1};bp={'note':np.zeros((round(length/11.5)+100,88),np.float32)}
    bt=basic_times(len(bp['note']))*1000
    for n in ns:
        a=n['start_ms']//10;z=(n['start_ms']+n['duration_ms'])//10
        e['rmvpe'][a:z]=440*2**((n['midi']-69)/12);p['midi'][a:z]=n['midi']
        bp['note'][(bt>=a*10)&(bt<z*10),n['midi']-21]=.8
    for a in attacks:e['word'][a//10]=1.
    return e,p,bp,ac

class IntervalLatticeTests(unittest.TestCase):
    def test_unmatched_late_subharmonic_cannot_force_a_cut(self):
        actual=[note(0,1200,72)];raw=actual+[note(420,630,60)]
        result,_=decode_lattice(raw,actual,*data(actual,attacks=[0]))
        self.assertEqual([(n['start_ms'],n['duration_ms'],n['midi']) for n in result],[(0,1200,72)])

    def test_same_pitch_phonetic_reattack_is_retained(self):
        actual=[note(0,400,60),note(400,900,60)]
        result,_=decode_lattice(actual,actual,*data(actual,attacks=[0,400]))
        self.assertEqual([n['start_ms'] for n in result],[0,400])

    def test_a_genuine_short_note_is_not_a_duration_filter(self):
        actual=[note(0,400,60),note(400,510,64),note(510,1000,67)]
        result,_=decode_lattice(actual,actual,*data(actual,attacks=[0,400,510]))
        self.assertEqual([n['midi'] for n in result],[60,64,67])

    def test_a_real_attack_can_cut_a_model_overlong_previous_note(self):
        actual=[note(0,500,60),note(500,900,62),note(900,2000,64)]
        raw=[note(0,2000,60),*actual[1:]]
        result,_=decode_lattice(raw,raw,*data(actual,attacks=[0,500,900]))
        self.assertEqual([n['midi'] for n in result],[60,62,64])

    def test_true_octave_and_chromatic_notes_survive(self):
        actual=[note(0,400,60),note(400,900,72),note(900,1500,73)]
        result,_=decode_lattice(actual,actual,*data(actual,attacks=[0,400,900]))
        self.assertEqual([n['midi'] for n in result],[60,72,73])

    def test_rest_is_not_filled(self):
        actual=[note(0,400,60),note(650,1100,60)]
        result,_=decode_lattice(actual,actual,*data(actual,attacks=[0,650]))
        self.assertEqual(result[0]['start_ms']+result[0]['duration_ms'],400)
        self.assertEqual(result[1]['start_ms'],650)

    def test_duplicate_event_matching_requires_both_endpoints(self):
        h=build_hypotheses([note(0,500,60),note(500,1000,60)],[note(0,1000,60)])
        self.assertEqual(len(h),3)

    def test_late_octave_alias_is_a_competing_pitch_not_a_new_attack(self):
        actual=[note(0,1000,72)];raw=actual+[note(80,1010,60)]
        h=build_hypotheses(raw,actual,np.zeros(300))
        self.assertEqual({n['start_ms'] for n in h},{0})

    def test_alternate_onset_jitter_does_not_add_a_note(self):
        actual=[note(0,500,60),note(500,1000,62)]
        h=build_hypotheses(actual,[note(60,520,60),note(560,1020,62)])
        self.assertEqual({n['start_ms'] for n in h},{0,500})

    def test_alternate_alone_cannot_inject_a_new_attack(self):
        h=build_hypotheses([note(0,1200,60)],[note(0,1200,60),note(400,550,72)])
        self.assertEqual({n['start_ms'] for n in h},{0})

    def test_upper_voice_attack_protects_lower_alias(self):
        ns=[note(0,400,60),note(400,900,60)]
        alt=[note(0,900,60),note(400,900,72)]
        e,_,_,ac=data(ns)
        out,a=merge_corroborated_sustain(ns,alt,e,ac)
        self.assertEqual(len(out),2)

    def test_hallucinated_long_asr_token_is_not_an_attack(self):
        ns=[note(300,800,60)];e,_,_,ac=data(ns)
        alignment={'characters':[{'start_ms':0,'end_ms':27980,'estimated_split':False}]}
        attacks,rejected=acoustic_character_attacks(alignment,ns,e,ac)
        self.assertEqual(attacks,[]);self.assertEqual(rejected[0]['reason'],'implausible_token_duration')

    def test_sentence_time_division_is_explicitly_uncertain(self):
        chars=characters_from_chunks([{'text':'天地','timestamp':[.2,1.4]}])
        self.assertTrue(all(c['estimated_split'] for c in chars))

    def test_empty_input(self):
        self.assertEqual(build_hypotheses([],[]),[])
        self.assertEqual(decode_lattice([],[],{},{},{},{})[0],[])

if __name__=='__main__':unittest.main()
