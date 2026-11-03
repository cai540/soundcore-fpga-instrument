"""Use the singing model at its published native waveform sample rate.

No downsampling through the legacy App PCM. No external pitch classifier,
score, lyric or known note count is fed to the model.
"""
from pathlib import Path
import argparse,gc,hashlib,json,subprocess,time
import numpy as np
from scipy.signal import resample_poly
from game_vocal_engine import GameOnnxEngine
from transcribe_vocal_oss import write_notes,write_midi
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v9_20261029'

def infer(engine,wav,steps):
    start=time.perf_counter();duration=np.array([wav.shape[-1]/engine.rate],np.float32)
    xs,xe,mask=engine.sessions['encoder'].run(None,{'waveform':wav,'duration':duration})
    known=np.zeros(mask.shape,bool);bd=known.copy()
    params={'x_seg':xs,'known_boundaries':known,'maskT':mask,'threshold':np.array(.2,np.float32),'radius':np.array(2,np.int64),
            'language':np.array([engine.config['languages']['zh']],np.int64)}
    for t in np.arange(steps,dtype=np.float32)/steps:
        params.update(prev_boundaries=bd,t=np.array([t],np.float32))
        bd=engine.sessions['segmenter'].run(None,params)[0]
    ds,nmask=engine.sessions['bd2dur'].run(None,{'boundaries':bd,'maskT':mask})
    presence,pitch=engine.sessions['estimator'].run(None,{'x_est':xe,'boundaries':bd,'maskT':mask,'maskN':nmask,'threshold':np.array(.2,np.float32)})
    result=[];regions=[];cursor=0.
    for d,on,p,valid in zip(ds[0],presence[0],pitch[0],nmask[0]):
        if not valid:break
        a=round(cursor*1000);cursor+=float(d);z=min(round(cursor*1000),round(float(duration[0])*1000))
        n={'start_ms':a,'duration_ms':z-a,'midi':int(np.floor(p+.5)) if on else 0,'confidence':0.}
        regions.append({**n,'continuous_midi':float(p)})
        if on and z>a:result.append(n)
    return result,{'regions':regions,'boundary_frames':np.flatnonzero(bd[0]).tolist(),'runtime_seconds':time.perf_counter()-start}

def main():
    rows=[]
    for name,leaf,start in [('zuguo','wodezuguo_vocals_20261026.mp3',47.09),('qiansixi','qiansixi_vocals_20261026.mp3',23.99)]:
        native=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(R/'songs/source'/leaf),'-ac','1','-ar','44100','-f','f32le','-']),dtype='<f4').copy()
        native=native[round(start*44100):round((start+16)*44100)]
        old=np.fromfile(B/'input_ab'/name/'legacy_resampled/input.f32',dtype='<f4')
        legacy=resample_poly(old,441,160).astype(np.float32)
        for tag,pcm,steps in [('native_8',native,8),('native_32',native,32),('legacy_8',legacy,8)]:
            engine=GameOnnxEngine('medium',steps=steps);notes,trace=infer(engine,pcm[None,:],steps)
            out=B/'game_native'/name/tag;out.mkdir(parents=True,exist_ok=True)
            write_notes(notes,out/'notes.csv');write_midi(notes,out/'raw.mid')
            info={'name':name,'mode':tag,'sample_rate':44100,'steps':steps,'notes':len(notes),'source_start_s':start,
                  'source_pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),'legacy_app_resampler_used':tag.startswith('legacy'),
                  'reference_or_lyrics_used':False,'runtime_seconds':trace['runtime_seconds']}
            (out/'trace.json').write_text(json.dumps(trace,indent=2));(out/'result.json').write_text(json.dumps(info,indent=2));rows.append(info)
            print(info,flush=True);del engine;gc.collect()
    (B/'game_native/results.json').write_text(json.dumps(rows,indent=2))

if __name__=='__main__':main()
