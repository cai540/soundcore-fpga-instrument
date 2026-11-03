from pathlib import Path
import json,subprocess
import numpy as np
from scipy.signal import resample_poly
from benchmark_oss_vocals import inputs
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from register_candidate_pipeline import decode
from melodic_pitch_refiner import refine
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029';NEW=R/'build/vocal_pitch_90_20261029'

def main():
    results=[]
    for name,window,path,offset in inputs():
        d=B/name/window;old=read_notes(PRE/name/window/'notes.csv');pcm=np.fromfile(path,dtype='<f4')
        if not (d/'melodia.npz').exists():
            resample_poly(pcm,441,160).astype('<f4').tofile(d/'melodia_input_44100.f32')
            subprocess.run(['D:/node.js/node.exe',str(R/'scripts/extract_melodia_pitch.cjs'),str(d/'melodia_input_44100.f32'),str(d/'melodia_run')],check=True)
            f=np.fromfile(d/'melodia_run.pitch.f32',dtype='<f4');c=np.fromfile(d/'melodia_run.pitchConfidence.f32',dtype='<f4')
            grid=np.arange((len(pcm)+159)//160)*.01;idx=np.rint(grid*44100/128).astype(int).clip(0,len(f)-1)
            np.savez_compressed(d/'melodia.npz',f0=f[idx],confidence=c[idx])
        e=np.load(PRE/name/window/'evidence.npz');pe=np.load(d/'pesto.npz');me=np.load(d/'melodia.npz')
        notes,base_audit=refine(old,pcm,e['rmvpe'],pe['midi'],pe['confidence'],me['f0'])
        write_notes(notes,d/'v7_base_notes.csv')
        views=[np.load(d/f'context_{w}_{o}.npz')['midi'] for w,o in [(4000,0),(4000,2000),(8000,0)]]
        basic=np.load(R/'build/vocal_oss_20261029/basic'/name/window/'activations.npz')
        output,audit=decode(notes,views,np.load(PRE/name/window/'evidence.npz'),np.load(d/'pesto.npz'),
                           np.load(NEW/name/window/'crepe.npz'),basic,np.load(PRE/name/window/'acoustic.npz'))
        write_notes(output,d/'register_candidate_notes.csv')
        audit['base_pitch']=base_audit
        (d/'register_candidate_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        row={'name':name,'window':window,'notes_before':len(notes),'notes_after':len(output),
             'components_added':audit['components']['notes_added'],'events_deleted':len(audit['cleanup']['deleted']),
             'vibrato_islands_absorbed':len(audit['cleanup']['absorbed']),'same_policy_all_cases':True}
        results.append(row);print(row,flush=True)
    (NEW/'register_candidate_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
