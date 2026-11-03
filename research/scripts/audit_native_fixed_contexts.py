"""Reuse the old complete-note context estimator on original-rate audio.

Diagnostic entry point. Supplied notes are model observations, not a score.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import subprocess
import numpy as np
from estimate_pitch_contexts import ContextualGamePitchEstimator
from native_vocal_observations import load
from context_pitch_consensus import refine_context
from recording_tonality import infer_collection
from transcribe_vocal_oss import write_notes

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('audio', type=Path)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.baseline / 'notes.csv').open() as f:
        notes = [{k: float(v) if k == 'confidence' else int(v) for k, v in row.items()}
                 for row in csv.DictReader(f)]
    pcm = np.frombuffer(subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(args.audio), '-ac', '1', '-ar', '44100',
        '-f', 'f32le', '-']), dtype='<f4').copy()
    source_sha = hashlib.sha256(pcm.tobytes()).hexdigest()
    info = json.loads((args.baseline / 'observations.json').read_text())
    if source_sha != info['native_pcm_sha256']:
        raise RuntimeError('Waveform and observations differ')
    engine = ContextualGamePitchEstimator(sample_rate=44100,
        cache=ROOT / 'build/vocal_transcription_v9_20261029/fixed_context_cache')
    views, data = [], {}
    for core, offset in [(4000, 0), (4000, 2000), (8000, 0)]:
        key = str(core) + '_' + str(offset)
        view = engine.predict(pcm, notes, core, offset,
            lambda i, n: print('context', key, i, '/', n, flush=True))
        data[key + '_midi'] = view['midi']
        data[key + '_present'] = view['present']
        views.append(np.where(view['present'], view['midi'], np.nan))
    np.savez_compressed(args.output / 'views.npz', **data)
    e, pe, _ = load(info['directory'])
    output, audit = refine_context(notes, views, e, pe, infer_collection(notes))
    write_notes(output, args.output / 'legacy_context_refinement.csv')
    (args.output / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf8')
    (args.output / 'manifest.json').write_text(json.dumps({
        'native_pcm_sha256': source_sha,
        'schedule_sha256': hashlib.sha256(json.dumps(notes, sort_keys=True).encode()).hexdigest(),
        'observation_directory': info['directory'],
        'weights_sha256': engine.engine.weights,
        'sample_rate': 44100,
        'references_or_lyrics_used': False,
        'real_world_accuracy_verified': False,
    }, indent=2), encoding='utf8')
    print('changes', audit['changes'], flush=True)


if __name__ == '__main__':
    main()
