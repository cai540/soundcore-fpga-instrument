"""Experimental audio-to-note CLI, independent of the four evaluation songs.

Runs the frozen syllable frontend, then adds independent pitch evidence.
No score/reference/lyric dataset is read. This is not an Android release.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
import numpy as np
from scipy.signal import resample_poly
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes,write_midi,render,encode_audio,device_fit
from melodic_pitch_refiner import refine
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029'
VERSION='melody-register-and-periodic-center-candidate1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('audio',type=Path,nargs='?')
    parser.add_argument('--output',type=Path);parser.add_argument('--start',type=float,default=0)
    parser.add_argument('--duration',type=float,default=0);parser.add_argument('--pitch-worker',type=Path)
    args=parser.parse_args()
    if args.pitch_worker:
        import torch,pesto
        from extract_pitch_grounding import pesto_extract
        torch.set_num_threads(6)
        model=pesto.load_model('mir-1k_g7',step_size=10.,sampling_rate=16000)
        pcm=np.fromfile(args.pitch_worker/'audio.f32',dtype='<f4')
        np.savez_compressed(args.pitch_worker/'pesto.npz',**pesto_extract(model,pcm));return
    if args.audio is None or args.output is None:parser.error('audio and --output are required')
    out=args.output;out.mkdir(parents=True,exist_ok=True);base=out/'base_syllables'
    subprocess.run([sys.executable,str(R/'scripts/transcribe_syllable_main.py'),str(args.audio),
                    '--output',str(base),'--start',str(args.start),'--duration',str(args.duration)],check=True)
    info=json.loads((base/'result.json').read_text(encoding='utf8'));old_cache=Path(info['cache_directory'])
    pcm=np.fromfile(old_cache/'audio.f32',dtype='<f4')
    assert hashlib.sha256(pcm.tobytes()).hexdigest()==info['pcm_sha256']
    weights=[B/'extra/pesto/weights/mir-1k_g7.ckpt',B/'essentia_js/package/dist/essentia-wasm.umd.js',
             B/'essentia_js/package/dist/essentia.js-core.umd.js',R/'scripts/extract_melodia_pitch.cjs',
             R/'scripts/extract_pitch_grounding.py']
    signatures={str(p.relative_to(R)):sha(p) for p in weights}
    key=hashlib.sha256(json.dumps([info['pcm_sha256'],signatures,'pesto10ms-melodia128-44k1-v1'],sort_keys=True).encode()).hexdigest()
    cache=B/'local_cache'/key;cache.mkdir(parents=True,exist_ok=True)
    cache_hit=(cache/'pesto.npz').exists() and (cache/'melodia.npz').exists()
    pcm.tofile(cache/'audio.f32')
    if not (cache/'pesto.npz').exists():
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--pitch-worker',str(cache)],check=True)
    if not (cache/'melodia.npz').exists():
        resample_poly(pcm,441,160).astype('<f4').tofile(cache/'audio_44100.f32')
        subprocess.run(['D:/node.js/node.exe',str(R/'scripts/extract_melodia_pitch.cjs'),
                        str(cache/'audio_44100.f32'),str(cache/'melodia_raw')],check=True)
        f=np.fromfile(cache/'melodia_raw.pitch.f32',dtype='<f4')
        c=np.fromfile(cache/'melodia_raw.pitchConfidence.f32',dtype='<f4')
        grid=np.arange((len(pcm)+159)//160)*.01
        idx=np.clip(np.rint(grid*44100/128).astype(int),0,len(f)-1)
        np.savez_compressed(cache/'melodia.npz',f0=f[idx],confidence=c[idx])
    notes=read_notes(base/'notes.csv');evidence=np.load(old_cache/'evidence.npz')
    pesto=np.load(cache/'pesto.npz');melodia=np.load(cache/'melodia.npz')
    new,audit=refine(notes,pcm,evidence['rmvpe'],pesto['midi'],pesto['confidence'],melodia['f0'])
    assert [(n['start_ms'],n['duration_ms']) for n in new]==[(n['start_ms'],n['duration_ms']) for n in notes]
    write_notes(new,out/'notes.csv');write_midi(new,out/'melody_source_clock.mid')
    synthesized=render(new,info['source_ms'])
    media=[encode_audio(synthesized,out/'melody_full_clock.mp3'),
           encode_audio(np.column_stack([pcm[:len(synthesized)],synthesized]),out/'voice_left_candidate_right.mp3')]
    (out/'pitch_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    result={**info,'version':VERSION,'base_version':info['version'],'pitch_weights_sha256':signatures,
            'pitch_cache_directory':str(cache),'pitch_cache_hit':cache_hit,'pitch_changes':audit['changes'],
            'timing_unchanged':True,'media':media,'device_mapping':device_fit(new,info['source_ms']),
            'human_listening_accepted':False,'not_android_release':True,'pitch_quality_still_unaccepted':True}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',out.resolve(),'pitch changes',audit['changes'],'cache',cache_hit,flush=True)

if __name__=='__main__':main()
