from pathlib import Path
import json,numpy as np
from transcription_event_consensus import consensus_events,merge_corroborated_sustain
from transcribe_vocal_oss import write_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'

def main():
    for name in ['zuguo','chilege','qiansixi','lantingxu']:
        d=B/'runs/medium_voice_beam1'/name/'full'
        raw=json.loads((d/'raw_notes.json').read_text());alt=json.loads((B/'runs/large_voice_beam1'/name/'full/raw_notes.json').read_text())
        views=[]
        for w,o in [(4000,0),(4000,2000),(8000,0)]:
            a=np.load(d/f'game_{w}_{o}.npz');v=a['midi'].copy();v[~a['present']]=np.nan;views.append(v)
        e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/evidence.npz')
        p=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/full/pesto.npz')
        c=np.load(R/f'build/vocal_pitch_90_20261029/{name}/full/crepe.npz')
        b=np.load(R/f'build/vocal_oss_20261029/basic/{name}/full/activations.npz')
        ac=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/acoustic.npz')
        notes,audit=consensus_events(raw,alt,views,e,p,c,b)
        write_notes(notes,d/'melody_consensus_raw.csv')
        notes,sustain=merge_corroborated_sustain(notes,alt,e,ac);audit['sustain']=sustain
        write_notes(notes,d/'melody_consensus.csv');(d/'consensus_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,len(notes),'sustain_merges',len(sustain['removed_reattacks']),flush=True)

if __name__=='__main__':main()
