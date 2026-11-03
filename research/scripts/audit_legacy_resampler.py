"""Measure alias leakage in the exact two-pole legacy streaming algorithm."""
from pathlib import Path
import json,numpy as np
from scipy.signal import lfilter,resample_poly
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v9_20261029'

def legacy_resample(x,rate):
    alpha=1. if rate==16000 else 1-np.exp(-2*np.pi*3800/rate)
    filtered=lfilter([alpha],[1,-(1-alpha)],lfilter([alpha],[1,-(1-alpha)],x)).astype(np.float32)
    n=int(np.floor((len(x)-1)*16000/rate))+1
    return np.interp(np.arange(n)*rate/16000,np.arange(len(x)),filtered).astype(np.float32)

def amplitude_at(x,hz):
    x=x[8000:];t=np.arange(len(x))/16000
    return float(2*abs(np.dot(x,np.exp(-2j*np.pi*hz*t)))/len(x))

def main():
    rows=[]
    for rate in [44100,48000]:
        for f in [440,15600]:
            x=np.sin(2*np.pi*f*np.arange(rate*2)/rate).astype(np.float32)
            old=legacy_resample(x,rate);new=resample_poly(x,16000//np.gcd(rate,16000),rate//np.gcd(rate,16000))
            alias=f if f<8000 else abs(f-16000)
            old_gain=amplitude_at(old,alias);new_gain=amplitude_at(new,alias)
            row={'input_rate':rate,'input_hz':f,'output_component_hz':alias,'legacy_amplitude':old_gain,'bandlimited_amplitude':new_gain,
                 'legacy_db':20*np.log10(max(old_gain,1e-15)),'bandlimited_db':20*np.log10(max(new_gain,1e-15))}
            rows.append(row);print(row,flush=True)
    (B/'resampler_alias_audit.json').write_text(json.dumps(rows,indent=2))

if __name__=='__main__':main()
