"""Diagnostic comparison only. No reference loaded by runtime inference."""
from pathlib import Path
import csv,json
import numpy as np
from evaluate_oss_vocals import read_notes,track
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--notes',default='notes.csv');parser.add_argument('--output',default='diagnostics.json');args=parser.parse_args()
    results=[]
    for name,ref in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi'),('lantingxu',None)]:
        d=B/name/'full'
        if not (d/args.notes).exists():continue
        info=json.loads((d/'result.json').read_text());old=read_notes(PRE/name/'full/notes.csv');new=read_notes(d/args.notes)
        length=info['source_ms'];o=track(old,length);n=track(new,length)
        old_intervals={(q['start_ms'],q['duration_ms']):q['midi'] for q in old}
        schedule_same=len(old)==len(new) and all((a['start_ms'],a['duration_ms'])==(b['start_ms'],b['duration_ms']) for a,b in zip(old,new))
        row={'name':name,'notes':len(new),'net_notes_added':len(new)-len(old),
             'changed_pitches_at_same_intervals':sum(old_intervals.get((q['start_ms'],q['duration_ms']),q['midi'])!=q['midi'] for q in new),
             'note_schedule_identical':schedule_same,'reference_kind':'prior_editorial_proxy_not_independent_gold',
             'real_world_90_percent_verified':False}
        if ref:
            refs=list(csv.DictReader((R/f'songs/product_song_review/{ref}.csv').open(encoding='utf8')))
            target=np.zeros(len(n),int);valid=np.zeros(len(n),bool)
            for q in refs:
                pitch=int(q['source_midi']);a=int(np.ceil((float(q['source_start_s'])+.12)*100));z=int(np.floor((float(q['source_end_s'])-.12)*100))
                if pitch>0 and z>a:target[a:z]=pitch;valid[a:z]=True
            for label,pred in [('old_v6',o),('new',n)]:
                err=abs(pred-target)
                row[label]={'voiced_interior_seconds':round(valid.sum()/100,2),'pitch_agreement':round(float(np.mean(err[valid]==0)),4),
                    'one_semitone_error_seconds':round(float(np.sum((err==1)&valid))/100,2),
                    'octave_error_seconds':round(float(np.sum((err==12)&valid))/100,2),
                    'other_pitch_error_seconds':round(float(np.sum((err!=0)&(err!=1)&(err!=12)&valid))/100,2)}
        results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (B/args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
