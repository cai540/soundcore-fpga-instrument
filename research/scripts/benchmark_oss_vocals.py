"""Run trained open-source models on exact PCM already used by App 0.9.
References, lyrics and filenames are never passed to a model.
"""
from pathlib import Path
import sys,os,json,csv,time,hashlib,subprocess,argparse
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_oss_20261029';OLD=R/'build/vocal_final_phrases_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def inputs():
    items=json.loads((OLD/'audio_results.json').read_text(encoding='utf8'));tasks=[]
    for name in ['zuguo','chilege','qiansixi','lantingxu']:
        chunks=sorted([q for q in items if q['name']==name and q['window'].startswith('chunk_')],key=lambda q:q['offset_seconds'])
        a=np.concatenate([np.fromfile(Path(q['new'])/'analysis.f32',dtype='<f4') for q in chunks])
        p=B/'inputs'/name/'full.f32';p.parent.mkdir(parents=True,exist_ok=True);a.tofile(p)
        tasks.append((name,'full',p,0))
        q=next(q for q in items if q['name']==name and q['window']=='first40')
        tasks.append((name,'first40',Path(q['new'])/'analysis.f32',q['offset_seconds']))
    for name in ['tigers','twinkle','tigers_holdout','twinkle_holdout']:
        tasks.append((name,'nursery',OLD/'audio'/name/'nursery/analysis.f32',0))
    return tasks
def write_notes(ns,p):
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence']);w.writeheader();w.writerows(ns)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=['rosvot','basic','game_medium','game_small'],required=True)
    parser.add_argument('--only',default='');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--profile',choices=['cli','checkpoint','game_cli'],default='cli');args=parser.parse_args()
    run_name=args.model if args.profile=='cli' else args.model+'_'+args.profile
    if args.model=='rosvot':
        from oss_vocal_engine import RosvotEngine
        engine=RosvotEngine(profile=args.profile);model_info={'model':'ROSVOT+RWBD+RMVPE','profile':args.profile,'weights':engine.weights}
    elif args.model.startswith('game_'):
        from game_vocal_engine import GameOnnxEngine
        engine=GameOnnxEngine(size=args.model.split('_')[1],boundary_threshold=.3 if args.profile=='game_cli' else .2)
        model_info={'model':'OpenVPI GAME ONNX 1.0.3','weights':engine.weights}
    else:
        sys.path.insert(0,str(B/'basic-pitch'))
        from basic_pitch.inference import predict,Model
        path=B/'basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx'
        engine=Model(path);model_info={'model':'Basic Pitch ONNX, official default postprocessing','weights_sha256':sha(path)}
    results=[]
    for name,window,pcm_file,offset in inputs():
        key=name+'/'+window
        if args.only and args.only not in key:continue
        d=B/run_name/name/window;d.mkdir(parents=True,exist_ok=True)
        if args.resume and (d/'result.json').exists():
            results.append(json.loads((d/'result.json').read_text(encoding='utf8')));print('cached',key,flush=True);continue
        pcm=np.fromfile(pcm_file,dtype='<f4');begin=time.perf_counter()
        print('start',args.model,key,len(pcm)/16000,flush=True)
        if args.model=='rosvot' or args.model.startswith('game_'):
            ns,trace=engine.recognize(pcm,lambda i,n:print(key,'chunk',i,'/',n,flush=True))
            (d/'trace.json').write_text(json.dumps(trace),encoding='utf8')
        else:
            import soundfile as sf
            wav=d/'input.wav';sf.write(wav,pcm,16000,subtype='FLOAT')
            raw,midi,events=predict(wav,engine)
            midi.write(str(d/'upstream_polyphonic.mid'))
            np.savez_compressed(d/'activations.npz',**raw)
            ns=[{'start_ms':round(s*1000),'duration_ms':round((e-s)*1000),'midi':int(m),'confidence':float(c)} for s,e,m,c,*_ in events]
            ns.sort(key=lambda n:(n['start_ms'],n['midi']))
        write_notes(ns,d/'notes.csv')
        result={'name':name,'window':window,'offset_seconds':offset,'input_file':str(pcm_file),'input_sha256':sha(pcm_file),
            'source_ms':len(pcm)//16,'notes':len(ns),'runtime_seconds':time.perf_counter()-begin,**model_info}
        (d/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');results.append(result)
        print('done',key,len(ns),round(result['runtime_seconds'],2),'seconds',flush=True)
    (B/f'{run_name}_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
