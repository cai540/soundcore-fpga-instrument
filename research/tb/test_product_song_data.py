import csv,json,unittest,hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'songs'))
from zuguo_score import phrases
REVIEW=ROOT/'songs/product_song_review';ROM=ROOT/'songs/rom_product_songs'
class ProductSongData(unittest.TestCase):
    def test_score_pitch_and_timing(self):
        with (REVIEW/'wodezuguo.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
        expected=[n['pitch'] for p in phrases() for n in p['notes']]
        self.assertEqual([int(r['midi']) for r in rows if r['midi']!='rest'],expected)
        # Independent score oracle: low 7-6-5 then NORMAL 5, not four lows.
        # pYIN was fooled by residual low C4 under the actual C5 syllable.
        for phrase in (3,16):
            repeated=[int(r['midi']) for r in rows if r['source_location']==f'syllable-review-phrase-{phrase}']
            self.assertEqual(repeated,[64,62,60,72,65,67,69])
        # "分享海的欢乐" is a different phrase; its two low 5s are valid.
        share=[int(r['midi']) for r in rows if r['source_location']=='syllable-review-phrase-21']
        self.assertEqual(share,[64,62,60,60,67,65])
        self.assertGreaterEqual(min(int(r['duration_ms']) for r in rows if r['midi']!='rest'),160)
        self.assertLess(max(int(r['duration_ms']) for r in rows if r['midi']=='rest'),1000)
        self.assertAlmostEqual(float(rows[0]['source_start_s']),47.33,places=2)
        self.assertAlmostEqual(float(rows[-1]['source_end_s']),204.16,places=2)
        self.assertEqual(sum(int(r['duration_ms']) for r in rows),148010)
        # Every completed clause breathes; no silence splits a lyric word.
        self.assertEqual(sum(r['midi']=='rest' for r in rows),31)
        self.assertEqual(int(rows[7]['duration_ms']),910)
        # Wrong repeat alignment previously stretched the second syllable
        # of this line to 1280 ms while squeezing its first note to 190 ms.
        repeat=[r for r in rows if r['source_location']=='syllable-review-phrase-16']
        self.assertEqual([int(r['duration_ms']) for r in repeat[:3]],[400,430,360])
        lyrics=json.loads((REVIEW/'wodezuguo_lyrics.json').read_text(encoding='utf-8'))
        clock=0
        for r in rows:
            duration=int(r['duration_ms'])
            if r['midi']=='rest':
                self.assertTrue(160<=duration<=550)
                self.assertFalse(any(w['start_ms']<clock<w['end_ms'] for w in lyrics['words']))
            clock+=duration
        coda=[r for r in rows if r['source_location']=='syllable-review-phrase-29']
        self.assertEqual([int(r['midi']) for r in coda],[72,79,77,77])
        self.assertAlmostEqual(float(coda[2]['source_start_s']),199.34,places=2)
        self.assertLessEqual(int(coda[-1]['duration_ms']),4500)
    def test_catalogue_rom_and_words(self):
        entries=json.loads((REVIEW/'catalog.json').read_text(encoding='utf-8'))
        kotlin=(ROOT/'app/android/app/src/main/java/cn/soundcore/instrument/SongCatalog.kt').read_text(encoding='utf-8')
        for song in entries:
            with (REVIEW/(song['name']+'.csv')).open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
            packed=[int(x,16) for x in (ROM/f"song_{song['id']}.mem").read_text().split()]
            self.assertEqual(len(packed),song['events']);self.assertEqual(len(rows),len(packed))
            self.assertIn(f'SongEntry({song["id"]}, "{song["title"]}", {song["events"]})',kotlin)
            for r,v in zip(rows,packed):
                self.assertEqual((v>>6)&65535,int(r['duration_ms']))
                self.assertEqual((v>>22)&1,int(r.get('guide_continuation') or 0))
                self.assertEqual('rest' if v&7==7 else str(60+((v>>3)&7)*7+(v&7)),r['midi'])
            lyrics=json.loads((REVIEW/(song['name']+'_lyrics.json')).read_text(encoding='utf-8'))
            starts=[int(v,16) for v in (ROM/f"lyric_starts_{song['id']}.mem").read_text().split()]
            self.assertEqual(len(starts),1024)
            self.assertEqual(starts[:song['words']],[w['start_ms'] for w in lyrics['words']])
            self.assertEqual(len(lyrics['words']),song['words']);self.assertEqual(len(lyrics['guide_words']),song['events'])
            for w in lyrics['words']:
                text=lyrics['phrases'][w['phrase']]['line1']+lyrics['phrases'][w['phrase']]['line2']
                self.assertEqual(text[w['index']],w['char']);self.assertLess(w['start_ms'],w['end_ms'])
                self.assertLessEqual(w['end_ms'],song['duration_ms'])
            self.assertTrue(all(0<=v<song['words'] for v in lyrics['guide_words']))
    def test_chilege_replaces_slot_one_and_preserves_accepted_song(self):
        from chilege_score import phrases as new_phrases,TRANSPOSE
        archive=ROOT/'build/archive/before_chilege_20261026'
        for name in ('wodezuguo.csv','wodezuguo_lyrics.json','wodezuguo_full_preview.wav'):
            self.assertEqual((REVIEW/name).read_bytes(),(archive/'songs/product_song_review'/name).read_bytes())
        self.assertEqual((ROM/'song_0.mem').read_bytes(),(archive/'songs/rom_product_songs/song_0.mem').read_bytes())
        catalog=json.loads((REVIEW/'catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog[1]['name'],'chilege');self.assertEqual(catalog[1]['title'],'敕勒歌')
        with (REVIEW/'chilege.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
        expected=[n['pitch']+TRANSPOSE for p in new_phrases() if p['label']!='vocal-coda' for n in p['notes']]
        self.assertEqual([int(r['midi']) for r in rows if r['midi']!='rest'],expected)
        self.assertTrue(all(int(r['duration_ms'])>=120 for r in rows if r['midi']!='rest'))
        self.assertTrue(all(int(r['duration_ms'])<=650 for r in rows if r['midi']=='rest'))
        self.assertTrue(31.<float(rows[0]['source_start_s'])<32.)
        self.assertAlmostEqual(float(rows[-1]['source_end_s']),221.382,places=3)
        self.assertEqual(sum(int(r['duration_ms']) for r in rows),149000)
        lyrics=json.loads((REVIEW/'chilege_lyrics.json').read_text(encoding='utf-8'))
        primary=[i for i,r in enumerate(rows) if r['midi']!='rest' and r['guide_continuation']=='0']
        self.assertEqual([lyrics['guide_words'][i] for i in primary],list(range(len(lyrics['words']))))
        for p in (11,15):
            notes=[int(r['source_midi']) for r in rows if r['source_location']=='supplied-score-phrase-'+str(p)]
            self.assertEqual(notes[:3],[66,69,59]) # Low 6 under 草, not a spurious octave jump.
        # Common baseline: "一" must be centered in its 16-pixel cell.
        glyph=json.loads((ROM/'lyric_manifest.json').read_text(encoding='utf-8'))['glyphs']['一']
        font=[int(x,16) for x in (ROM/'lyric_font.mem').read_text().split()]
        active=[p*8+b for p in range(2) for x in range(16) for b in range(8) if font[glyph*32+p*16+x]&(1<<b)]
        self.assertEqual((min(active),max(active)),(7,8))
    def test_preview_durations_and_amplitudes(self):
        for song in json.loads((REVIEW/'catalog.json').read_text(encoding='utf-8')):
            wave,sr=sf.read(REVIEW/(song['name']+'_full_preview.wav'))
            self.assertAlmostEqual(len(wave)/sr,song['duration_ms']/1000,places=3)
            self.assertTrue(np.isfinite(wave).all());self.assertLess(np.max(np.abs(wave)),.9)
if __name__=='__main__':unittest.main()
