"""General audio-to-main-note entry point. No song database or lyric input."""
from pathlib import Path
import argparse,gc,hashlib,json,subprocess,sys
import numpy as np
from transcribe_vocal_oss import decode_audio,write_notes,write_midi,render,encode_audio,device_fit
from syllable_vocal_decoder import acoustic_features,decode_syllables
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_syllable_main_20261029'
VERSION='syllable-main-v6-evidence1'
EVIDENCE_VERSION='RWBD-RMVPE-FCPE-v1-GAME-medium-0.2-8steps-acoustic-v1'

def main():
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path,nargs='?');p.add_argument('--output',type=Path)
    p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=0)
    p.add_argument('--extract-worker',type=Path);a=p.parse_args()
    if a.extract_worker:
        from syllable_vocal_evidence import SyllableEvidenceExtractor
        pcm=np.fromfile(a.extract_worker/'audio.f32',dtype='<f4')
        data=SyllableEvidenceExtractor().extract(pcm,lambda i,n:print('acoustic evidence',i,'/',n,flush=True))
        np.savez_compressed(a.extract_worker/'evidence.npz',**data);return
    if a.audio is None or a.output is None:p.error('audio and --output are required')
    if a.start<0 or a.duration<0:p.error('start and duration must be nonnegative')
    pcm=decode_audio(a.audio);start=round(a.start*16000);end=start+round(a.duration*16000) if a.duration else len(pcm)
    pcm=pcm[start:end].astype(np.float32);assert 1600<=len(pcm)<=16000*600,'audio must be 0.1 to 600 seconds'
    source_sha=hashlib.sha256(pcm.tobytes()).hexdigest()
    models=[R/'build/vocal_oss_20261029/ROSVOT/checkpoints/rmvpe/model.pt',
            R/'build/vocal_oss_20261029/ROSVOT/checkpoints/rwbd/model.pt',
            B/'extra/torchfcpe/assets/fcpe_c_v001.pt']
    models+=sorted((R/'build/vocal_oss_20261029/game_models/medium').rglob('*.onnx'))
    weight_hashes={str(q.relative_to(R)):hashlib.sha256(q.read_bytes()).hexdigest() for q in models}
    signature=hashlib.sha256(json.dumps([EVIDENCE_VERSION,source_sha,weight_hashes],sort_keys=True).encode()).hexdigest()
    cache=B/'local_cache'/signature;cache.mkdir(parents=True,exist_ok=True)
    pcm.tofile(cache/'audio.f32')
    cache_hit=(cache/'evidence.npz').exists() and (cache/'game_notes.json').exists() and (cache/'acoustic.npz').exists()
    if not (cache/'evidence.npz').exists():
        # Keep Torch and ONNX inference in separate processes. A successful
        # worker completion is required before cached evidence is consumed.
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--extract-worker',str(cache)],check=True)
    else:print('reuse acoustic model cache',flush=True)
    if not (cache/'game_notes.json').exists():
        from game_vocal_engine import GameOnnxEngine
        notes,trace=GameOnnxEngine(size='medium').recognize(pcm,lambda i,n:print('note evidence',i,'/',n,flush=True))
        (cache/'game_notes.json').write_text(json.dumps(notes),encoding='utf8')
        (cache/'game_trace.json').write_text(json.dumps(trace),encoding='utf8')
    game=json.loads((cache/'game_notes.json').read_text())
    if not (cache/'acoustic.npz').exists():np.savez_compressed(cache/'acoustic.npz',**acoustic_features(pcm))
    notes,audit=decode_syllables(pcm,dict(np.load(cache/'evidence.npz')),game,dict(np.load(cache/'acoustic.npz')))
    out=a.output;out.mkdir(parents=True,exist_ok=True)
    write_notes(notes,out/'notes.csv');write_midi(notes,out/'melody_source_clock.mid')
    synth=render(notes,len(pcm)//16)
    media=[encode_audio(synth,out/'melody_full_clock.mp3'),
           encode_audio(np.column_stack([pcm[:len(synth)],synth]),out/'voice_left_main_notes_right.mp3')]
    if notes:
        begin=notes[0]['start_ms'];finish=min(len(synth)//16,notes[-1]['start_ms']+notes[-1]['duration_ms'])
        media.append(encode_audio(synth[begin*16:finish*16],out/'melody_trimmed_to_detected_events.mp3'))
    info={'version':VERSION,'evidence_version':EVIDENCE_VERSION,'source_name':a.audio.name,'source_offset_seconds':a.start,'source_ms':len(pcm)//16,
          'pcm_sha256':source_sha,'weights_sha256':weight_hashes,'cache_directory':str(cache),'inference_cache_hit':cache_hit,
          'media':media,'device_mapping':device_fit(notes,len(pcm)//16),'actual_characters_recognized':False,
          'human_listening_accepted':False,'not_android_release':True}
    (out/'syllable_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',out.resolve(),flush=True)

if __name__=='__main__':main()
