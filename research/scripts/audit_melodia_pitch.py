"""Offline diagnostic. Editorial targets are not provided to pitch extraction."""
from pathlib import Path
import json,csv
import numpy as np
from evaluate_oss_vocals import read_notes,track
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def summarize(values):
    values=np.asarray(values);values=values[(values>=24)&(values<=108)]
    if len(values)<5:return None
    pitches=np.arange(24,109)
    mass=np.exp(-.5*((pitches[:,None]-values)/.65)**2).mean(axis=1)
    j=int(np.argmax(mass))
    around=values[abs(values-pitches[j])<1.5]
    return {'mode':int(pitches[j]),'mass':float(mass[j]),'mean':float(around.mean()),
            'std':float(around.std()),'voiced_frames':len(values)}

def main():
    totals=[]
    for name,ref in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi'),('lantingxu',None)]:
        d=B/name/'full'
        if not (d/'melodia.npz').exists():continue
        evidence=np.load(d/'melodia.npz');f=evidence['f0'];p=np.where(f>0,69+12*np.log2(np.maximum(f,1)/440),0)
        old=read_notes(PRE/name/'full/notes.csv');new=[];audit=[]
        for n in old:
            a=(n['start_ms']+9)//10;z=(n['start_ms']+n['duration_ms']+9)//10;trim=min(5,(z-a)//8)
            value=summarize(p[a+trim:z-min(3,trim)])
            pitch=value['mode'] if value else n['midi']
            new.append({**n,'midi':pitch});audit.append({**n,'melodia':value,'new_midi':pitch})
        row={'name':name,'changes':sum(o['midi']!=n['midi'] for o,n in zip(old,new))}
        if ref:
            length=json.loads((d/'result.json').read_text())['source_ms'];preds=[track(old,length),track(new,length)]
            target=np.zeros(len(preds[0]),int);valid=np.zeros(len(target),bool)
            refs=list(csv.DictReader((R/f'songs/product_song_review/{ref}.csv').open(encoding='utf8')))
            for q in refs:
                m=int(q['source_midi']);a=int(np.ceil((float(q['source_start_s'])+.12)*100));z=int(np.floor((float(q['source_end_s'])-.12)*100))
                if m>0 and z>a:target[a:z]=m;valid[a:z]=True
            for label,pred in zip(['old','melodia'],preds):
                err=abs(pred-target);row[label]={'agreement':float(np.mean(err[valid]==0)),
                     'semitone_error_s':float(np.sum((err==1)&valid))/100,'octave_error_s':float(np.sum((err==12)&valid))/100}
        (d/'melodia_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        totals.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (B/'melodia_diagnostics.json').write_text(json.dumps(totals,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
