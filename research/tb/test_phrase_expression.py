import csv,json,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'songs/phrase_expression_review'

class PhraseExpression(unittest.TestCase):
    def test_score_and_clock_preserved(self):
        reports=json.loads((OUT/'report.json').read_text(encoding='utf-8'))
        for song,name in enumerate(('lantingxu','qiansixi')):
            with (OUT/f'{name}.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
            with (ROOT/'songs/continuous_score_review'/f'{name}.csv').open(encoding='utf-8') as f:base=list(csv.DictReader(f))
            def melodic_order(source):
                pitches=[]
                for r in source:
                    if r['midi']!='rest' and (not pitches or pitches[-1]!=r['midi']):pitches.append(r['midi'])
                return pitches
            self.assertEqual(melodic_order(rows),melodic_order(base))
            self.assertEqual(sum(int(r['duration_ms']) for r in rows),sum(int(r['duration_ms']) for r in base))
            words=[int(w,16) for w in (ROOT/'songs/rom_phrase_expression'/f'song_{song}.mem').read_text().splitlines()]
            self.assertEqual(len(rows),len(words))
            for r,w in zip(rows,words):
                pitch='rest' if (w&7)==7 else str(60+((w>>3)&7)*7+(w&7))
                self.assertEqual((r['midi'],int(r['duration_ms'])),(pitch,w>>6))
            breaths=reports[name]['phrase_breaths']
            self.assertGreater(sum(r['midi']=='rest' for r in rows),sum(r['midi']=='rest' for r in base)*2)
            for b in breaths:
                match=next(r for r in rows if r['segmentation']=='score-phrase-breath' and abs(float(r['source_start_s'])-b['begin'])<.001)
                self.assertEqual(match['midi'],'rest')
                self.assertGreaterEqual(int(match['duration_ms']),95)
                self.assertLessEqual(int(match['duration_ms']),260)
                if 'raw_rest_end' in b:
                    self.assertAlmostEqual(b['end'],b['raw_rest_end'],places=3)
                    self.assertGreaterEqual(b['begin']+.001,b['raw_rest_begin'])
            for change in reports[name]['timing_refinements']:
                self.assertLessEqual(abs(change['after_s']-change['before_s']),.101)
                self.assertLess(change['new_pitch_error'],change['old_pitch_error']*.65)

if __name__=='__main__':unittest.main()
