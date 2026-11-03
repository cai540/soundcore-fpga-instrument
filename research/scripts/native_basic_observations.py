"""Optional Basic Pitch register evidence from native, bandlimited audio.

Only model activations are used; its polyphonic event list is not a vocal
syllable schedule and is never copied into the output melody.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/vocal_transcription_v9_20261029'


def extract(pcm44100):
    model = ROOT / 'build/vocal_oss_20261029/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx'
    info = {'policy': 'native-basic-register-evidence-v1',
            'native_pcm_sha256': hashlib.sha256(pcm44100.tobytes()).hexdigest(),
            'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
            'analysis_rate': 22050, 'rate_conversion': 'scipy resample_poly 1/2',
            'polyphonic_notes_used_as_vocal_events': False}
    key = hashlib.sha256(json.dumps(info, sort_keys=True).encode()).hexdigest()
    directory = BASE / 'basic_native_cache' / key
    directory.mkdir(parents=True, exist_ok=True)
    dst = directory / 'activations.npz'
    if dst.exists():
        return directory, {**info, 'cache_hit': True}
    sys.path.insert(0, str(ROOT / 'build/vocal_oss_20261029/basic-pitch'))
    from basic_pitch.inference import run_inference
    import soundfile as sf
    pcm = resample_poly(pcm44100, 1, 2).astype(np.float32)
    wave = directory / 'input.wav'
    sf.write(wave, pcm, 22050, subtype='FLOAT')
    raw = run_inference(wave, model)
    np.savez_compressed(dst, **raw)
    (directory / 'manifest.json').write_text(json.dumps(info, indent=2), encoding='utf8')
    return directory, {**info, 'cache_hit': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('audio', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    pcm = np.frombuffer(subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(args.audio), '-ac', '1', '-ar', '44100',
        '-f', 'f32le', '-']), dtype='<f4').copy()
    directory, info = extract(pcm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'directory': str(directory), **info}, indent=2), encoding='utf8')
    print('saved', directory, 'cache_hit', info['cache_hit'], flush=True)


if __name__ == '__main__':
    main()
