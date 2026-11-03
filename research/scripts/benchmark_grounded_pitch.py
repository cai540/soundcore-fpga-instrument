"""Pitch-only experiment on all fixed v6 schedules, same policy everywhere."""
from pathlib import Path
import json,time
import numpy as np
from benchmark_oss_vocals import inputs
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from grounded_pitch_decoder import refine_pitch_schedule,refine_pitch_schedule_guarded
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--policy',choices=['lattice','guarded'],default='guarded');args=parser.parse_args()
    results=[]
    for name,window,path,offset in inputs():
        d=B/name/window
        if not (d/'pesto.npz').exists() or not (d/'world.npz').exists():continue
        print('pitch only',name,window,flush=True);start=time.perf_counter()
        pcm=np.fromfile(path,dtype='<f4');ns=read_notes(PRE/name/window/'notes.csv')
        cache=json.loads((d/'register_cache.json').read_text()) if (d/'register_cache.json').exists() else {}
        decoder=refine_pitch_schedule_guarded if args.policy=='guarded' else refine_pitch_schedule
        out,audit=decoder(pcm,ns,dict(np.load(PRE/name/window/'evidence.npz')),dict(np.load(d/'pesto.npz')),
                                      dict(np.load(d/'world.npz')),cache)
        assert [(n['start_ms'],n['duration_ms']) for n in ns]==[(n['start_ms'],n['duration_ms']) for n in out]
        write_notes(out,d/'notes.csv');(d/'pitch_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        (d/'register_cache.json').write_text(json.dumps(cache),encoding='utf8')
        info={'name':name,'window':window,'input_file':str(path),'offset_seconds':offset,'source_ms':len(pcm)//16,
              'notes':len(out),'changed_pitches':audit['changed'],'timing_unchanged':True,'runtime_seconds':time.perf_counter()-start}
        (d/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8');results.append(info)
        print('done',info,flush=True)
    (B/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
