"""Offline audit only; edited song notes/words are NOT inference inputs."""
from pathlib import Path
import json,csv
import numpy as np
from evaluate_oss_vocals import read_notes,track
from package_vocal_oss import baseline_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_syllable_main_20261029';OLD=R/'build/vocal_oss_20261029'

def main():
    rows=[]
    for name,ref in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi'),('lantingxu',None)]:
        d=B/name/'full'
        if not (d/'notes.csv').exists():continue
        info=json.loads((d/'result.json').read_text());length=info['source_ms']
        sequences={'old_0.9':baseline_notes(name),'game':read_notes(OLD/'game_medium'/name/'full/notes.csv'),
                   'syllable_main':read_notes(d/'notes.csv')}
        if (d/'notes_reestimated.csv').exists():sequences['reestimate_v2_rejected']=read_notes(d/'notes_reestimated.csv')
        for model,ns in sequences.items():
            row={'name':name,'model':model,'events':len(ns),'under_200ms':sum(n['duration_ms']<200 for n in ns)}
            if ref:
                refs=list(csv.DictReader((R/f'songs/product_song_review/{ref}.csv').open(encoding='utf8')))
                words=json.loads((R/f'songs/product_song_review/{ref}_lyrics.json').read_text(encoding='utf8'))['words']
                predicted=track(ns,length);target=np.zeros(len(predicted),int);valid=np.zeros(len(predicted),bool);rest=np.zeros(len(predicted),bool)
                for r in refs:
                    a=int(np.ceil((float(r['source_start_s'])+.15)*100));z=int(np.floor((float(r['source_end_s'])-.15)*100))
                    if z<=a:continue
                    pitch=int(r['source_midi'])
                    if pitch>0:valid[a:z]=True;target[a:z]=pitch
                    else:rest[a:z]=True
                extras=0;multi=0;missing=0;note_counts=[]
                for w in words:
                    a=w['begin']*1000+50;z=w['end']*1000-50
                    if z<=a:continue
                    events=[n for n in ns if min(z,n['start_ms']+n['duration_ms'])-max(a,n['start_ms'])>70]
                    # Count meaningful pitch changes, not just different event IDs.
                    pitches=[]
                    for n in events:
                        if not pitches or pitches[-1]!=n['midi']:pitches.append(n['midi'])
                    extras+=max(0,len(pitches)-1);multi+=len(pitches)>1;missing+=len(pitches)==0
                    note_counts.append({'char':w['char'],'start_ms':round(a-50),'end_ms':round(z+50),'pitches':pitches})
                row.update(stable_interior_seconds=round(valid.sum()/100,2),
                           reference_interior_pitch_agreement=round(float(np.mean(predicted[valid]==target[valid])),4),
                           interior_coverage=round(float(np.mean(predicted[valid]>0)),4),
                           rest_false_voice=round(float(np.mean(predicted[rest]>0)),4),
                           audited_words=len(note_counts),multi_pitch_words=multi,extra_word_pitch_changes=extras,missing_words=missing)
                if name=='zuguo':
                    later=valid & (np.arange(len(predicted))*10>=87090)
                    row['after_first40_agreement']=round(float(np.mean(predicted[later]==target[later])),4)
                (B/f'{name}_{model}_word_audit.json').write_text(json.dumps(note_counts,ensure_ascii=False,indent=2),encoding='utf8')
            rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (B/'diagnostics.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
