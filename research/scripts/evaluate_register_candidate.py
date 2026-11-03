"""Offline diagnostics only; excluded from runtime imports."""
from pathlib import Path
import csv,json
from evaluate_pitch_notes import evaluate
from evaluate_oss_vocals import read_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';NEW=R/'build/vocal_pitch_90_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def main():
    rows=[]
    for name,rname in [('zuguo','wodezuguo'),('chilege','chilege'),('qiansixi','qiansixi')]:
        source=list(csv.DictReader((R/'songs/product_song_review'/f'{rname}.csv').open(encoding='utf8')))
        ref=[{'start_ms':round(float(q['source_start_s'])*1000),'duration_ms':round((float(q['source_end_s'])-float(q['source_start_s']))*1000),
              'midi':int(q['source_midi'])} for q in source if int(q['source_midi'])>0]
        old=evaluate(ref,read_notes(PRE/name/'full/notes.csv'))
        current=evaluate(ref,read_notes(B/name/'full/register_candidate_notes.csv'))
        row={'name':name,'old_v6':old,'new_candidate':current,'reference_kind':'prior_editorial_proxy_not_independent_gold',
             'source_midi_not_globally_transposed_device_midi':True,'timing_alignment_uses_no_pitch':True,
             'not_90_percent_accuracy_proof':True}
        rows.append(row);print(name,'old',old['correct_pitch_and_octave_notes'],'new',current['correct_pitch_and_octave_notes'],
                              'reference',len(ref),'missing',current['missed_notes'],'octave',current['octave_error_notes'],flush=True)
    rows.append({'name':'lantingxu','reference_available':False,'real_world_90_percent_verified':False})
    (NEW/'event_comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
