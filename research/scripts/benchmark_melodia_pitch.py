"""Cache independent melody evidence; no song reference, lyrics, or score input."""
from pathlib import Path
import json, subprocess, hashlib
import numpy as np
from scipy.signal import resample_poly
from benchmark_oss_vocals import inputs

R=Path(__file__).resolve().parents[1]
B=R/'build/vocal_pitch_grounded_20261029'

def main():
    for name,window,source,offset in inputs():
        # Start with all four complete sources. Nursery and cut-window runs follow only if useful.
        if window!='full': continue
        d=B/name/window;d.mkdir(parents=True,exist_ok=True)
        if (d/'melodia.npz').exists():continue
        x=np.fromfile(source,dtype='<f4');out=d/'melodia_44100.f32'
        resample_poly(x,441,160).astype('<f4').tofile(out)
        subprocess.run(['D:/node.js/node.exe',str(R/'scripts/extract_melodia_pitch.cjs'),str(out),str(d/'melodia_raw')],check=True)
        f0=np.fromfile(d/'melodia_raw.pitch.f32',dtype='<f4')
        confidence=np.fromfile(d/'melodia_raw.pitchConfidence.f32',dtype='<f4')
        # Preserve exact source time, no proportional stretching to output length.
        grid=np.arange((len(x)+159)//160)*.01
        idx=np.clip(np.rint(grid*44100/128).astype(int),0,len(f0)-1)
        np.savez_compressed(d/'melodia.npz',f0=f0[idx],confidence=confidence[idx])
        info=json.loads((d/'melodia_raw.json').read_text())
        info.update(input_file=str(source),input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),offset_seconds=offset)
        (d/'melodia.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,'frames',len(f0),'voiced',float(np.mean(f0>0)),flush=True)

if __name__=='__main__':main()
