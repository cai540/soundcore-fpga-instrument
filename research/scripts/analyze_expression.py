from pathlib import Path
import csv,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/expression_20261028'
rows=list(csv.DictReader((OUT/'texture_levels_rom.csv').open()))
assert len(rows)==630
for i,r in enumerate(rows):
    assert [int(r[k]) for k in ['timbre','note','expression']]==[i//315,(i%315)//9,255 if i%9==8 else (i%9)*32]
    assert float(r['rms'])>0 and int(r['peak'])<32760
groups=[]
for kind in range(2):
    selected=[r for r in rows if int(r['timbre'])==kind]
    norm=np.array([float(r['rms']) for r in selected]);raw=np.array([float(r['raw_rms']) for r in selected])
    span=20*np.log10(norm.max()/norm.min());assert span<1.0,span
    groups.append(dict(timbre='harmonica' if kind else 'erhu',normalized_rms_min=float(norm.min()),
        normalized_rms_max=float(norm.max()),normalized_span_db=float(span),
        uncompensated_span_db=float(20*np.log10(raw.max()/raw.min())),
        actual_rtl_cases=len(selected),maximum_source_peak=max(int(r['peak']) for r in selected)))
# Continuous phase reference including every interpolation code, not just anchors.
coeff=json.loads((OUT/'coefficient_reference.json').read_text())
phase=np.arange(8192,dtype=np.uint64)*(2**32//8192)
def sine(p):
    q=(p+0x40000000)&0xffffffff
    t=np.where(q>>31,((~(q>>16))&32767)*2,((q>>16)&32767)*2).astype(np.int64)
    x=(t^32768)+np.where(t<32768,65536,0);x=np.where(x>=65536,x-131072,x)
    return (x*(65536-np.abs(x)))>>15
w=np.array([sine((phase*k)&0xffffffff) for k in range(1,7)],dtype=float)
covariance=w@w.T/len(phase);all_rms=[]
for kind in range(2):
    for note in range(35):
        for expression in range(256):
            anchor,frac=expression>>5,expression&31
            a=np.array(coeff[f'1,{kind},{note},{anchor}']);b=np.array(coeff[f'1,{kind},{note},{anchor+1}'])
            c=(a+((b-a)*frac//32))/4096
            all_rms.append(float(np.sqrt(c@covariance@c)))
reference_span=20*np.log10(max(all_rms)/min(all_rms));assert reference_span<1.0
result={'actual_rtl_anchor_cases':630,'reference_interpolation_cases':len(all_rms),
    'all_reference_interpolation_span_db':float(reference_span),'measurements':groups,
    'interpretation':'RMS energy consistency at fixed amplitude; not proof of perceptual equal loudness or instrument realism',
    'physical_listening_verified':False,'hardware_programmed':False}
(OUT/'spectral_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
