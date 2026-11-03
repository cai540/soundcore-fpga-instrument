from pathlib import Path
import argparse,hashlib,json,numpy as np
from monophonic_note_lattice import decode_lattice
from transcribe_vocal_oss import write_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'
from benchmark_oss_vocals import inputs
parser=argparse.ArgumentParser();parser.add_argument('--all-windows',action='store_true');args=parser.parse_args();rows=[]
for name,window,path,_ in inputs():
    if not args.all_windows and window!='full':continue
    d=B/'runs/medium_voice_beam1'/name/window
    other=B/'runs/large_voice_beam1'/name/window
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    for folder in [d,other]:
        assert json.loads((folder/'result.json').read_text())['source_pcm_sha256']==digest
    raw=json.loads((d/'raw_notes.json').read_text());alt=json.loads((other/'raw_notes.json').read_text())
    e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/{window}/evidence.npz')
    p=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/{window}/pesto.npz')
    b=np.load(R/f'build/vocal_oss_20261029/basic/{name}/{window}/activations.npz')
    ac=np.load(R/f'build/vocal_syllable_main_20261029/{name}/{window}/acoustic.npz')
    notes,audit=decode_lattice(raw,alt,e,p,b,ac)
    write_notes(notes,d/'melody_lattice.csv');(d/'lattice_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    row={'name':name,'window':window,'notes':len(notes),'hypotheses':audit['candidate_notes'],'source_pcm_sha256':digest}
    rows.append(row);print(row,flush=True)
(B/'lattice_batch.json').write_text(json.dumps(rows,indent=2))
