"""Small independently read score checks; not a replacement accuracy metric.

This file is evaluation-only. Pitch/rhythm inference must not import it or
load independent_score_checks.json. Approximate phrase spans count attacks;
they are not independently verified individual word onset labels.
"""
from pathlib import Path
import csv,json
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v9_20261029'

def main():
    fixture=json.loads((B/'independent_score_checks.json').read_text(encoding='utf8'));rows=[]
    cases=[('v8_candidate',R/'output/vocal_event_research_20261029/qiansixi/full/音符.csv',0),
           ('native_game_direct',B/'game_native/qiansixi/native_8/notes.csv',23.99),
           ('native_full_recording',B/'native_full/qiansixi/notes.csv',0),
           ('legacy_editorial_proxy',R/'songs/product_song_review/qiansixi.csv',0)]
    for name,path,offset in cases:
        data=list(csv.DictReader(path.open(encoding='utf8')))
        for check in fixture['checks']:
            a,z=check['source_outer_span_approx_s'];pitches=[]
            for n in data:
                if name=='legacy_editorial_proxy':
                    t=float(n['source_start_s']);p=int(n['source_midi'])
                else:t=int(n['start_ms'])/1000+offset;p=int(n['midi'])
                if a<=t<z and p>=0:pitches.append(p)
            row={'case':name,'phrase':check['text'],'expected':check['expected_midi_attacks'],
                 'observed':pitches,'exact_sequence':pitches==check['expected_midi_attacks'],
                 'checks_pitch_sequence_and_attack_count_only':True,'timing_accuracy_measured':False,
                 'real_world_90_percent_verified':False}
            rows.append(row);print(row,flush=True)
    (B/'independent_score_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
