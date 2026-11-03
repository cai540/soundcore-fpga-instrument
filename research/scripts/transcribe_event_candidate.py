"""Generic local event-transcription candidate; no song/lyric database.

The CPU and CUDA environments stay separate. Content-addressed caches store
acoustic observations and actual model events, never editorial answers.
This is a desktop research entry point, not the Android implementation.
"""
from pathlib import Path
import argparse,hashlib,inspect,json,os,subprocess,sys
import numpy as np
from transcribe_vocal_oss import decode_audio,write_notes,write_midi,render,encode_audio
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'
CPU=R/'build/vocal_oss_20261029/venv/Scripts/python.exe'
GPU=R/'build/vocal_pitch_90_20261029/venv/Scripts/python.exe'
VERSION='complete-interval-research-v8'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while block:=f.read(4*1024**2):h.update(block)
    return h.hexdigest()

def worker(kind,cache):
    pcm=np.fromfile(cache/'audio.f32',dtype='<f4')
    if kind in ('medium','large'):
        from muscriptor_public_engine import MuscriptorEngine
        ns,events,midi,info=MuscriptorEngine(kind,'float16').recognize(pcm,('voice',),lambda i,n:print(kind,i,'/',n,flush=True))
        (cache/f'{kind}.raw.json').write_text(json.dumps(ns),encoding='utf8')
        (cache/f'{kind}.events.json').write_text(json.dumps(events),encoding='utf8')
        (cache/f'{kind}.info.json').write_text(json.dumps(info,indent=2),encoding='utf8')
    elif kind=='evidence':
        from syllable_vocal_evidence import SyllableEvidenceExtractor
        np.savez_compressed(cache/'evidence.npz',**SyllableEvidenceExtractor().extract(pcm))
    elif kind=='pesto':
        from extract_pitch_grounding import pesto_extract
        import torch,pesto
        torch.set_num_threads(6)
        model=pesto.load_model('mir-1k_g7',step_size=10.,sampling_rate=16000)
        np.savez_compressed(cache/'pesto.npz',**pesto_extract(model,pcm))
    elif kind=='crepe':
        from extract_crepe_evidence import extract
        extract(pcm,cache)
    elif kind=='basic':
        import soundfile as sf
        sys.path.insert(0,str(R/'build/vocal_oss_20261029/basic-pitch'))
        from basic_pitch.inference import predict,Model
        sf.write(cache/'input.wav',pcm,16000,subtype='FLOAT')
        weights=R/'build/vocal_oss_20261029/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx'
        data,_,_=predict(cache/'input.wav',Model(weights));np.savez_compressed(cache/'basic.npz',**data)

