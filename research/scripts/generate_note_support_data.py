"""Synthetic ground truth only: no songs, lyrics, edited scores or pretrained note labels.

Oscillator synthesis and envelopes are standard DSP. The varied recordings and
candidate-evidence training task belong to this project, not an invention of DSP/MLP.
"""
from pathlib import Path
import hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/independent_note_support_20261101/data'
SR=16000

def synth(rng,split,index):
    timbre=index%6
    notes=[];windows=[];cursor=.18
    midi=int(rng.integers(45,83))
    for j in range(8):
        midi=int(np.clip(midi+int(rng.choice([-12,-7,-3,-2,-1,0,0,1,2,3,7,12])),42,88))
        duration=float(rng.uniform(.12,.85))
        if j==7:duration=.65
        start=round(cursor*SR);length=round(duration*SR)
        t=np.arange(length)/SR
        # Test uses nonzero detuning and wider vibrato not seen in training.
        detune=float(rng.uniform(-.12,.12)) if split=='test' else 0
        cents=float(rng.uniform(0,65 if split=='test' else 42))
        f=440*2**((midi-69+detune+cents/100*np.sin(2*np.pi*rng.uniform(3.5,7)*t))/12)
        phase=2*np.pi*np.cumsum(f)/SR+rng.uniform(0,2*np.pi)
        if timbre==0:partials=np.array([1.,0.,0.,0.])
        elif timbre==1:partials=np.array([1.,.5,.33,.25,.2,.16])
        elif timbre==2:partials=np.array([1.,0.,.45,0.,.2,0.,.1])
        elif timbre==3:partials=np.array([.1,1.,.6,.3,.15]) # weak fundamental
        elif timbre==4:partials=rng.uniform(.02,.8,7);partials[0]=.6
        else:partials=np.array([.5,.2,1.,.2,.5,.15])
        tone=sum(p*np.sin((h+1)*phase+rng.uniform(-.15,.15)) for h,p in enumerate(partials))
        attack=float(rng.uniform(.008,.06));release=float(rng.uniform(.02,.10))
        envelope=np.minimum(1,t/attack)*np.minimum(1,(duration-t)/release)
        tone=tone/max(1e-6,np.max(np.abs(tone)))*envelope*rng.uniform(.08,.7)
        notes.append((start,tone));windows.append(dict(start_ms=round(cursor*1000),duration_ms=round(duration*1000),midi=midi))
        gap=float(rng.choice([0,.04,.09,.18,.3]))
        if gap>=.18:
            windows.append(dict(start_ms=round((cursor+duration+.015)*1000),duration_ms=round((gap-.03)*1000),midi=-1))
        cursor+=duration+gap
    audio=np.zeros(round((cursor+.2)*SR))
    for start,tone in notes:audio[start:start+len(tone)]+=tone
    noise=rng.normal(size=len(audio))
    if split=='test': # correlated noise is a held-out perturbation
        noise=np.convolve(noise,[.6,.3,.1],mode='same')
    audio+=noise*rng.uniform(.0005,.025)
    if index%4==0:
        delay=int(.047*SR);audio[delay:]+=.13*audio[:-delay].copy()
    audio+=rng.uniform(-.008,.008)
    audio*=rng.choice([.035,.3,1.])
    return audio.astype('<f4'),windows,timbre

def main():
    OUT.mkdir(parents=True,exist_ok=True);clips=[]
    for split,count,seed in [('train',72,918273),('validation',18,198273),('test',24,771239)]:
        rng=np.random.default_rng(seed)
        for i in range(count):
            audio,windows,timbre=synth(rng,split,i)
            name=f'{split}_{i:03d}';path=OUT/f'{name}.f32';path.write_bytes(audio.tobytes())
            clips.append(dict(id=name,split=split,seed=seed,timbre=timbre,file=path.name,
                sample_rate=SR,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),windows=windows))
    manifest=dict(schema=1,source='project generated oscillator PCM; exact oscillator pitch/rest labels',
        real_recordings_used=False,partition='whole recording; independent PRNG seeds; test detuning/noise held out',clips=clips)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(clips=len(clips),windows=sum(len(c['windows']) for c in clips),seconds=sum((OUT/c['file']).stat().st_size/4/SR for c in clips))))

if __name__=='__main__':main()
