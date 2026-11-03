"""Ablate earlier generic refinements on fresh native-model observations.

This produces diagnostic CSVs, not a listening-approved song release. No
curated score, lyrics, song key, bookmark or expected note count enters.
"""
from pathlib import Path
import argparse
import csv
import json
import subprocess
import time

import numpy as np
from scipy.signal import resample_poly

from native_vocal_observations import load
from syllable_vocal_decoder import decode_syllables
from periodic_vowel_events import collapse_periodic_vowels
from vocal_event_refinement import refine_events
from vocal_boundary_features import analyze
from transcribe_vocal_oss import write_notes


def main():
    p = argparse.ArgumentParser()
    p.add_argument('audio', type=Path)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((args.baseline / 'observations.json').read_text())
    evidence, pesto, acoustic = load(metadata['directory'])
    with (args.baseline / 'notes.csv').open() as f:
        raw = [{k: float(v) if k == 'confidence' else int(v) for k, v in row.items()}
               for row in csv.DictReader(f)]
    native = np.frombuffer(subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(args.audio), '-ac', '1', '-ar', '44100',
        '-f', 'f32le', '-']), dtype='<f4').copy()
    import hashlib
    if hashlib.sha256(native.tobytes()).hexdigest() != metadata['native_pcm_sha256']:
        raise RuntimeError('Observation waveform does not match the original input')
    pcm = resample_poly(native, 160, 441).astype(np.float32)
    boundary = analyze(pcm, acoustic['rms'])
    np.savez_compressed(args.output / 'app_boundary.npz', **boundary)
    rows = []
    experiments = [
        ('raw', lambda: (raw, {'unmodified': True})),
        ('legacy_syllable_decoder', lambda: decode_syllables(pcm, evidence, raw, acoustic)),
        ('legacy_vowel_refinement', lambda: refine_events(raw, evidence, pesto, acoustic)),
        ('legacy_periodic_refinement', lambda: collapse_periodic_vowels(raw, evidence, pesto)),
    ]
    for name, operation in experiments:
        started = time.perf_counter()
        notes, audit = operation()
        write_notes(notes, args.output / (name + '.csv'))
        (args.output / (name + '.json')).write_text(json.dumps(audit, indent=2), encoding='utf8')
        rows.append({'name': name, 'notes': len(notes), 'seconds': time.perf_counter() - started,
                     'real_world_accuracy_verified': False})
        print(rows[-1], flush=True)
    (args.output / 'ablation.json').write_text(json.dumps(rows, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
