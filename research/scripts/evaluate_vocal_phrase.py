"""Offline evaluation: references never enter a recognizer call.
Check real change retention AND false internal changes, not just fewer notes.
"""
from pathlib import Path
import csv,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'build/vocal_natural_20261029/audio'
def readnotes(path):
 return [{'start':int(x['start_ms']),'end':int(x['start_ms'])+int(x['duration_ms']),'midi':int(x['midi'])}
  for x in csv.DictReader(path.open(encoding='utf8'))]
def refs(name):
 key='wodezuguo' if name=='zuguo' else name
 return [{'start':round(float(x['source_start_s'])*1000),'end':round(float(x['source_end_s'])*1000),'midi':int(x['source_midi'])}
  for x in csv.DictReader((ROOT/f'songs/product_song_review/{key}.csv').open(encoding='utf8')) if x['midi']!='rest']
def labels(notes,n):
 a=np.full(n,-1)
 for x in notes:a[max(0,x['start']//10):min(n,(x['end']+9)//10)]=x['midi']
 return a
def evaluate(name,window,path):
 olddir=BASE/name/window;old=readnotes(olddir/'notes.csv');new=readnotes(path)
 t=np.genfromtxt(olddir/'vocal_frontend.csv',delimiter=',',names=True);n=len(t)-1
 off=round((47.09 if name=='zuguo' else 30.97)*1000) if window=='first40' else int(window[-2:])*40000
 reference=[{**x,'start':x['start']-off,'end':x['end']-off} for x in refs(name)]
 predictions={'old':labels(old,n),'new':labels(new,n)};expected=labels(reference,n);mask=np.zeros(n,bool)
 for x in reference:
  a=max(0,(x['start']+150)//10);b=min(n,(x['end']-150)//10)
  if b>a:mask[a:b]=True
 out={'name':name,'window':window,'reference_frames':int(mask.sum()),'versions':{},'trusted_changes':[],'long_single_pitch':[]}
 for version,p in predictions.items():
  out['versions'][version]={'matching_frames':int(((p==expected)&mask).sum()),'coverage_frames':int(((p>=0)&mask).sum()),
   'notes':len(old if version=='old' else new)}
 # A trusted reference change additionally needs acoustic time-mean support
 # on BOTH sides. Exclude uncertain manually aligned boundaries from this gate.
 for a,b in zip(reference,reference[1:]):
  if a['midi']==b['midi'] or not(250<a['start']<a['end']<=b['start']+100<b['end']<n*10-250):continue
  spans=[];valid=True
  for x in [a,b]:
   s=max(0,(x['start']+60)//10);e=min(n,(x['end']-60)//10)
   f=t['pitch'][s:e];f=f[np.isfinite(f)]
   if len(f)<8:valid=False;break
   f.sort();trim=f[len(f)//10:len(f)-len(f)//10 or None];center=float(np.mean(trim))
   if abs(center-x['midi'])>.55:valid=False;break
   spans.append((s,e,center))
  if not valid:continue
  item={'boundary_ms':b['start'],'reference':[a['midi'],b['midi']],'acoustic_centers':[x[2] for x in spans]}
  for version,p in predictions.items():
   support=[float(np.mean(p[s:e]==x['midi'])) for (s,e,c),x in zip(spans,[a,b])]
   item[version]={'support':support,'retained':all(q>=.5 for q in support)}
  out['trusted_changes'].append(item)
 # Long nominal single-note blocks: preserve rests, count extra *different*
 # pitches rather than punishing intentional repeated syllables by note count.
 for x in reference:
  s=max(0,(x['start']+100)//10);e=min(n,(x['end']-100)//10)
  if e-s<40 or x['start']<250 or x['end']>n*10-250:continue
  item={'start_ms':x['start'],'end_ms':x['end'],'reference':x['midi']}
  for version,p in predictions.items():
   values,counts=np.unique(p[s:e],return_counts=True)
   item[version]=[int(v) for v,c in zip(values,counts) if v>=0 and c>=8]
  out['long_single_pitch'].append(item)
 return out
if __name__=='__main__':
 directory=Path(sys.argv[1]);dest=Path(sys.argv[2]);results=[]
 for name in ['zuguo','chilege']:
  for d in sorted((directory/name).iterdir()):
   if d.is_dir() and (d/'notes.csv').exists() and (BASE/name/d.name/'vocal_frontend.csv').exists():results.append(evaluate(name,d.name,d/'notes.csv'))
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 for name in ['zuguo','chilege']:
  group=[x for x in results if x['name']==name and x['window'].startswith('chunk_')]
  print(name,'full windows',len(group))
  for v in ['old','new']:
   frames=sum(x['reference_frames'] for x in group);match=sum(x['versions'][v]['matching_frames'] for x in group)
   changes=[c for x in group for c in x['trusted_changes']];longs=[c for x in group for c in x['long_single_pitch']]
   print(v,'pitch',match,frames,round(match/max(1,frames),4),'trusted changes',sum(c[v]['retained'] for c in changes),'/',len(changes),
    'extra-pitch long notes',sum(len(c[v])>1 for c in longs),'/',len(longs))
