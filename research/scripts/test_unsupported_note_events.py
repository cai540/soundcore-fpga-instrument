import unittest
import numpy as np
from unsupported_note_events import cleanup
from test_register_candidate import evidence,n


class EventSupportTests(unittest.TestCase):
    def test_a_real_90ms_note_survives(self):
        e,p,c,b=evidence(np.ones(40)*74);e['word']=np.zeros(40)
        a={'flux':np.zeros(40),'rms':np.ones(40)*.1}
        notes=[n(100,90,74)];out,_=cleanup(notes,e,p,b,a);self.assertEqual(out,notes)

    def test_unvoiced_model_hallucination_is_removed(self):
        e,p,c,b=evidence(np.ones(40)*60);e['rmvpe'][:]=0;e['word']=np.zeros(40);p['confidence'][:]=0;b['note'][:]=.11
        a={'flux':np.zeros(40),'rms':np.ones(40)*.0001}
        out,audit=cleanup([n(100,180,60)],e,p,b,a)
        self.assertEqual(out,[]);self.assertEqual(len(audit['deleted']),1)

    def test_a_long_held_note_survives_one_tracker_dropout(self):
        e,p,c,b=evidence(np.ones(150)*72);e['rmvpe'][:]=0;e['word']=np.zeros(150)
        a={'flux':np.zeros(150),'rms':np.ones(150)*.1}
        notes=[n(0,1500,72)];out,_=cleanup(notes,e,p,b,a);self.assertEqual(out,notes)

    def test_repeated_words_stay_separate(self):
        e,p,c,b=evidence(np.ones(120)*72);e['word']=np.zeros(120)
        a={'flux':np.zeros(120),'rms':np.ones(120)*.1}
        notes=[n(0,400,72),n(400,400,72),n(800,400,72)]
        out,_=cleanup(notes,e,p,b,a);self.assertEqual(out,notes)

if __name__=='__main__':unittest.main(verbosity=2)
