"""Fresh acoustic observations for the native single-singer pipeline.

Reuse the earlier RWBD/RMVPE/FCPE, PESTO and acoustic-feature code, but never
reuse evidence extracted from the legacy App resampler. Identity is the PCM,
extractor code and model hashes, not the recording's name or a known score.
This worker is deliberately separate from the ONNX note-model process.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/vocal_transcription_v9_20261029'
POLICY = 'native-acoustic-observations-v1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def specification(pcm44100):
    paths = [
        ROOT / 'scripts/syllable_vocal_evidence.py',
        ROOT / 'scripts/syllable_vocal_decoder.py',
        ROOT / 'scripts/extract_pitch_grounding.py',
        ROOT / 'scripts/game_vocal_engine.py',
        Path(__file__),
        ROOT / 'build/vocal_oss_20261029/ROSVOT/checkpoints/rmvpe/model.pt',
        ROOT / 'build/vocal_oss_20261029/ROSVOT/checkpoints/rwbd/model.pt',
        ROOT / 'build/vocal_oss_20261029/ROSVOT/checkpoints/rosvot/config.yaml',
        ROOT / 'build/vocal_oss_20261029/ROSVOT/checkpoints/rwbd/config.yaml',
        ROOT / 'build/vocal_syllable_main_20261029/extra/torchfcpe/assets/fcpe_c_v001.pt',
        ROOT / 'build/vocal_pitch_grounded_20261029/extra/pesto/weights/mir-1k_g7.ckpt',
    ]
    info = {
        'policy': POLICY,
        'native_rate': 44100,
        'native_pcm_sha256': hashlib.sha256(pcm44100.tobytes()).hexdigest(),
        'rate_conversion': 'scipy.signal.resample_poly 160/441',
        'analysis_rate': 16000,
        'source_ms': round(len(pcm44100) * 1000 / 44100),
        'frame_ms': 10,
        'code_and_weights_sha256': {str(p.relative_to(ROOT)): digest(p) for p in paths},
        'song_identity_or_reference_used': False,
    }
    signature = hashlib.sha256(json.dumps(info, sort_keys=True).encode()).hexdigest()
    return signature, info


def extract(pcm44100, cache_root=BASE / 'acoustic_cache'):
    if (pcm44100.dtype != np.float32 or pcm44100.ndim != 1
            or not np.isfinite(pcm44100).all() or len(pcm44100) < 4410):
        raise ValueError('Finite native mono float32 PCM of at least 0.1 s required')
    signature, info = specification(pcm44100)
    directory = Path(cache_root) / signature
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / 'observations.npz'
    manifest = directory / 'manifest.json'
    if destination.exists() and manifest.exists():
        previous = json.loads(manifest.read_text(encoding='utf8'))
        if previous.get('observations_sha256') == digest(destination):
            return directory, {**previous, 'cache_hit': True}

    started = time.perf_counter()
    pcm = resample_poly(pcm44100, 160, 441).astype(np.float32)
    # Importing this module does not initialize any model or read any score.
    from syllable_vocal_evidence import SyllableEvidenceExtractor
    from syllable_vocal_decoder import acoustic_features
    from extract_pitch_grounding import pesto_extract
    import torch
    import pesto
    torch.set_num_threads(6)
    extractor = SyllableEvidenceExtractor()
    evidence = extractor.extract(pcm, lambda i, n: print('phonetic/f0', i, '/', n, flush=True))
    del extractor
    pitched = pesto_extract(pesto.load_model('mir-1k_g7', step_size=10., sampling_rate=16000), pcm)
    features = acoustic_features(pcm)
    arrays = {**{'e_' + k: v for k, v in evidence.items()},
              **{'p_' + k: v for k, v in pitched.items() if k != 'probabilities'},
              **{'a_' + k: v for k, v in features.items()}}
    frames = len(evidence['rmvpe'])
    if any(len(v) != frames for v in arrays.values()):
        raise RuntimeError('Acoustic observations do not share the source 10 ms grid')
    # One finished manifest commits the cache; a partial worker output cannot
    # become a successful cache hit after interruption.
    temporary = directory / 'observations.pending.npz'
    np.savez_compressed(temporary, **arrays)
    temporary.replace(destination)
    info.update(analysis_pcm_sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
                observations_sha256=digest(destination), frames=frames,
                extraction_seconds=time.perf_counter() - started)
    manifest.write_text(json.dumps(info, indent=2), encoding='utf8')
    return directory, {**info, 'cache_hit': False}


def load(directory):
    with np.load(Path(directory) / 'observations.npz') as archive:
        groups = [{k[2:]: archive[k] for k in archive.files if k.startswith(prefix)}
                  for prefix in ('e_', 'p_', 'a_')]
    return tuple(groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import subprocess
    pcm = np.frombuffer(subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(args.audio), '-ac', '1', '-ar', '44100',
        '-f', 'f32le', '-']), dtype='<f4').copy()
    directory, info = extract(pcm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'directory': str(directory), **info}, indent=2), encoding='utf8')
    print('saved', directory, 'cache_hit', info['cache_hit'], flush=True)


if __name__ == '__main__':
    main()
