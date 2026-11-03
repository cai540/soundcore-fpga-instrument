"""Check the fresh RTL preview files, including real MP3 decoding."""
from pathlib import Path
import hashlib, json, subprocess, wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'build/expression_20261028'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
a = json.loads((OUT/'audition.json').read_text())
for name, digest in a['capture_source_sha256'].items():
    assert sha(ROOT/name) == digest, 'Stale audio source: '+name
inputs = json.loads((OUT/'build_input_sha256.json').read_text())
for name, digest in inputs.items():
    assert sha(ROOT/name) == digest, 'Changed build input: '+name
assert len(a['preview_files']) == 8
results = []
for key, filename in a['preview_files'].items():
    mp3 = Path(filename)
    wav = mp3.with_suffix('.wav')
    seconds = 25 if key.endswith('_ablations') else 6 if key.endswith('_new') and not key.endswith('_old_then_new') else 12.5
    with wave.open(str(wav), 'rb') as w:
        assert w.getframerate() == 48000 and w.getnchannels() == 1 and w.getsampwidth() == 2
        assert w.getnframes() == int(seconds*48000), (key, w.getnframes())
        original = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.int32)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp3), '-f', 's16le',
                              '-acodec', 'pcm_s16le', '-ar', '48000', '-ac', '1', '-'],
                             capture_output=True, check=True).stdout
    pcm = np.frombuffer(decoded, dtype='<i2').astype(np.int32)
    assert len(pcm) == len(original), (key, len(pcm), len(original))
    assert 0 < max(abs(original)) < 32767
    assert 0 < max(abs(pcm)) < 32767
    results.append(dict(name=key, seconds=seconds, wav_sha256=sha(wav), mp3_sha256=sha(mp3),
                        original_peak=int(max(abs(original))), decoded_peak=int(max(abs(pcm)))))
result = dict(passed=True, previews=results, actual_source_hashes_checked=True,
              frozen_build_inputs_checked=len(inputs), actual_mp3_decoding_checked=True,
              physical_listening_verified=False)
(OUT/'audio_validation.json').write_text(json.dumps(result, indent=2))
print('PASS:8 previews, exact WAV/decoded MP3 durations, current sources, no clipping')
