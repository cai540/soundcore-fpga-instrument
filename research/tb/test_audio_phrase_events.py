"""Regression checks for the rushed turns / sparse phrases reported on board."""
import csv
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class AudioPhraseEvents(unittest.TestCase):
    def rows(self,name):
        with (ROOT/'songs/audio_phrase_review'/f'{name}.csv').open(encoding='utf-8',newline='') as f:
            return list(csv.DictReader(f))

    def test_audio_clock_is_preserved(self):
        for name in ('lantingxu','qiansixi'):
            for r in self.rows(name):
                span=round((float(r['source_end_s'])-float(r['source_start_s']))*1000)
                duration=int(r['duration_ms'])
                # Only an explicit, long silent interlude may be shortened.
                if duration!=span:
                    self.assertEqual(r['midi'],'rest')
                    self.assertGreater(span,1800)
                    self.assertEqual(duration,600)
                if r['midi']!='rest': self.assertGreaterEqual(duration,170)

    def test_known_vocal_entries_and_outro(self):
        for name,first in [('lantingxu',[69,66,69]),('qiansixi',[77,76,72])]:
            rows=self.rows(name)
            notes=[int(r['midi']) for r in rows if r['midi']!='rest']
            self.assertEqual(notes[:3],first)
        end=self.rows('lantingxu')[-1]
        self.assertEqual((int(end['midi']),int(end['duration_ms'])),(74,2710))
        self.assertLess(float(end['source_end_s']),232)

    def test_interlude_and_dense_flickers(self):
        for r in self.rows('qiansixi'):
            if 111.95<=float(r['source_start_s'])<135.95:
                self.assertEqual(r['midi'],'rest')
        for name in ('lantingxu','qiansixi'):
            rows=self.rows(name)
            self.assertLessEqual(max(int(r['duration_ms']) for r in rows if r['midi']=='rest'),1800)
            for a,b,c in zip(rows,rows[1:],rows[2:]):
                if 'rest' in (a['midi'],b['midi'],c['midi']): continue
                p,q,r=(int(x['midi']) for x in (a,b,c))
                self.assertFalse(abs(p-q)>=7 and abs(q-r)>=7 and abs(p-r)<=2
                                 and int(b['duration_ms'])<260,(name,b))

    def test_rom_round_trip(self):
        for song,name in enumerate(('lantingxu','qiansixi')):
            rows=self.rows(name)
            words=[int(x,16) for x in (ROOT/'songs/rom_audio_phrase_review'/f'song_{song}.mem').read_text().splitlines()]
            self.assertEqual(len(rows),len(words))
            self.assertLessEqual(len(rows),1024)
            for row,w in zip(rows,words):
                p='rest' if w&7==7 else str(60+((w>>3)&7)*7+(w&7))
                self.assertEqual((row['midi'],int(row['duration_ms'])),(p,w>>6))

    def test_no_sparse_seven_second_windows(self):
        for name in ('lantingxu','qiansixi'):
            starts=[]; elapsed=0
            for row in self.rows(name):
                if row['midi']!='rest': starts.append(elapsed)
                elapsed+=int(row['duration_ms'])
            for start in range(0,elapsed-7000,1000):
                self.assertGreater(sum(start<=s<start+7000 for s in starts),2,
                                   (name,start))


if __name__=='__main__': unittest.main()
