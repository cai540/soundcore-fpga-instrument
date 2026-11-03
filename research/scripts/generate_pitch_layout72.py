"""Expand the pitch domain; preserve existing72-note timbre edits by default."""
from pathlib import Path
import json, math, re, hashlib,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--initialize-legacy-timbres',action='store_true',help='Explicitly restore V1 coefficients; otherwise retain any existing72-note tone tables');args=parser.parse_args()
p=json.loads((ROOT/'config/expression_profile_v1.json').read_text(encoding='utf8'))
def sine(phase):
    phase=np.asarray(phase,dtype=np.uint64)&0xffffffff;q=(phase+0x40000000)&0xffffffff
    t=np.where(q>>31,((~(q>>16))&32767)*2,((q>>16)&32767)*2).astype(np.int64)
    x=(t^32768)+np.where(t<32768,65536,0);x=np.where(x>=65536,x-131072,x)
    return (x*(65536-np.abs(x)))>>15
phase=np.arange(8192,dtype=np.uint64)*(2**32//8192)
waves=np.array([sine(phase*k) for k in range(1,7)],dtype=float)
out=[[],[]]
for timbre in range(2):
    kind='harmonica' if timbre else 'erhu'
    for note in range(72):
        f0=440*2**((36+note-69)/12);freq=f0*np.arange(1,7)
        body=p.get(kind+'_body',dict(floor=.8 if timbre else .7,peak=.35 if timbre else .55,
            centre_hz=1200 if timbre else 1700,width_octaves=.9 if timbre else .7,rolloff_hz=22000 if timbre else 18000))
        shape=(body['floor']+body['peak']*np.exp(-.5*(np.log2(freq/body['centre_hz'])/body['width_octaves'])**2))*np.exp(-freq/body['rolloff_hz'])
        for anchor in range(9):
            x=anchor/8;weights=((1-x)*np.array(p[kind+'_soft'])+x*np.array(p[kind+'_strong']))*shape
            raw=weights*p['raw_weight_scale'];sig=raw@waves
            norm=raw*p['target_wave_rms']/np.sqrt(np.mean(sig*sig))
            for mode,w in enumerate([raw,norm]):
                values=np.rint(w*4096).astype(int);assert np.all((values>=0)&(values<4096))
                n=0
                for v in reversed(values):n=(n<<12)|int(v)
                out[mode].append(f'{n:018x}')
for mode,name in enumerate(['expression_raw.mem','expression_normalized.mem']):
    target=ROOT/'rtl'/name
    current=target.read_text().split()if target.exists()else[]
    if len(current)==1296 and not args.initialize_legacy_timbres:
        assert all(len(v)==18 and 0<=int(v,16)<2**72 for v in current)
        print('Preserved existing tone table:',name)
        continue
    original=(ROOT/'build/timbre_pressure_repair_20261101/before/rtl'/name).read_text().split()
    for timbre in range(2):
        assert out[mode][timbre*648+24*9:timbre*648+59*9]==original[timbre*315:(timbre+1)*315],name
    target.write_text('\n'.join(out[mode])+'\n')
lines=['// Exact MIDI 36..107 at 48 kHz. Natural pads are mapped separately.',
 'module note_step_table72(input wire [6:0] note_index, output reg [31:0] phase_step);',
 'always @* case(note_index)']
for i in range(72):lines.append(f"7'd{i}: phase_step=32'd{round(440*2**((36+i-69)/12)*2**32/48000)};")
lines+=['default: phase_step=0;','endcase','endmodule']
(ROOT/'rtl/note_step_table72.v').write_text('\n'.join(lines)+'\n')
print('72 exact pitches; existing tone edits retained unless explicit legacy initialization was requested.')
