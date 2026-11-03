"""Diagnostic reference use only. No reference leaves this audit module."""
from pathlib import Path
import csv,json
import numpy as np
from oss_vocal_postprocess import f0_grid
from evaluate_oss_vocals import read_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_oss_20261029';O=R/'build/vocal_syllable_main_20261029'

def word_edges(trace):
    out=[]
    for c in trace['chunks']:
        out.extend(c['begin_ms']+i*128/24 for i in c['word_boundary_frames']
                   if c['core_start_ms']<=c['begin_ms']+i*128/24<c['core_end_ms'])
    return np.array(out)

def main():
    O.mkdir(exist_ok=True)
    for name,ref in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi')]:
        tr=json.loads((B/'rosvot'/name/'full/trace.json').read_text())
        info=json.loads((B/'rosvot'/name/'full/result.json').read_text())
        edges=word_edges(tr);f0=f0_grid(tr,info['source_ms'])
        new_evidence=O/name/'full/evidence.npz'
        fc=np.load(new_evidence)['fcpe'] if new_evidence.exists() else np.zeros(len(f0))
        pitch=np.where(f0>0,69+12*np.log2(np.maximum(f0,1)/440),np.nan)
        ns=read_notes(B/'game_medium'/name/'full/notes.csv')
        words=json.loads((R/f'songs/product_song_review/{ref}_lyrics.json').read_text(encoding='utf8'))['words']
        refs=list(csv.DictReader((R/f'songs/product_song_review/{ref}.csv').open(encoding='utf8')))
        rows=[]
        for w in words:
            a=w['begin']*1000;z=w['end']*1000
            if z-a<100:continue
            contained=[n for n in ns if min(z,n['start_ms']+n['duration_ms'])-max(a,n['start_ms'])>70]
            inside=pitch[int((a+60)/10):int((z-60)/10)];inside=inside[np.isfinite(inside)]
            rp=[int(r['source_midi']) for r in refs if int(r['source_midi'])>0 and min(z,float(r['source_end_s'])*1000)-max(a,float(r['source_start_s'])*1000)>80]
            row={'char':w['char'],'start':round(a),'end':round(z),'pitch':round(float(np.median(inside)),2) if len(inside) else None,
                 'ref_pitches':list(dict.fromkeys(rp)),'model_pitches':[n['midi'] for n in contained],
                 'word_boundaries_inside':np.round(edges[(edges>a+100)&(edges<z-100)]).astype(int).tolist(),
                 'nearest_start_error':round(float(np.min(abs(edges-a)))) if len(edges) else None}
            fi=fc[int((a+60)/10):int((z-60)/10)];fi=fi[fi>0]
            row['fcpe_pitch']=round(float(np.median(69+12*np.log2(fi/440))),2) if len(fi) else None
            rows.append(row)
        (O/f'{name}_baseline_word_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,'words',len(rows),'RWBD',len(edges),'GAME',len(ns),'F0wrong',sum(r['pitch'] is not None and round(r['pitch']) not in r['ref_pitches'] for r in rows if r['ref_pitches']),flush=True)
        print('start<=100ms',sum(r['nearest_start_error']<=100 for r in rows),'word internal bds',sum(len(r['word_boundaries_inside']) for r in rows),flush=True)
        if name=='zuguo':
            for row in rows[:68]:print(json.dumps(row,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
