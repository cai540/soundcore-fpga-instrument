"""Apply one boundary policy to all four full recordings."""
from pathlib import Path
import argparse,json,numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from phonetic_event_refinement import refine_phonetic_events
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',default='');args=p.parse_args()
    for name in ['zuguo','chilege','qiansixi','lantingxu']:
        if args.only and args.only not in name:continue
        d=B/'runs/medium_voice_beam1'/name/'full'
        if not (d/'melody_joint.csv').exists():continue
        notes=read_notes(d/'melody_joint.csv')
        a=json.loads((B/'asr'/name/'full/alignment.json').read_text(encoding='utf8'))
        e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/evidence.npz')
        pp=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/full/pesto.npz')
        ac=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/acoustic.npz')
        out,audit=refine_phonetic_events(notes,a,e,pp,ac)
        write_notes(out,d/'melody_phonetic.csv');(d/'phonetic_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,'before',len(notes),'after',len(out),'merges',len(audit['same_vowel_merges']),
              'ASR protected attacks',len(audit['protected_attacks_ms']),'ASR rejected',len(audit['rejected_asr_times']),flush=True)

if __name__=='__main__':main()
