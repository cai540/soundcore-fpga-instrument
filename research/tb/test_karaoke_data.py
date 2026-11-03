import csv,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class KaraokeData(unittest.TestCase):
    def test_source_clock_order_and_rom(self):
        for song,name in enumerate(('lantingxu','qiansixi')):
            with (ROOT/'songs/karaoke_review'/f'{name}.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
            words=[int(s,16) for s in (ROOT/'songs/rom_karaoke'/f'song_{song}.mem').read_text().splitlines()]
            self.assertEqual(len(rows),len(words))
            for i,(r,w) in enumerate(zip(rows,words)):
                if i:self.assertAlmostEqual(float(rows[i-1]['source_end_s']),float(r['source_start_s']),places=3)
                self.assertGreater(int(r['duration_ms']),0)
                self.assertEqual(int(r['duration_ms']),w>>6)
                p='rest' if w&7==7 else str(60+((w>>3)&7)*7+(w&7))
                self.assertEqual(r['midi'],p)
    def test_qian_chorus_has_no_inserted_silences(self):
        with (ROOT/'songs/karaoke_review/qiansixi.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
        for r in rows:
            t=(float(r['source_start_s'])+float(r['source_end_s']))/2
            if 90.13<=t<111.95 or 179.50<=t<223.15:self.assertNotEqual(r['midi'],'rest')
    def test_lanting_one_note_per_character_and_lower_opera(self):
        with (ROOT/'songs/karaoke_review/lantingxu.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
        lyrics=json.loads((ROOT/'songs/karaoke_review/lantingxu_lyrics.json').read_text(encoding='utf-8'))
        self.assertEqual(len([r for r in rows if r['midi']!='rest']),len(lyrics['words']))
        opera=[r for r in rows if r['source_location']=='opera']
        self.assertEqual(len(opera),80)
        self.assertLessEqual(max(int(r['midi']) for r in opera),71)
        for r in opera:self.assertGreaterEqual(int(r['duration_ms']),65)
    def test_lyrics_and_guide_addresses_are_bounded(self):
        for song,name in enumerate(('lantingxu','qiansixi')):
            b=json.loads((ROOT/'songs/karaoke_review'/f'{name}_lyrics.json').read_text(encoding='utf-8'))
            self.assertEqual(len(b['words']),len({(w['phrase'],w['index']) for w in b['words']}))
            for i,w in enumerate(b['words']):
                self.assertGreater(w['end_ms'],w['start_ms'])
                if i:self.assertGreaterEqual(w['start_ms'],b['words'][i-1]['start_ms'])
                self.assertEqual(w['char'],(b['phrases'][w['phrase']]['line1']+b['phrases'][w['phrase']]['line2'])[w['index']])
            self.assertLess(max(b['guide_words']),len(b['words']))
if __name__=='__main__':unittest.main()
