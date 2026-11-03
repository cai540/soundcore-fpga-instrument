"""CREPE full probabilities, with file-global decoding across GPU batches.

torchcrepe.predict decodes inside each inference batch. Here inference is
batched only for memory, then the official Viterbi decoder sees the entire
source time axis. All raw probabilities are cached for subsequent experiments.
"""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
import torch,torchcrepe
from benchmark_oss_vocals import inputs
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_90_20261029'

def extract(pcm,d):
    d.mkdir(parents=True,exist_ok=True);source_sha=hashlib.sha256(pcm.tobytes()).hexdigest()
    start=time.perf_counter();T=(len(pcm)+159)//160
    torch.manual_seed(0);np.random.seed(0)
    if (d/'crepe_probabilities.npz').exists():
        old=json.loads((d/'crepe_input.json').read_text(encoding='utf8'))
        if old['source_pcm_sha256']!=source_sha:raise RuntimeError('CREPE source cache mismatch')
        prob=np.load(d/'crepe_probabilities.npz')['probabilities'].astype(np.float32)
    else:
        blocks=[];audio=torch.from_numpy(pcm.copy())[None,:]
        with torch.inference_mode():
            for j,frames in enumerate(torchcrepe.preprocess(audio,16000,160,128,'cuda:0',True)):
                blocks.append(torchcrepe.infer(frames,'full','cuda:0').cpu().numpy())
                if j%40==0:print('CREPE batch',j,flush=True)
        prob=np.concatenate(blocks)[:T].astype(np.float32)
        np.savez_compressed(d/'crepe_probabilities.npz',probabilities=prob.astype(np.float16))
        (d/'crepe_input.json').write_text(json.dumps({'source_pcm_sha256':source_sha,'sample_rate':16000,'hop_samples':160,
            'model':'torchcrepe 0.0.24 full','probability_frames':len(prob),'batch_size':128},indent=2),encoding='utf8')
    frequencies=10*2**((np.arange(360)*20+1997.3794084376191)/1200)
    arg=frequencies[np.argmax(prob,axis=1)]
    values=torch.from_numpy(prob.T.copy()[None])
    # Silence carries no pitch evidence; do not let normalized silent windows
    # impose an arbitrary register on the next actual voiced phrase.
    padded=np.pad(pcm,(160,320));frames=np.lib.stride_tricks.sliding_window_view(padded,320)[::160][:T]
    rms=np.sqrt(np.mean(frames.astype(float)**2,axis=1));silence=rms<max(1e-5,float(np.quantile(rms,.9))*.02)
    values[:,:,silence]=0.
    print('global Viterbi frames',T,flush=True)
    pitch,periodicity=torchcrepe.postprocess(values,50.,1760.,torchcrepe.decode.viterbi,False,True)
    f0=pitch[0].numpy();confidence=periodicity[0].numpy();f0[silence]=0;confidence[silence]=0
    np.savez_compressed(d/'crepe.npz',f0=f0.astype(np.float32),periodicity=confidence.astype(np.float32),
                        argmax_f0=arg.astype(np.float32),rms=rms.astype(np.float32))
    info={'source_pcm_sha256':source_sha,'frames':T,'runtime_seconds':time.perf_counter()-start,
          'file_global_decoder':True,'inference_batches_not_decoding_boundaries':True,'fmin':50,'fmax':1760,
          'periodicity_is_not_pitch_accuracy':True}
    (d/'crepe_result.json').write_text(json.dumps(info,indent=2),encoding='utf8');print(info,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',default='');p.add_argument('--include-windows',action='store_true');a=p.parse_args()
    torch.set_num_threads(6)
    for name,window,path,offset in inputs():
        if a.only and a.only not in name+'/'+window:continue
        if not a.include_windows and window!='full':continue
        d=B/name/window
        if (d/'crepe.npz').exists():print('cached',name,window,flush=True);continue
        print('start',name,window,flush=True);extract(np.fromfile(path,dtype='<f4'),d)

if __name__=='__main__':main()
