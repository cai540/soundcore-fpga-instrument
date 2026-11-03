import unittest
import numpy as np
from vocalparse_time_alignment import align_units,main_units

def evidence(pitches,word_at=()):
    pitches=np.asarray(pitches,float);voiced=pitches>0
    hz=np.where(voiced,440*2**((pitches-69)/12),0)
    word=np.zeros(len(pitches));word[list(word_at)]=.99
    # Square amplitude only supplies energy; the pitch observations here are
    # analytic test inputs, not evidence of model transcription accuracy.
    pcm=np.repeat(voiced.astype(float)*.1,160).astype(np.float32)
    return pcm,{'rmvpe':hz,'word':word},{'midi':pitches,'confidence':voiced.astype(float)}

def parsed(ps,notes=None):
    return {'words':['字']*len(ps),'pitches':ps,'notes':notes or ['<NOTE_4>']*len(ps),'bpm':120}

class AlignmentBehavior(unittest.TestCase):
    def test_phrase_rest_remains_and_source_clock_is_preserved(self):
        p=np.r_[np.zeros(20),np.ones(50)*69,np.zeros(30),np.ones(50)*72,np.zeros(10)]
        x,e,v=evidence(p,[20,100]);ns,a=align_units(x,parsed([69,72]),e,v)
        self.assertTrue(a['accepted']);self.assertEqual([n['midi'] for n in ns],[69,72])
        self.assertLess(abs(ns[0]['start_ms']-200),80)
        self.assertGreater(ns[1]['start_ms']-ns[0]['start_ms']-ns[0]['duration_ms'],180)

    def test_two_equal_pitch_syllables_are_not_merged(self):
        p=np.ones(100)*69;x,e,v=evidence(p,[0,50]);ns,a=align_units(x,parsed([69,69]),e,v)
        self.assertEqual(len(ns),2);self.assertTrue(a['accepted'])
        self.assertLess(abs(ns[1]['start_ms']-500),100)

    def test_true_octave_and_period_error_do_not_edit_model_pitch(self):
        p=np.r_[np.ones(50)*60,np.ones(50)*60];x,e,v=evidence(p,[0,50])
        ns,a=align_units(x,parsed([60,72]),e,v)
        self.assertEqual([n['midi'] for n in ns],[60,72]);self.assertTrue(a['accepted'])

    def test_silent_audio_rejects_a_hallucinated_score(self):
        x,e,v=evidence(np.zeros(100));ns,a=align_units(x,parsed([69,71]),e,v)
        self.assertFalse(a['accepted'])

    def test_duration_does_not_extend_past_recording(self):
        x,e,v=evidence(np.r_[np.ones(45)*69,np.ones(30)*70]);ns,a=align_units(x,parsed([69,70]),e,v)
        self.assertEqual(len(ns),2);self.assertTrue(all(n['duration_ms']>0 for n in ns))
        self.assertLessEqual(ns[-1]['start_ms']+ns[-1]['duration_ms'],750)
        self.assertLessEqual(ns[0]['start_ms']+ns[0]['duration_ms'],ns[1]['start_ms'])

    def test_main_note_groups_only_continuations_not_repeated_words(self):
        p={'words':['字','·','字'],'pitches':[69,70,69],
           'notes':['<NOTE_2>','<NOTE_8>','<NOTE_4>'],'bpm':90}
        u=main_units(p);self.assertEqual(len(u),2);self.assertEqual([n['midi'] for n in u],[69,69])
        self.assertEqual(u[0]['beats'],2.5)

if __name__=='__main__':unittest.main(verbosity=2)
