"""Inspect automatic vowel-center fits; references are diagnostic only."""
from pathlib import Path
import json,csv
import numpy as np
from evaluate_oss_vocals import read_notes
from grounded_pitch_decoder import hz_to_midi,SHIFTS
from vocal_pitch_center import estimate_center
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def fit_note(n,r,p,c):
    a=n['start_ms']//10;z=(n['start_ms']+n['duration_ms'])//10
    a+=min(3,(z-a)//10);z-=min(2,(z-a)//10)
    results=[]
    for raw,weight in [(r,np.ones(len(r))),(p,c)]:
        x=raw[a:z];w=weight[a:z].copy()
        options=x[:,None]+SHIFTS[None,:];k=np.argmin(abs(options-n['midi']),axis=1)
        v=options[np.arange(len(x)),k];w[(x<24)|(abs(v-n['midi'])>3)|(w<.35)]=0
        results.append(estimate_center(np.arange(a,z)*.01,v,w))
    return results

def main():
    all_results=[]
    for name,ref in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi'),('lantingxu',None)]:
        ns=read_notes(PRE/name/'full/notes.csv');ev=np.load(PRE/name/'full/evidence.npz');ps=np.load(B/name/'full/pesto.npz')
        rp=hz_to_midi(ev['rmvpe']);rows=[]
        refs=list(csv.DictReader((R/f'songs/product_song_review/{ref}.csv').open(encoding='utf8'))) if ref else []
        for n in ns:
            fits=fit_note(n,rp,ps['midi'],ps['confidence'])
            row={**n,'fits':fits}
            if all(f.get('vibrato') for f in fits):
                row['center_agreement']=abs(fits[0]['center']-fits[1]['center'])
                row['new_candidate']=round((fits[0]['center']+fits[1]['center'])/2)
            expected=[int(r['source_midi']) for r in refs if int(r['source_midi'])>0 and min(float(r['source_end_s'])*1000,n['start_ms']+n['duration_ms'])-max(float(r['source_start_s'])*1000,n['start_ms'])>n['duration_ms']*.4]
            row['reference_pitches']=list(dict.fromkeys(expected));rows.append(row)
        (B/name/'full/vibrato_centers.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
        changes=[v for v in rows if v.get('center_agreement',99)<.6 and v['new_candidate']!=v['midi']]
        print(name,'fits',sum(all(f.get('vibrato') for f in q['fits']) for q in rows),'changes',len(changes),flush=True)
        for q in changes:print(json.dumps(q,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
