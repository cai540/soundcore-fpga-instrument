"""Same PCM, same global decoder for full songs and short/held-out windows."""
from pathlib import Path
import json,time,hashlib
import numpy as np
from benchmark_oss_vocals import inputs
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from syllable_vocal_decoder import acoustic_features,decode_syllables
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_syllable_main_20261029';OLD=R/'build/vocal_oss_20261029'

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--only',default='');a=p.parse_args();results=[]
    for name,window,path,offset in inputs():
        key=name+'/'+window
        if a.only and a.only not in key:continue
        d=B/name/window;d.mkdir(parents=True,exist_ok=True)
        if not (d/'evidence.npz').exists():continue
        pcm=np.fromfile(path,dtype='<f4');evidence=dict(np.load(d/'evidence.npz'))
        game=read_notes(OLD/'game_medium'/name/window/'notes.csv')
        print('decode',key,flush=True);t=time.perf_counter()
        if not (d/'acoustic.npz').exists() or 'octave_penalty' not in np.load(d/'acoustic.npz').files:
            np.savez_compressed(d/'acoustic.npz',**acoustic_features(pcm))
        feat=dict(np.load(d/'acoustic.npz'))
        ns,audit=decode_syllables(pcm,evidence,game,feat)
        write_notes(ns,d/'notes.csv');(d/'syllable_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        info={'name':name,'window':window,'input_file':str(path),'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'source_ms':len(pcm)//16,'offset_seconds':offset,'notes':len(ns),'syllables':len(audit['syllables']),
              'ornaments':audit['ornaments_retained'],'runtime_decode_seconds':time.perf_counter()-t,
              'policy':audit['policy'],'references_used_in_inference':False}
        (d/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8');results.append(info)
        print('saved',key,len(ns),'syllables',info['syllables'],'ornaments',info['ornaments'],flush=True)
    (B/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
