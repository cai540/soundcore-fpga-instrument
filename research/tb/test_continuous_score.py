import csv
import json
import unittest
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'songs/continuous_score_review'


class ContinuousScore(unittest.TestCase):
    def rows(self,name):
        with (OUT/f'{name}.csv').open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

    def test_known_false_gaps_are_sounding(self):
        probes={'lantingxu':[27.9,34.3,40.65,66.6,73.1],
                'qiansixi':[25.35,92.6,97.3,98.6,100.9,102.3]}
        for name,times in probes.items():
            for t in times:
                row=next(r for r in self.rows(name) if float(r['source_start_s'])<=t<float(r['source_end_s']))
                self.assertNotEqual(row['midi'],'rest',(name,t,row))

    def test_main_vocal_pitch_entries(self):
        for name,expected in [('lantingxu',[69,66,69,71,66,69,71,69,66,64,66]),
                              ('qiansixi',[77,76,72,69,72,74])]:
            pitches=[int(r['midi']) for r in self.rows(name) if r['midi']!='rest']
            self.assertEqual(pitches[:len(expected)],expected)

    def test_mute_requires_low_energy_or_explicit_section_gap(self):
        reports=json.loads((OUT/'report.json').read_text(encoding='utf-8'))
        for name,report in reports.items():
            measurement=np.load(ROOT/'songs/audio_measurements'/f'{name}.npz')
            for row in self.rows(name):
                if row['midi']!='rest' or row['source_location']=='between-vocal-sections':continue
                a,b=float(row['source_start_s']),float(row['source_end_s'])
                mask=(measurement['times']>=a)&(measurement['times']<b)
                threshold=next(s['quiet_threshold'] for s in report['sections'] if s['begin']<=a<s['end'])
                self.assertLessEqual(float(np.max(measurement['rms'][mask])),threshold*1.05)

    def test_rom_pitch_duration_and_source_clock(self):
        for song,name in enumerate(('lantingxu','qiansixi')):
            rows=self.rows(name)
            words=[int(s,16) for s in (ROOT/'songs/rom_continuous_score'/f'song_{song}.mem').read_text().splitlines()]
            self.assertEqual(len(rows),len(words))
            for row,word in zip(rows,words):
                pitch='rest' if word&7==7 else str(60+((word>>3)&7)*7+(word&7))
                self.assertEqual((row['midi'],int(row['duration_ms'])),(pitch,word>>6))
                span=round((float(row['source_end_s'])-float(row['source_start_s']))*1000)
                if int(row['duration_ms'])!=span:
                    self.assertEqual(row['midi'],'rest')
                    self.assertGreater(span,1800)
                    self.assertEqual(int(row['duration_ms']),600)


if __name__=='__main__':unittest.main()
