import unittest,numpy as np
from periodic_vowel_events import collapse_periodic_vowels

def n(a,z,p):return {'start_ms':a,'duration_ms':z-a,'midi':p,'confidence':0.}
def waveform(pitches,attacks=()):
    x=np.asarray(pitches,float);word=np.zeros(len(x))
    for a in attacks:word[a//10]=1.
    return {'rmvpe':440*2**((x-69)/12),'word':word},{'midi':x,'confidence':np.ones(len(x))}

class PeriodicVowelTests(unittest.TestCase):
    def test_two_periodic_tracks_can_explain_an_a_b_a_fragment(self):
        notes=[n(0,200,69),n(200,400,70),n(400,800,69)]
        t=np.arange(100)*.01;e,p=waveform(69+.9*np.sin(2*np.pi*6*t))
        out,a=collapse_periodic_vowels(notes,e,p)
        self.assertEqual(len(out),1);self.assertEqual(out[0]['midi'],69)
        self.assertEqual(a['events_removed'],2)

    def test_real_stepped_short_notes_are_not_vibrato(self):
        notes=[n(0,200,69),n(200,400,70),n(400,800,69)]
        e,p=waveform(np.r_[np.full(20,69),np.full(20,70),np.full(60,69)])
        self.assertEqual(len(collapse_periodic_vowels(notes,e,p)[0]),3)

    def test_distinct_words_are_protected_even_with_vibrato(self):
        notes=[n(0,200,69),n(200,400,70),n(400,800,69)]
        t=np.arange(100)*.01;e,p=waveform(69+.9*np.sin(2*np.pi*6*t),[200,400])
        self.assertEqual(len(collapse_periodic_vowels(notes,e,p)[0]),3)

    def test_a_rest_is_never_bridged(self):
        notes=[n(0,200,69),n(240,400,70),n(400,800,69)]
        t=np.arange(100)*.01;e,p=waveform(69+.9*np.sin(2*np.pi*6*t))
        self.assertEqual(len(collapse_periodic_vowels(notes,e,p)[0]),3)

    def test_two_fragments_need_actual_periodic_evidence(self):
        t=np.arange(100)*.01;e,p=waveform(69+.9*np.sin(2*np.pi*6*t))
        notes=[n(0,500,69),n(500,800,70)]
        out,_=collapse_periodic_vowels(notes,e,p,minimum_fragments=2)
        self.assertEqual([q['midi'] for q in out],[69])
        e,p=waveform(np.r_[np.full(50,69),np.full(50,70)])
        self.assertEqual(collapse_periodic_vowels(notes,e,p,minimum_fragments=2)[0],notes)

    def test_two_distinct_articulated_notes_survive_periodic_f0(self):
        t=np.arange(100)*.01;e,p=waveform(69+.9*np.sin(2*np.pi*6*t),[500])
        notes=[n(0,500,69),n(500,800,70)]
        self.assertEqual(collapse_periodic_vowels(notes,e,p,minimum_fragments=2)[0],notes)

if __name__=='__main__':unittest.main()
