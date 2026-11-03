"""Audio-only joint word/pitch inference and source-clock alignment.

Existing acoustic caches are reused; curated song notes/lyrics are never read.
All file-name routing is outside the engine and has no influence on inference.
"""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
from benchmark_oss_vocals import inputs
from game_vocal_engine import context_cuts
from vocalparse_pitch_engine import VocalParseEngine
from vocalparse_time_alignment import align_units
from transcribe_vocal_oss import write_notes,write_midi,render,encode_audio
from evaluate_oss_vocals import read_notes
from recording_tonality import infer_collection

R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_90_20261029'
PRE=R/'build/vocal_syllable_main_20261029';PITCH=R/'build/vocal_pitch_grounded_20261029'

def crop_voiced(pcm,evidence,a,z):
    r=np.asarray(evidence['rmvpe']);s=a//10;e=min(len(r),(z+9)//10)
    rms=np.array([np.sqrt(np.mean(pcm[k*160:min(len(pcm),(k+1)*160)].astype(float)**2)) for k in range(s,e)])
    floor=max(.00002,float(np.quantile(rms,.9))*.04)
    active=(r[s:e]>50)&(rms>floor)
    if active.sum()<max(15,.1*(e-s)):return None
    k=np.flatnonzero(active)
    begin=max(a,(s+int(k[0]))*10-180);end=min(z,(s+int(k[-1])+1)*10+180)
    if end-begin<250:return None
    return begin,end

def quiet_split(pcm,a,z):
    center=(a+z)//2;lo=max(a+1500,center-1600);hi=min(z-1500,center+1600)
    slots=np.arange(lo//20,hi//20)*20
    if not len(slots):return center//20*20
    energy=[np.mean(pcm[max(a*16,int(k)*16-800):min(z*16,int(k)*16+800)].astype(float)**2) for k in slots]
    return int(slots[int(np.argmin(energy))])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='');parser.add_argument('--include-windows',action='store_true')
    parser.add_argument('--policy',choices=['raw','fused'],default='raw')
    parser.add_argument('--cache-only',action='store_true',help='Never initialize a GPU model; report missing inference caches.')
    args=parser.parse_args();engine=None;cache=B/'inference_cache';cache.mkdir(exist_ok=True)
    engine_sha=hashlib.sha256((R/'scripts/vocalparse_pitch_engine.py').read_bytes()).hexdigest()
    weight_sha=json.loads((B/'checkpoint/sha256.json').read_text(encoding='utf8'))['model.safetensors']
    all_results=[]
    for name,window,path,offset in inputs():
        key=name+'/'+window
        if args.only and args.only not in key:continue
        if not args.include_windows and window!='full':continue
        d=B/name/window/args.policy;d.mkdir(parents=True,exist_ok=True)
        pcm=np.fromfile(path,dtype='<f4');evidence=dict(np.load(PRE/name/window/'evidence.npz'))
        pesto=dict(np.load(PITCH/name/window/'pesto.npz'));cuts=context_cuts(pcm)
        tonality=infer_collection(read_notes(PRE/name/window/'notes.csv'))
        pending=[]
        for a,z in zip(cuts,cuts[1:]):
            if z-a>12000:
                mid=quiet_split(pcm,a,z);pending.extend([(a,mid,0),(mid,z,0)])
            else:pending.append((a,z,0))
        all_notes=[];all_unfiltered=[];chunks=[];start=time.perf_counter()
        for a,z,depth in pending:
            bounds=crop_voiced(pcm,evidence,a,z)
            if bounds is None:chunks.append({'core_ms':[a,z],'skipped':'no_acoustic_voice'});continue
            begin,end=bounds;x=pcm[begin*16:end*16]
            digest=hashlib.sha256(x.tobytes()).hexdigest()
            signature=hashlib.sha256(json.dumps([digest,engine_sha,weight_sha,768]).encode()).hexdigest();dst=cache/(signature+'.json')
            if dst.exists():result=json.loads(dst.read_text(encoding='utf8'));hit=True
            else:
                if args.cache_only:
                    print('deferred inference cache',key,begin,end,flush=True)
                    chunks.append({'core_ms':[a,z],'crop_ms':[begin,end],'deferred_missing_cache':True})
                    continue
                if engine is None:engine=VocalParseEngine()
                print('infer',key,begin,end,flush=True);result=engine.infer(x);hit=False
                dst.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
            if result.get('parsed') and not result['token_limit_reached']:
                ev={k:v[begin//10:(end+9)//10] for k,v in evidence.items()}
                pe={k:v[begin//10:(end+9)//10] for k,v in pesto.items() if k!='probabilities'}
                if args.policy=='fused':
                    from vocalparse_acoustic_fusion import decode_fused
                    notes,audit=decode_fused(x,result['parsed'],ev,pe,tonality)
                else:notes,audit=align_units(x,result['parsed'],ev,pe)
            else:notes=[];audit={'accepted':False,'reason':'empty_or_truncated_model_output'}
            row={'core_ms':[a,z],'crop_ms':[begin,end],'cache_hit':hit,'inference_cache':str(dst),'alignment':audit,
                 'parsed':result.get('parsed'),'source_pcm_sha256':digest,'runtime_seconds':result['runtime_seconds']}
            retry=not audit['accepted'] and depth<2 and z-a>5000
            if retry:
                mid=quiet_split(pcm,a,z);pending.extend([(a,mid,depth+1),(mid,z,depth+1)])
                row['retried_with_smaller_chunks']=True
            else:
                for n in notes:
                    shifted={**n,'start_ms':n['start_ms']+begin};all_unfiltered.append(shifted)
                    if audit['accepted']:all_notes.append(shifted)
            chunks.append(row);print('done',key,begin,end,'units',len(notes),'accepted',audit['accepted'],flush=True)
            (d/'chunks.json').write_text(json.dumps(chunks,ensure_ascii=False,indent=2),encoding='utf8')
        all_notes.sort(key=lambda n:n['start_ms'])
        assert all(a['start_ms']+a['duration_ms']<=b['start_ms'] for a,b in zip(all_notes,all_notes[1:]))
        write_notes(all_notes,d/'notes.csv');write_notes(all_unfiltered,d/'unfiltered_notes.csv')
        write_midi(all_notes,d/'candidate_source_clock.mid')
        ms=len(pcm)//16;synth=render(all_notes,ms)
        media=[encode_audio(np.column_stack([pcm[:len(synth)],synth]),d/'source_left_candidate_right.mp3')]
        if all_notes:
            a=all_notes[0]['start_ms'];z=all_notes[-1]['start_ms']+all_notes[-1]['duration_ms']
            media.append(encode_audio(synth[a*16:z*16],d/'candidate_detected_vocals.mp3'))
        info={'name':name,'window':window,'source_ms':ms,'source_offset_seconds':offset,'notes':len(all_notes),
              'input_file':str(path),'input_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),
              'rejected_or_uncertain_chunks':sum(not q.get('alignment',{}).get('accepted',True) and not q.get('retried_with_smaller_chunks') for q in chunks),
              'model':'VocalParse-1.7B audio-only','model_sha256':weight_sha,'runtime_seconds':time.perf_counter()-start,
              'deferred_missing_inference_caches':sum(q.get('deferred_missing_cache',False) for q in chunks),
              'media':media,'human_listening_accepted':False,'real_world_pitch_accuracy_verified':False,
              'lyrics_or_score_supplied':False,'not_apk_release':True}
        (d/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
        all_results.append(info)
    (B/('results_'+args.policy+'.json')).write_text(json.dumps(all_results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
