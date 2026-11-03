import unittest
from evaluate_pitch_notes import evaluate

def n(a,d,p):return {'start_ms':a,'duration_ms':d,'midi':p}

class EventMetricBehavior(unittest.TestCase):
    def test_octave_error_is_not_counted_correct(self):
        r=evaluate([n(0,500,60)],[n(0,500,72)])
        self.assertEqual(r['correct_pitch_and_octave_notes'],0)
        self.assertEqual(r['correct_pitch_class_notes'],1)
        self.assertEqual(r['octave_error_notes'],1)

    def test_missing_and_extra_notes_lower_different_denominators(self):
        r=evaluate([n(0,500,60),n(1000,500,62)],
                   [n(0,500,60),n(2000,200,64),n(2300,200,65)])
        self.assertEqual(r['missed_notes'],1);self.assertEqual(r['extra_notes'],2)
        self.assertEqual(r['exact_recall_including_missed_notes'],.5)
        self.assertAlmostEqual(r['exact_precision_including_extra_notes'],1/3)

    def test_swapped_pitches_do_not_get_reordered_to_make_a_pass(self):
        ref=[n(0,500,60),n(500,500,62)]
        r=evaluate(ref,[n(0,500,62),n(500,500,60)])
        self.assertEqual(r['matched_by_time'],2)
        self.assertEqual(r['correct_pitch_and_octave_notes'],0)

    def test_fragmenting_one_true_note_cannot_inflate_correct_count(self):
        ref=[n(0,1000,60)];pred=[n(k*100,100,60) for k in range(10)]
        r=evaluate(ref,pred);self.assertEqual(r['correct_pitch_and_octave_notes'],1)
        self.assertEqual(r['extra_notes'],9)
        self.assertEqual(r['exact_precision_including_extra_notes'],.1)

if __name__=='__main__':unittest.main(verbosity=2)
