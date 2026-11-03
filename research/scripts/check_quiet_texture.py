"""Check the actual quieter RTL against the archived noisy audition and no-texture control."""
from pathlib import Path
import hashlib, json, subprocess, wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/quiet_texture_20261027'
OLD = ROOT / 'build/organic_20261027'
RATE = 48000

def capture(folder, name, count):
    raw = np.array([int(x, 16) for x in (folder / name).read_text().split()], dtype=np.int32)
    assert len(raw) == count, (name, len(raw), count)
    return np.where(raw > 32767, raw - 65536, raw).astype(float)

old = capture(OUT, 'old.hex', 576000)
new = capture(OUT, 'new.hex', 576000)
tone = capture(OUT, 'tonal_only.hex', 576000)
rms = lambda x: float(np.sqrt(np.mean(x*x)))
measurements = []
for kind, base in [('harmonica', 0), ('erhu', 288000)]:
    window = slice(base + 240000, base + 274000)
    before = old[window] - tone[window]
    after = new[window] - tone[window]
    reduction = 20 * np.log10(rms(after) / rms(before))
    fraction = rms(after) / rms(new[window])
    assert reduction < -22, (kind, 'hiss reduction too small', reduction)
    assert fraction < .01, (kind, 'residual texture exceeds 1%', fraction)
    assert np.max(abs(new[base:base+9500])) == 0, 'idle hiss'
    measurements.append(dict(timbre=kind, texture_change_db=float(reduction),
                             residual_texture_rms_fraction=fraction))

# Use exactly the gain of the noisy song previews; quieter noise must not be
# compensated by normalizing this version separately.
gain = json.loads((OLD / 'audio_metrics.json').read_text())['common_preview_gain']
for song in ['zuguo', 'chilege']:
    samples = capture(OUT, song + '_20s.hex', 960000)
    previous = capture(OLD, song + '_20s.hex', 960000)
    assert abs(samples).max() < 32760 and abs(samples * gain).max() < 1
    path = OUT / (song + '_quiet_20s.wav')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(np.rint(samples * gain * 32767).astype('<i2').tobytes())
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-codec:a',
                    'libmp3lame', '-q:a', '2', str(path.with_suffix('.mp3'))], check=True)
    change_db = 20 * np.log10(rms(samples) / rms(previous))
    assert abs(change_db) < .25, (song, 'overall gain changed', change_db)
    measurements.append(dict(song=song, overall_rms_change_db=float(change_db),
                             common_gain=gain, clipped_samples=0))

record = dict(measurements=measurements,
              texture_source_sha256=hashlib.sha256((ROOT / 'rtl/instrument_texture.v').read_bytes()).hexdigest(),
              sram_written=False, flash_written=False)
(OUT / 'hiss_validation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
