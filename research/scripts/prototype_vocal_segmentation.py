"""Generic acoustic prototype; no reference pitches/times in segment()."""
from pathlib import Path
import numpy as np
import json,csv

def median(a,n):
 return np.median(np.lib.stride_tricks.sliding_window_view(np.pad(a,(n//2,n//2),mode='edge'),n),axis=-1)
def runs(a):
 edges=np.r_[0,np.flatnonzero(a[1:]!=a[:-1])+1,len(a)]
 return [(int(s),int(e),a[s]) for s,e in zip(edges,edges[1:])]

def vibrato_center(p):
 """Remove only coherent 3..9Hz oscillation, not an isolated step/ramp."""
 out=p.copy()
 for i in range(len(p)):
  s=max(0,i-42);e=min(len(p),i+43);y=p[s:e];t=(np.arange(s,e)-i)*.01
  if len(y)<60:continue
  if np.count_nonzero(abs(np.diff(y))>.035)<.35*(len(y)-1):continue
  base=np.column_stack([np.ones(len(t)),t]);coef=np.linalg.lstsq(base,y,rcond=None)[0]
  residual=y-base@coef;var=np.dot(residual,residual)
  if var<.04*len(t):continue
  best=None
  for f in np.arange(3,9.01,.5):
   osc=np.column_stack([np.cos(2*np.pi*f*t),np.sin(2*np.pi*f*t)])
   c=np.linalg.lstsq(osc,residual,rcond=None)[0];fit=osc@c
   explained=1-np.dot(residual-fit,residual-fit)/var
   if best is None or explained>best[0]:best=(explained,c[0])
  if best[0]>.65:out[i]-=best[1]*min(1,(best[0]-.65)/.15)
 return out

def segment(pitch,prob,rms,duration):
 p=pitch.copy();energy=median(rms,5);floor=max(.0025,float(np.max(rms))*.035)
 active=np.isfinite(p)&(rms>floor)
 p[~active]=np.nan
 labels=np.where(active,np.rint(np.nan_to_num(p,nan=-100)).astype(int),-1)
 labels=median(labels,9).astype(int);labels[~active]=-1
 original=p.copy()
 for s,e,n in runs(labels):
  if n<0 or e-s>45 or np.mean(prob[s:e])>=.45:continue
  left=original[max(0,s-50):s];right=original[e:min(len(p),e+50)]
  left=left[np.isfinite(left)&(np.abs(left-n)>6)];right=right[np.isfinite(right)&(np.abs(right-n)>6)]
  if len(left)<8 or len(right)<8:continue
  a=np.median(left);b=np.median(right)
  for delta in [-12,12]:
   if abs(n+delta-a)<=3 and abs(n+delta-b)<=3 and abs(a-b)<=4:
    p[s:e]+=delta;break
 # Interpolate only after octave repair so a missing-pitch gap cannot create
 # a staircase through the middle of an octave-error jump.
 for s,e,state in runs(active):
  if not state and s>0 and e<len(p) and e-s<=16 and active[s-1] and active[e] and np.all(rms[s:e]>floor*1.5):
   p[s:e]=np.linspace(p[s-1],p[e],e-s+2)[1:-1];active[s:e]=True
 attacks=np.zeros(len(p));cuts=[]
 for k in range(2,len(p)-2):
  if not(energy[k]<energy[k-1] and energy[k]<=energy[k+1]):continue
  a=np.max(energy[max(0,k-25):k]);b=np.max(energy[k+1:min(len(p),k+26)])
  low=energy[k];height=min(a,b)
  if height<floor*3 or height<low*2.2:continue
  threshold=low+(height-low)*.5;l=k;r=k
  while l>0 and k-l<25 and energy[l-1]<threshold:l-=1
  while r+1<len(p) and r-k<25 and energy[r+1]<threshold:r+=1
  if r-l+1>9:continue
  cuts.append(k)
  for i in range(max(0,k-3),min(len(p),k+13)):attacks[i]=max(attacks[i],max(0,1-abs(i-k)/16))
 # Filter the continuous trajectory BEFORE rounding. 250ms rejects periodic
 # vibrato excursions while keeping >=150ms plateaus and monotone fast runs.
 for s,e,state in runs(active):
  if state:p[s:e]=vibrato_center(median(p[s:e],5))
 # Weak whole-phrase pitch prior, never a fixed key or a fixed note set.
 observed=p[np.isfinite(p)];lo=max(24,int(np.floor(np.min(observed)))-1);hi=min(108,int(np.ceil(np.max(observed)))+1)
 candidates=np.arange(lo,hi+1);c=len(candidates);dwell=15
 hist=np.zeros(c)
 for i in np.flatnonzero(np.isfinite(p)):
  hist+=np.exp(-.5*((candidates-p[i])/.3)**2)*(.25+.75*min(rms[i]/max(floor,np.max(rms)*.3),1))
 prior=-.04*np.log((hist+max(hist.max()*.02,.01))/(hist.max()+max(hist.max()*.02,.01)))
 output=[]
 for s,e,state in runs(active):
  if not state or e-s<dwell:continue
  if e-s<25 and np.mean(prob[s:e])<.12 and np.max(rms[s:e])<np.max(rms)*.18:continue
  # Trim only trailing very weak fade, never insert a gap inside an island.
  edge=max(floor,float(np.max(energy[s:e]))*.10)
  audible=np.flatnonzero(energy[s:e]>=edge)
  if len(audible):e=min(e,s+int(audible[-1])+4)
  if e-s<dwell:continue
  back=np.full((e-s,c,dwell),-1,dtype=np.int16)
  previous=np.full((c,dwell),np.inf)
  for frame in range(s,e):
   k=frame-s;delta=abs(p[min(e-1,frame+3)]-p[max(s,frame-3)])
   stable=max(.25,1/(1+(delta/.55)**4))
   weight=(.6+.4*prob[frame])*stable
   diff=np.abs(candidates-p[frame]);fit=np.minimum(4,np.where(diff<=.75,diff**2,1.5*diff-.5625))*weight+prior
   if k==0:previous[:,0]=fit;continue
   now=np.full_like(previous,np.inf)
   now[:,1:]=previous[:,:-1]+fit[:,None]
   for age in range(1,dwell):back[k,:,age]=np.arange(c)*dwell+age-1
   stay=previous[:,-1]<previous[:,-2]
   now[stay,-1]=previous[stay,-1]+fit[stay];back[k,stay,-1]=np.arange(c)[stay]*dwell+dwell-1
   order=np.argsort(previous[:,-1]);a=int(order[0]);b=int(order[1])
   source=np.where(np.arange(c)==a,b,a)
   penalty=6.*(1-.65*attacks[frame])
   now[:,0]=previous[source,-1]+penalty+fit
   back[k,:,0]=source*dwell+dwell-1
   previous=now
  state=int(np.argmin(previous[:,-1]))*dwell+dwell-1
  decoded=np.zeros(e-s,dtype=int)
  for k in range(e-s-1,-1,-1):decoded[k]=lo+state//dwell;state=int(back[k].flat[state]) if k else -1
  for a,b,n in runs(decoded):
   a+=s;b+=s;boundaries=[a]
   for cut in cuts:
    if cut-a>=12 and b-cut>=12 and cut-boundaries[-1]>=12:boundaries.append(cut)
   boundaries.append(b)
   for start,end in zip(boundaries,boundaries[1:]):
    if end-start>=9:output.append({'start_ms':start*10,'duration_ms':min(end*10,duration)-start*10,'midi':int(n),'confidence':float(np.mean(prob[start:end]))})
 return output

if __name__=='__main__':
 ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_syllable_20261029'
 for name in ['zuguo','chilege']:
  t=np.genfromtxt(B/name/'old_track.csv',delimiter=',',names=True)
  out=segment(t['pitch'],t['probability'],t['rms'],40000)
  p=B/name/'prototype_notes.csv'
  with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence']);w.writeheader();w.writerows(out)
  reference=json.loads((B/name/'reference.json').read_text(encoding='utf8'));report=[]
  for w in reference['words']:
   s=max(0,w['start']+60);e=min(40000,w['end']-60)
   if e<=s:continue
   predicted=[n for n in out if min(e,n['start_ms']+n['duration_ms'])-max(s,n['start_ms'])>=40]
   expected=[n for n in reference['references'] if min(e,n['end'])-max(s,n['start'])>=40]
   report.append({**w,'predicted_notes':len(predicted),'predicted_pitches':[n['midi'] for n in predicted],
    'reference_pitches':list(dict.fromkeys(n['midi'] for n in expected))})
  (B/name/'prototype_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  print(name,len(out),'notes; multiple pitch words',sum(len(set(w['predicted_pitches']))>len(w['reference_pitches']) for w in report),flush=True)
