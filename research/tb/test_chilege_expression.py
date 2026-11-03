"""Listening-request contracts across repeated phrases, independent of the editor."""
import csv,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REVIEW=ROOT/'songs/product_song_review'
BASE=Path(json.loads((ROOT/'build/chilege_expression_baseline.json').read_text(encoding='utf-8'))['archive'])/'songs/product_song_review'
def rows(path):
    with path.open(encoding='utf-8') as f:return list(csv.DictReader(f))
def words(path):return {(w['phrase'],w['index']):w for w in json.loads(path.read_text(encoding='utf-8'))['words']}
class ChilegeExpression(unittest.TestCase):
    def test_all_repeats_follow_duration_requests(self):
        old=words(BASE/'chilege_lyrics.json');new=words(REVIEW/'chilege_lyrics.json')
        duration=lambda w:w['end_ms']-w['start_ms']
        for p in (0,4,16):self.assertGreaterEqual(duration(new[p,4])-duration(old[p,4]),200)
        for p in (0,16):
            self.assertLessEqual(duration(new[p,7]),duration(old[p,7])*.70)
            self.assertGreaterEqual(duration(new[p,9])-duration(old[p,9]),400)
        for p in (1,17):self.assertGreaterEqual(duration(new[p,4])-duration(old[p,4]),250)
        for p in (7,20):
            self.assertLessEqual(duration(new[p,5]),duration(old[p,5])*.75)
            for index in (6,7,8):self.assertLess(duration(new[p,index]),duration(old[p,index]))
        for p in (8,12):
            for index in (2,5):self.assertLessEqual(duration(new[p,index]),duration(old[p,index])*.8)
        for p in (10,14):self.assertLessEqual(duration(new[p,2]),duration(old[p,2])*.8)
        self.assertGreaterEqual(duration(new[6,9]),1500)
    def test_no_rearticulated_high_tian_or_spurious_short_melisma(self):
        rs=rows(REVIEW/'chilege.csv');ws=words(REVIEW/'chilege_lyrics.json')
        def notes(p,i):
            w=ws[p,i]
            return [r for r in rs if r['midi']!='rest' and w['begin']<=float(r['source_start_s'])<w['end'] and r['source_location']=='supplied-score-phrase-'+str(p)]
        self.assertEqual([int(r['source_midi']) for r in notes(5,9)],[66])
        self.assertEqual([int(r['source_midi']) for r in notes(6,9)],[59])
        for p in (10,14):
            turn=notes(p,4);self.assertEqual([int(r['source_midi']) for r in turn],[74,66])
            self.assertTrue(all(int(r['duration_ms'])>=350 for r in turn))
            self.assertEqual([int(r['guide_continuation']) for r in turn],[0,1])
        bundle=json.loads((REVIEW/'chilege_lyrics.json').read_text(encoding='utf-8'))
        primary=[i for i,r in enumerate(rs) if r['midi']!='rest' and r['guide_continuation']=='0']
        self.assertEqual([bundle['guide_words'][i] for i in primary],list(range(184)))
    def test_other_melodies_and_accepted_song_remain_identical(self):
        for name in ('wodezuguo.csv','wodezuguo_lyrics.json','wodezuguo_full_preview.wav'):
            self.assertEqual((REVIEW/name).read_bytes(),(BASE/name).read_bytes())
        before=rows(BASE/'chilege.csv');after=rows(REVIEW/'chilege.csv')
        for p in (2,3,9,11,13,15,18,19):
            def part(rs):return [{k:v for k,v in r.items() if k!='step'} for r in rs if r['source_location']=='supplied-score-phrase-'+str(p)]
            self.assertEqual(part(before),part(after),p)
if __name__=='__main__':unittest.main()
