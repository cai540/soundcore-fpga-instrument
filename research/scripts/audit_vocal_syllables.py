"""Offline comparison to curated SOURCE clocks, never used at runtime."""
from pathlib import Path
import csv,json,os,subprocess,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_syllable_20261029';B.mkdir(exist_ok=True)
JDK=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
cp=os.pathsep.join(map(str,[ROOT/'build/generic_four_vocals_20261028/frozen_classes',stdlib,B]))
subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(B),str(ROOT/'scripts/support/DumpVocalTrack.java')],check=True)
sources={'zuguo':('wodezuguo',47.09),'chilege':('chilege',30.97)}
all_words={};metrics=[]
for key,(ref,offset) in sources.items():
 d=B/key;d.mkdir(exist_ok=True)
 source=ROOT/f'build/generic_four_vocals_20261028/{key}/first40'
 if not (d/'old_track.csv').exists():subprocess.run([str(JDK/'java.exe'),'-cp',cp,'DumpVocalTrack',str(source/'analysis.f32'),str(d/'old_track.csv')],check=True)
 rows=list(csv.DictReader((ROOT/f'songs/product_song_review/{ref}.csv').open(encoding='utf8')))
 refs=[dict(start=round(float(r['source_start_s'])*1000-offset*1000),end=round(float(r['source_end_s'])*1000-offset*1000),
    midi=int(r['source_midi'])) for r in rows if r['midi']!='rest' and float(r['source_end_s'])>offset and float(r['source_start_s'])<offset+40]
 words=json.loads((ROOT/f'songs/product_song_review/{ref}_lyrics.json').read_text(encoding='utf8'))['words']
 words=[dict(char=w['char'],start=round(w['begin']*1000-offset*1000),end=round(w['end']*1000-offset*1000),
  phrase=w['phrase'],index=w['index']) for w in words if w['end']>offset and w['begin']<offset+40]
 all_words[key]={'offset':offset,'references':refs,'words':words}
 (d/'reference.json').write_text(json.dumps(all_words[key],ensure_ascii=False,indent=2),encoding='utf8')
 notes=[dict(start=int(n['start_ms']),end=int(n['start_ms'])+int(n['duration_ms']),midi=int(n['midi']))
  for n in csv.DictReader((source/'notes.csv').open())]
 report=[]
 for w in words:
  s=max(0,w['start']+60);e=min(40000,w['end']-60)
  if e<=s:continue
  inside=[n for n in notes if min(e,n['end'])-max(s,n['start'])>=40]
  refinside=[n for n in refs if min(e,n['end'])-max(s,n['start'])>=40]
  report.append({**w,'predicted_notes':len(inside),'predicted_pitches':[n['midi'] for n in inside],
   'reference_pitches':list(dict.fromkeys(n['midi'] for n in refinside))})
 (d/'old_word_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(key,'words',len(report),'multiple pitch words',sum(len(set(w['predicted_pitches']))>len(w['reference_pitches']) for w in report),flush=True)

from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['SimHei'];plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(4,1,figsize=(16,11),constrained_layout=True)
for row,(key,ref) in enumerate(all_words.items()):
 t=np.genfromtxt(B/key/'old_track.csv',delimiter=',',names=True)
 ax=axes[row*2];ax.plot(t['ms']/1000,t['pitch'],lw=.8,label='原始逐帧音高')
 for n in ref['references']:
  if n['start']<12000 and n['end']>0:ax.plot([max(0,n['start'])/1000,min(12000,n['end'])/1000],[n['midi']]*2,color='red',lw=2)
 for w in ref['words']:
  if 0<=w['start']<12000:ax.axvline(w['start']/1000,color='gray',alpha=.35);ax.text(w['start']/1000,82,w['char'])
 ax.set_xlim(0,12);ax.set_ylim(49,84);ax.set_title(key+'：红色为旧精修的源时间主音，仅供对照');ax.grid(alpha=.2)
 ax=axes[row*2+1];ax.plot(t['ms']/1000,t['rms'],label='RMS');ax.plot(t['ms']/1000,t['probability']*.15,alpha=.6,label='置信度×0.15');ax.set_xlim(0,12);ax.legend();ax.grid(alpha=.2)
fig.savefig(B/'baseline_pitch_words.png',dpi=130)
print(B/'baseline_pitch_words.png')
