"""Recording-internal motif cross-check on newly transcribed events."""
from pathlib import Path
import json,numpy as np
from recording_motif_consensus import refine_repeats
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'
for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/'runs/medium_voice_beam1'/name/'full'
    if not (d/'melody_consensus_raw.csv').exists():continue
    notes=read_notes(d/'melody_consensus_raw.csv')
    bp=np.load(R/f'build/vocal_oss_20261029/basic/{name}/full/activations.npz')
    cr=np.load(R/f'build/vocal_pitch_90_20261029/{name}/full/crepe.npz')
    out,audit=refine_repeats(notes,bp,cr)
    write_notes(out,d/'melody_repeat.csv');(d/'repeat_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,'paths',len(audit['paths']),'changed',audit['changes'],flush=True)
