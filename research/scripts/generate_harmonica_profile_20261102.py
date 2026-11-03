"""Generate only the reed half of the72-pitch tables; preserve existing bow bits."""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy.optimize import nnls
R=Path(__file__).resolve().parents[1];B=R/'build/harmonica_refinement_20261102'
P=R/'config/harmonica_profile_v3_20261102.json';p=json.loads(P.read_text('utf8'))
def sine(phase):
    q=(np.asarray(phase,dtype=np.uint64)+0x40000000)&0xffffffff
    t=np.where(q>>31,((~(q>>16))&32767)*2,((q>>16)&32767)*2).astype(np.int64)
    x=(t^32768)+np.where(t<32768,65536,0);x=np.where(x>=65536,x-131072,x)
    y=(x*(65536-np.abs(x)))>>15
    return y
def main():
    phase=np.arange(16384,dtype=np.uint64)*(2**32//16384)
    waves=np.array([sine(phase*k)for k in range(1,7)],float)
    # Model the real fixed-point oscillator's own harmonic leakage. Solve
    # the six-source spectral mixing once offline instead of adding many
    # correction multipliers to the almost-full FPGA.
    ideals=np.array([np.sin(phase.astype(float)/2**32*2*np.pi*k)for k in range(1,7)])
    transfer=2/len(phase)*(ideals@waves.T)/32768
    out=[[],[]];levels=[];body=p['body']
    for note in range(72):
        f0=440*2**((36+note-69)/12);freq=f0*np.arange(1,7)
        shape=(body['floor']+body['peak']*np.exp(-.5*(np.log2(freq/body['centre_hz'])/body['width_octaves'])**2))*np.exp(-freq/body['rolloff_hz'])
        fade=np.clip((p['harmonic_cutoff_hz']-freq)/(p['harmonic_cutoff_hz']-p['harmonic_fade_start_hz']),0,1)
        for anchor in range(9):
            mix=anchor/8;weights=((1-mix)*np.array(p['harmonica_soft'])+mix*np.array(p['harmonica_strong']))*shape*fade
            calibrated,_=nnls(transfer,weights)
            raw=calibrated*p['raw_weight_scale'];norm=raw*p['target_wave_rms']/np.sqrt(np.mean((raw@waves)**2))
            for mode,w in enumerate([raw,norm]):
                values=np.rint(w*4096).astype(int);assert np.all((values>=0)&(values<4096))
                n=sum(int(v)<<(12*k)for k,v in enumerate(values));out[mode].append(f'{n:018x}')
            levels.append(dict(midi=note+36,expression_anchor=anchor,normalized_rms=float(np.sqrt(np.mean(((np.rint(norm*4096)/4096)@waves)**2)))))
    for mode,name in enumerate(['expression_raw.mem','expression_normalized.mem']):
        baseline=(R/'rtl'/name).read_text().split();assert len(baseline)==1296
        packed=baseline[:648]+out[mode]
        (R/'rtl'/name).write_text('\n'.join(packed)+'\n')
        assert(R/'rtl'/name).read_text().split()[:648]==baseline[:648]
    f=np.abs(np.fft.rfft(sine(phase)))
    report=dict(profile_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),reed_anchors=len(levels),bow_anchors_bit_exact=648,
        runtime_oscillator_unchanged=True,raw_oscillator_h3_db=float(20*np.log10(f[3]/f[1])),
        spectral_transfer_matrix=transfer.tolist(),offline_nonnegative_spectral_calibration=True,additional_runtime_multipliers=0,
        normalized_rms_min=min(x['normalized_rms']for x in levels),normalized_rms_max=max(x['normalized_rms']for x in levels),
        levels=levels,uses_recorded_pcm=False,physical_listening_verified=False)
    (B/'profile_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items()if k!='levels'},indent=2))
if __name__=='__main__':main()
