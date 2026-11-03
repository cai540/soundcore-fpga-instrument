"""Single-main-pitch output after estimating whole acoustic syllables."""
from pathlib import Path
import json,shutil
from benchmark_oss_vocals import inputs
from transcribe_vocal_oss import write_notes

R=Path(__file__).resolve().parents[1];B=R/'build/vocal_syllable_main_20261029'

def final_notes(units):
    # Deliberately use the whole-region neural estimate. Reference lyrics,
    # a key signature, pitch templates or song identifiers have no role here.
    return [{'start_ms':int(s['start_ms']),'duration_ms':int(s['end_ms']-s['start_ms']),
             'midi':int(s['midi']),'confidence':0.0} for s in units]

def main():
    for name,window,_,_ in inputs():
        d=B/name/window
        if not (d/'syllable_pitch.json').exists():continue
        units=json.loads((d/'syllable_pitch.json').read_text())
        write_notes(final_notes(units),d/'notes_reestimated.csv')
        if not (d/'notes_v2.csv').exists():shutil.copy2(d/'notes.csv',d/'notes_v2.csv')

if __name__=='__main__':main()
