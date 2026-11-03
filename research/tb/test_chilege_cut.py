"""The 2:29 edit must preserve the reviewed prefix and remove the real coda."""
import csv,json,unittest
from pathlib import Path
import numpy as np
import soundfile as sf
import mido
ROOT=Path(__file__).resolve().parents[1];REVIEW=ROOT/'songs/product_song_review'
BASE=Path(json.loads((ROOT/'build/chilege_cut_baseline.json').read_text(encoding='utf-8'))['archive'])/'songs/product_song_review'
def rows(path):
    with path.open(encoding='utf-8') as f:return list(csv.DictReader(f))
class ChilegeCut(unittest.TestCase):
    def test_exact_end_preserved_prefix_and_synchronized_outputs(self):
        before=rows(BASE/'chilege.csv');after=rows(REVIEW/'chilege.csv')
        self.assertEqual(after[:-1],before[:len(after)-1])
        a,b=after[-1],before[len(after)-1]
        self.assertEqual({k:v for k,v in a.items() if k not in ('duration_ms','source_end_s')},{k:v for k,v in b.items() if k not in ('duration_ms','source_end_s')})
        self.assertEqual(sum(int(x['duration_ms']) for x in after),149000)
        self.assertEqual(int(a['duration_ms']),2642)
        lyrics=json.loads((REVIEW/'chilege_lyrics.json').read_text(encoding='utf-8'))
        self.assertEqual(len(lyrics['words']),184);self.assertEqual(lyrics['words'][-1]['char'],'川')
        self.assertEqual(lyrics['words'][-1]['end_ms'],149000)
        self.assertNotIn('啊',''.join(p['line1']+p['line2'] for p in lyrics['phrases']))
        self.assertEqual(len(lyrics['guide_words']),len(after))
        old,sr=sf.read(BASE/'chilege_full_preview.wav');new,rate=sf.read(REVIEW/'chilege_full_preview.wav')
        self.assertEqual(rate,sr);self.assertEqual(len(new),149*sr)
        # Only the existing 18ms note release at the new endpoint may differ.
        keep=int((149-.019)*sr);np.testing.assert_array_equal(new[:keep],old[:keep])
        self.assertLess(abs(new[-1]),.001)
        self.assertAlmostEqual(mido.MidiFile(REVIEW/'chilege_review.mid').length,149.,places=3)
if __name__=='__main__':unittest.main()
