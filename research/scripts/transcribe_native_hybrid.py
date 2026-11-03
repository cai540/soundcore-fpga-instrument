"""Generic native vocal -> protected main-note research pipeline.

The only musical input is audio. Reuses earlier acoustic/context code without
importing benchmarks, edited MIDI, supplied lyrics or a song-name database.
Writes diagnostic MIDI/CSV; it is not an accepted Android/FPGA release.
"""
from pathlib import Path
import argparse
import gc
import hashlib
import json
import subprocess
import sys
import time
import numpy as np
from scipy.signal import resample_poly

from game_native_voice_engine import NativeVoiceEngine
from native_vocal_observations import load
from estimate_pitch_contexts import ContextualGamePitchEstimator
from native_voice_refinement import refine
from vocal_boundary_features import analyze
from transcribe_vocal_oss import write_notes, write_midi

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/vocal_transcription_v9_20261029'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', default='zh')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reused = ['native_voice_refinement.py', 'game_native_voice_engine.py',
              'native_vocal_observations.py', 'native_basic_observations.py',
              'estimate_pitch_contexts.py', 'vocal_event_refinement.py',
              'vocal_boundary_features.py', 'vocal_pitch_center.py', 'periodic_vowel_events.py']
    code_hashes = {p: hashlib.sha256((ROOT / 'scripts' / p).read_bytes()).hexdigest() for p in reused}
    started = time.perf_counter()
    pcm = np.frombuffer(subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(args.audio), '-ac', '1', '-ar', '44100',
        '-f', 'f32le', '-']), dtype='<f4').copy()
    source_sha = hashlib.sha256(pcm.tobytes()).hexdigest()
    engine = NativeVoiceEngine(BASE / 'native_cache', language=args.language)
    notes, note_trace = engine.recognize(pcm, 44100,
        lambda i, n: print('native notes', i, '/', n, flush=True))
    del engine
    gc.collect()
    write_notes(notes, args.output / 'raw.csv')
    # Each worker verifies its own content-addressed model/PCM cache. There is
    # no filename-dependent dispatch and no reference score argument.
    for worker, name in [('native_vocal_observations.py', 'observations.json'),
                         ('native_basic_observations.py', 'basic_observations.json')]:
        subprocess.run([sys.executable, str(ROOT / 'scripts' / worker), str(args.audio),
                        '--output', str(args.output / name)], check=True)
    info = json.loads((args.output / 'observations.json').read_text())
    bp_info = json.loads((args.output / 'basic_observations.json').read_text())
    if any(meta['native_pcm_sha256'] != source_sha for meta in [info, bp_info]):
        raise RuntimeError('Observation and note-model source waveforms differ')
    evidence, pesto, acoustic = load(info['directory'])
    with np.load(Path(bp_info['directory']) / 'activations.npz') as archive:
        basic = {k: archive[k] for k in archive.files}
    pcm16 = resample_poly(pcm, 160, 441).astype(np.float32)
    boundary = analyze(pcm16, acoustic['rms'])
    model = ContextualGamePitchEstimator(sample_rate=44100, cache=BASE / 'fixed_context_cache')
    views = []
    for core, offset in [(4000, 0), (4000, 2000), (8000, 0)]:
        result = model.predict(pcm, notes, core, offset,
            lambda i, n: print('complete-note context', core, offset, i, '/', n, flush=True))
        views.append(np.where(result['present'], result['midi'], np.nan))
    output, audit = refine(notes, evidence, pesto, acoustic, boundary, views, basic)
    if any(hashlib.sha256((ROOT / 'scripts' / p).read_bytes()).hexdigest() != value
           for p, value in code_hashes.items()):
        raise RuntimeError('Algorithm source changed during inference; rerun with the completed caches')
    write_notes(output, args.output / 'notes.csv')
    write_midi(output, args.output / 'source_clock.mid')
    (args.output / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf8')
    manifest = {'version': audit['version'], 'source_ms': round(len(pcm) * 1000 / 44100),
        'native_pcm_sha256': source_sha, 'raw_notes': len(notes), 'output_notes': len(output),
        'algorithm_sha256': code_hashes,
        'note_model': note_trace, 'observations': info, 'basic_pitch': bp_info,
        'runtime_seconds': time.perf_counter() - started,
        'known_lyrics_or_reference_score_used': False, 'human_listening_accepted': False,
        'real_world_90_percent_verified': False, 'published_to_apk_or_fpga': False}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print('saved', args.output, len(output), 'notes', round(manifest['runtime_seconds'], 2), 'seconds', flush=True)


if __name__ == '__main__':
    main()
