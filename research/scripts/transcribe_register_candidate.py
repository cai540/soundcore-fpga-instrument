"""Local generic research CLI; no song database or known transcript.

The two Python runtimes are deliberately isolated. Acoustic caches are keyed
by PCM, model hashes and extraction code; decoder edits reuse observations.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes,write_midi,render,encode_audio,device_fit
from register_candidate_pipeline import decode,VERSION
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_90_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path,nargs='?');p.add_argument('--output',type=Path)
    p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=0)
    p.add_argument('--crepe-worker',type=Path);args=p.parse_args()
    if args.crepe_worker:
        from extract_crepe_evidence import extract
        extract(np.fromfile(args.crepe_worker/'audio.f32',dtype='<f4'),args.crepe_worker);return
    if args.audio is None or args.output is None:p.error('audio and --output are required')
    out=args.output;out.mkdir(parents=True,exist_ok=True);base=out/'base_pitch'
    subprocess.run([sys.executable,str(R/'scripts/transcribe_melodic_pitch.py'),str(args.audio),
                    '--output',str(base),'--start',str(args.start),'--duration',str(args.duration)],check=True)
    info=json.loads((base/'result.json').read_text(encoding='utf8'));old_cache=Path(info['cache_directory'])
    pitch_cache=Path(info['pitch_cache_directory']);pcm=np.fromfile(old_cache/'audio.f32',dtype='<f4')
    assert hashlib.sha256(pcm.tobytes()).hexdigest()==info['pcm_sha256']
    notes=read_notes(base/'notes.csv')
    assets=[R/'build/vocal_oss_20261029/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx',
            B/'venv/Lib/site-packages/torchcrepe/assets/full.pth',
            R/'scripts/estimate_pitch_contexts.py',R/'scripts/extract_crepe_evidence.py']
    signatures={str(q.relative_to(R)):sha(q) for q in assets}
    boundaries=[(q['start_ms'],q['duration_ms']) for q in notes]
    key=hashlib.sha256(json.dumps([info['pcm_sha256'],signatures,boundaries,info['weights_sha256'],
                                   'basic-pitch-official-clock-crepe-full-global-10ms-contexts-v1'],sort_keys=True).encode()).hexdigest()
    cache=B/'local_cache'/key;cache.mkdir(parents=True,exist_ok=True);pcm.tofile(cache/'audio.f32')
    leaves=['basic.npz','crepe.npz','context_4000_0.npz','context_4000_2000.npz','context_8000_0.npz']
    hit=all((cache/q).exists() for q in leaves)
    if not (cache/'basic.npz').exists():
        sys.path.insert(0,str(R/'build/vocal_oss_20261029/basic-pitch'))
        from basic_pitch.inference import predict,Model
        import soundfile as sf
        sf.write(cache/'model_input.wav',pcm,16000,subtype='FLOAT')
        raw,_,_=predict(cache/'model_input.wav',Model(assets[0]));np.savez_compressed(cache/'basic.npz',**raw)
    if not (cache/'crepe.npz').exists():
        env=dict(os.environ);env['PYTHONPATH']=str(R/'scripts');env['PYTHONIOENCODING']='utf-8'
        subprocess.run([str(B/'venv/Scripts/python.exe'),str(Path(__file__).resolve()),'--crepe-worker',str(cache)],env=env,check=True)
    estimator=None;views=[]
    for size,offset in [(4000,0),(4000,2000),(8000,0)]:
        dst=cache/f'context_{size}_{offset}.npz'
        if not dst.exists():
            if estimator is None:
                from estimate_pitch_contexts import ContextualGamePitchEstimator
                estimator=ContextualGamePitchEstimator()
            np.savez_compressed(dst,**estimator.predict(pcm,notes,size,offset))
        views.append(np.load(dst)['midi'])
    output,audit=decode(notes,views,np.load(old_cache/'evidence.npz'),np.load(pitch_cache/'pesto.npz'),
                        np.load(cache/'crepe.npz'),np.load(cache/'basic.npz'),np.load(old_cache/'acoustic.npz'))
    write_notes(output,out/'notes.csv');write_midi(output,out/'melody_source_clock.mid')
    synth=render(output,info['source_ms']);media=[encode_audio(synth,out/'melody_full_clock.mp3'),
                encode_audio(np.column_stack([pcm[:len(synth)],synth]),out/'voice_left_candidate_right.mp3')]
    (out/'selection_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    result={**info,'version':VERSION,'additional_weights_and_extractor_sha256':signatures,
            'register_cache_directory':str(cache),'register_cache_hit':hit,'additional_media':media,
            'output_notes':len(output),'device_mapping':device_fit(output,info['source_ms']),
            'lyrics_or_score_or_song_identity_used':False,'real_world_90_percent_verified':False,
            'human_listening_accepted':False,'not_android_release':True,'fpga_programmed':False}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',out.resolve(),'notes',len(output),'new evidence cache hit',hit,flush=True)

if __name__=='__main__':main()