def invoke(kind,cache,gpu=False):
    env=dict(os.environ);extra=R/'build/vocal_oss_20261029/extra'
    env['PYTHONPATH']=str(R/'scripts') if gpu else str(extra)+os.pathsep+str(R/'scripts')
    env['PYTHONIOENCODING']='utf-8'
    subprocess.run([str(GPU if gpu else CPU),'-u',str(Path(__file__).resolve()),'--worker',kind,'--cache',str(cache)],
                   env=env,cwd=R,check=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path,nargs='?');p.add_argument('--output',type=Path)
    p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=0)
    p.add_argument('--worker',choices=['medium','large','evidence','pesto','basic','crepe']);p.add_argument('--cache',type=Path)
    args=p.parse_args()
    if args.worker:
        if not args.cache:p.error('--worker needs --cache')
        worker(args.worker,args.cache);return
    if args.audio is None or args.output is None:p.error('audio and --output are required')
    if args.start<0 or args.duration<0:p.error('nonnegative start/duration required')
    pcm=decode_audio(args.audio);a=round(args.start*16000);z=a+round(args.duration*16000) if args.duration else len(pcm)
    pcm=pcm[a:z].astype(np.float32)
    if pcm.ndim!=1 or not 1600<=len(pcm)<=16000*600 or not np.isfinite(pcm).all():
        p.error('finite mono audio of 0.1 to 600 seconds required')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    assets=[B/f'weights/muscriptor-{s}-f16.gguf' for s in ['medium','large']]
    assets+=[R/'build/vocal_oss_20261029/ROSVOT/checkpoints/rmvpe/model.pt',
             R/'build/vocal_oss_20261029/ROSVOT/checkpoints/rwbd/model.pt',
             R/'build/vocal_syllable_main_20261029/extra/torchfcpe/assets/fcpe_c_v001.pt',
             R/'build/vocal_pitch_grounded_20261029/extra/pesto/weights/mir-1k_g7.ckpt',
             R/'build/vocal_oss_20261029/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx',
             R/'build/vocal_pitch_90_20261029/venv/Lib/site-packages/torchcrepe/assets/full.pth']
    assets+=sorted((R/'build/vocal_oss_20261029/game_models/medium').rglob('*.onnx'))
    assets+=[R/'scripts'/f for f in ['muscriptor_public_engine.py','syllable_vocal_evidence.py','extract_pitch_grounding.py',
                                   'extract_crepe_evidence.py','estimate_pitch_contexts.py']]
    fingerprints={str(q.relative_to(R)):sha(q) for q in assets}
    # Decoder/orchestration edits must not invalidate expensive acoustic
    # observations. Only the actual worker and extractor code enters this key.
    fingerprints['worker_function_sha256']=hashlib.sha256(inspect.getsource(worker).encode()).hexdigest()
    source_sha=hashlib.sha256(pcm.tobytes()).hexdigest()
    key=hashlib.sha256(json.dumps([source_sha,fingerprints,'16k-voice-events-f16-prelude-1'],sort_keys=True).encode()).hexdigest()
    cache=B/'local_cache'/key;cache.mkdir(parents=True,exist_ok=True);pcm.tofile(cache/'audio.f32')
    required={'evidence':'evidence.npz','pesto':'pesto.npz','basic':'basic.npz','crepe':'crepe.npz',
              'medium':'medium.raw.json','large':'large.raw.json'}
    hit=all((cache/f).exists() for f in required.values()) and all((cache/f'{s}.info.json').exists() for s in ('medium','large'))
    # Fail a worker before consuming a partial result. Workers emit raw JSON
    # before their metadata, so metadata is checked separately too.
    for kind,leaf in required.items():
        complete=(cache/leaf).exists()
        if kind in ('medium','large'):complete=complete and (cache/f'{kind}.info.json').exists()
        if not complete:invoke(kind,cache,kind in ('medium','large','crepe'))
    from syllable_vocal_decoder import acoustic_features
    from monophonic_note_lattice import decode_lattice
    from transcription_event_consensus import consensus_events
    from estimate_pitch_contexts import ContextualGamePitchEstimator
    e=np.load(cache/'evidence.npz');pp=np.load(cache/'pesto.npz');bp=np.load(cache/'basic.npz');cr=np.load(cache/'crepe.npz')
    if not (cache/'acoustic.npz').exists():np.savez_compressed(cache/'acoustic.npz',**acoustic_features(pcm))
    ac=np.load(cache/'acoustic.npz');raw=json.loads((cache/'medium.raw.json').read_text());alt=json.loads((cache/'large.raw.json').read_text())
    schedule,lattice=decode_lattice(raw,alt,e,pp,bp,ac)
    signature=hashlib.sha256(json.dumps([(n['start_ms'],n['duration_ms']) for n in schedule]).encode()).hexdigest()
    context=cache/'contexts'/signature;context.mkdir(parents=True,exist_ok=True);views=[];engine=None
    for width,offset in [(4000,0),(4000,2000),(8000,0)]:
        dst=context/f'{width}_{offset}.npz'
        if not dst.exists():
            if engine is None:engine=ContextualGamePitchEstimator()
            np.savez_compressed(dst,**engine.predict(pcm,schedule,width,offset))
        q=np.load(dst);v=q['midi'].copy();v[~q['present']]=np.nan;views.append(v)
    notes,audit=consensus_events(raw,alt,views,e,pp,cr,bp,note_schedule=schedule)
    from periodic_vowel_events import collapse_periodic_vowels
    notes,periodic=collapse_periodic_vowels(notes,e,pp)
    ms=len(pcm)//16
    from package_vocal_oss import validate,verify_midi
    validate(notes,ms);write_notes(notes,out/'notes.csv');write_midi(notes,out/'source_clock.mid');verify_midi(out/'source_clock.mid',notes)
    synth=render(notes,ms);media=[encode_audio(synth,out/'melody.mp3'),
                                 encode_audio(np.column_stack([pcm[:len(synth)],synth]),out/'voice_left_melody_right.mp3')]
    (out/'lattice_audit.json').write_text(json.dumps(lattice,indent=2),encoding='utf8')
    (out/'pitch_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
    (out/'periodic_vowel_audit.json').write_text(json.dumps(periodic,indent=2),encoding='utf8')
    result={'version':VERSION,'source_pcm_sha256':source_sha,'source_ms':ms,'source_offset_seconds':args.start,
            'cache_directory':str(cache),'acoustic_cache_hit':hit,'weights_and_extractor_sha256':fingerprints,
            'notes':len(notes),'media':media,'lyrics_score_or_song_identity_used':False,
            'real_world_90_percent_verified':False,'human_listening_accepted':False,
            'not_android_release':True,'fpga_programmed':False,
            'weight_license':'MuScriptor CC-BY-NC-4.0; weights not bundled in preview package'}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',out,'notes',len(notes),'cache_hit',hit,flush=True)

if __name__=='__main__':main()
