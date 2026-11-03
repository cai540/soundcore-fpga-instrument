"""Freeze the shipped 0.7 state; user lyric positions are offline queries only."""
from pathlib import Path
import json,csv,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_phrase_20261029'
B.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in (ROOT/'app/android/app/src').rglob('*') if p.is_file()]
files+=[ROOT/'app/android/app/build.gradle.kts',ROOT/'build/vocal_natural_20261029/release.json']
files+=list((ROOT/'songs/product_song_review').glob('*.csv'))+list((ROOT/'songs/product_song_review').glob('*_lyrics.json'))
manifest={}
for p in files:
 name=p.relative_to(ROOT).as_posix();target=B/'baseline'/name
 if target.exists():assert sha(target)==sha(p),'Baseline already exists with different content: '+name
 else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
 manifest[name]=sha(p)
(B/'baseline_sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
ref=list(csv.DictReader((ROOT/'songs/product_song_review/wodezuguo.csv').open(encoding='utf8')))
lyrics=json.loads((ROOT/'songs/product_song_review/wodezuguo_lyrics.json').read_text(encoding='utf8'))
queries=[]
for phrase in range(4):
 for w in [x for x in lyrics['words'] if x['phrase']==phrase]:
  matches=[n for n in ref if float(n['source_start_s'])<w['end'] and float(n['source_end_s'])>w['begin'] and n['midi']!='rest']
  queries.append({**w,'reference':matches})
(B/'offline_word_queries.json').write_text(json.dumps(queries,ensure_ascii=False,indent=2),encoding='utf8')
print('Frozen',len(manifest),'files; offline lyric words',len(queries))
for q in queries:print(q['phrase'],q['char'],q['begin'],q['end'],[n['source_midi'] for n in q['reference']])
