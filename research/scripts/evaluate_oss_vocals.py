"""Offline diagnostics. Editorial notes are never read by the recognizer.

These references are earlier manually edited listening targets, not an
independent fully annotated benchmark. Report coverage and sample counts,
not a made-up musical-quality score or transcription accuracy claim.
"""
from pathlib import Path
import csv,json
import numpy as np
from oss_vocal_postprocess import f0_grid,central_pitch

R=Path(__file__).resolve().parents[1];B=R/'build/vocal_oss_20261029'

def read_notes(path):
    return [{'start_ms':int(q['start_ms']),'duration_ms':int(q['duration_ms']),'midi':int(q['midi']),
             'confidence':float(q['confidence'])} for q in csv.DictReader(path.open(encoding='utf8'))]

def track(notes,length):
    t=np.zeros((length+9)//10,dtype=int)
    for n in notes:
        t[int(np.ceil(n['start_ms']/10)):int(np.ceil((n['start_ms']+n['duration_ms'])/10))]=n['midi']
    return t

def main():
    all_results=[]
    old_items=json.loads((R/'build/vocal_final_phrases_20261029/audio_results.json').read_text(encoding='utf8'))
    for model in ['old_0.9','rosvot','rosvot_checkpoint','game_medium','game_small','game_medium_game_cli','consensus']:
        for name,refname in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi'),('lantingxu',None)]:
            d=B/model/name/'full'
            if model=='old_0.9':
                ns=[];length=0
                for q in old_items:
                    if q['name']!=name or not q['window'].startswith('chunk_'):continue
                    offset=round(q['offset_seconds']*1000);folder=Path(q['new'])
                    length=max(length,offset+(folder/'analysis.f32').stat().st_size//64)
                    if (folder/'notes.csv').exists():ns += [{**n,'start_ms':n['start_ms']+offset} for n in read_notes(folder/'notes.csv')]
                info={'source_ms':length};policies=[('raw',ns)]
            else:
                if not (d/'result.json').exists():continue
                info=json.loads((d/'result.json').read_text());ns=read_notes(d/'notes.csv');policies=[('raw',ns)]
            if model.startswith(('rosvot','game_')):
                # GAME remains the boundary classifier. RMVPE is independent
                # pitch evidence, already measured on identical source PCM.
                tr=json.loads(((B/'rosvot'/name/'full' if model.startswith('game_') else d)/'trace.json').read_text())
                f0=f0_grid(tr,info['source_ms']);new,audit=central_pitch(ns,f0)
                with (d/'center_notes.csv').open('w',encoding='utf8',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence']);w.writeheader();w.writerows(new)
                (d/'pitch_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
                policies.append(('center',new))
            for policy,notes in policies:
                p=track(notes,info['source_ms'])
                row={'model':model,'name':name,'policy':policy,'notes':len(notes),'short_under150ms':sum(q['duration_ms']<150 for q in notes),
                     'changed_pitches':sum(a['midi']!=b['midi'] for a,b in zip(ns,notes))}
                if refname:
                    ref=list(csv.DictReader((R/f'songs/product_song_review/{refname}.csv').open(encoding='utf8')))
                    valid=np.zeros(len(p),bool);rest=np.zeros(len(p),bool);target=np.zeros(len(p),int)
                    for q in ref:
                        # Stable interior only, explicitly excludes attacks and releases.
                        a=int(np.ceil((float(q['source_start_s'])+.15)*100));z=int(np.floor((float(q['source_end_s'])-.15)*100))
                        if z>a:
                            pitch=int(q['source_midi'])
                            if pitch>0:valid[a:z]=True;target[a:z]=pitch
                            else:rest[a:z]=True
                    error=np.abs(target-p)
                    row.update(reference_interior_seconds=round(valid.sum()/100,2),
                               interior_coverage=round(float(np.mean(p[valid]>0)),4),
                               exact_semitone_agreement=round(float(np.mean(error[valid]==0)),4),
                               within_one_semitone=round(float(np.mean(error[valid]<=1)),4),
                               reference_rest_interior_seconds=round(rest.sum()/100,2),
                               reference_rest_false_voiced_fraction=round(float(np.mean(p[rest]>0)),4) if rest.any() else None)
                    if name=='zuguo':
                        after=valid & (np.arange(len(p))*10>=87090)
                        row['after_first40_seconds']=round(after.sum()/100,2)
                        row['after_first40_exact_agreement']=round(float(np.mean(error[after]==0)),4)
                all_results.append(row)
    (B/'offline_diagnostics.json').write_text(json.dumps(all_results,ensure_ascii=False,indent=2),encoding='utf8')
    for q in all_results:print(json.dumps(q,ensure_ascii=False))

if __name__=='__main__':main()
