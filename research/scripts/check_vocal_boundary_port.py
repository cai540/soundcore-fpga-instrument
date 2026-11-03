"""Compare the port with the real previously compiled Android DSP class."""
from pathlib import Path
import csv
import hashlib
import json
import os
import subprocess
import numpy as np
from vocal_boundary_features import analyze
from syllable_vocal_decoder import acoustic_features

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/vocal_transcription_v9_20261029/boundary_port_parity'
JDK = Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    classes = ROOT / 'app/android/app/build/tmp/kotlin-classes/debug'
    stdlib = next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
    cp = os.pathsep.join(map(str, [classes, stdlib, BASE]))
    subprocess.run([str(JDK / 'javac.exe'), '-cp', cp, '-d', str(BASE),
                    str(ROOT / 'scripts/support/CheckVocalBoundaryParity.java')], check=True)
    t = np.arange(16000 * 4) / 16000
    # Formant change, vibrato, true silence, quiet/normal gain. No note targets.
    phase = np.cumsum(220 * 2 ** (.6 * np.sin(2 * np.pi * 6 * t) / 12)) * 2 * np.pi / 16000
    voice = sum(np.sin(phase * h) / h * np.where(t < 1.5, np.exp(-((h * 220 - 700) / 900) ** 2),
                 np.exp(-((h * 220 - 1700) / 1000) ** 2)) for h in range(1, 13))
    voice[(t > 2.5) & (t < 2.8)] = 0
    voice[t > 3.7] = 0
    rows = []
    for name, pcm in [('normal', (voice * .2).astype(np.float32)),
                      ('quiet', (voice * .02).astype(np.float32))]:
        features = acoustic_features(pcm)
        target = analyze(pcm, features['rms'])
        wave, rms_file, actual = BASE / (name + '.f32'), BASE / (name + '.rms'), BASE / (name + '.csv')
        pcm.astype('<f4').tofile(wave)
        features['rms'].astype('<f8').tofile(rms_file)
        subprocess.run([str(JDK / 'java.exe'), '-cp', cp, 'CheckVocalBoundaryParity',
                        str(wave), str(rms_file), str(actual)], check=True)
        java = list(csv.DictReader(actual.open()))[:len(target['novelty'])]
        delta = {key: float(np.max(abs(target[key] - [float(row[key]) for row in java])))
                 for key in ('novelty', 'strength')}
        if max(delta.values()) > 1e-9:
            raise RuntimeError('Port/App measurement mismatch: ' + str(delta))
        rows.append({'case': name, 'frames_compared': len(java), 'maximum_absolute_error': delta})
    source = ROOT / 'app/android/app/src/main/java/cn/soundcore/instrument/VocalBoundaryEvidence.kt'
    (BASE / 'result.json').write_text(json.dumps({'cases': rows,
        'app_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'app_class_sha256': hashlib.sha256((classes / 'cn/soundcore/instrument/VocalBoundaryEvidence.class').read_bytes()).hexdigest(),
        'scope': 'same-PCM measurement parity; not real-song recognition accuracy'}, indent=2), encoding='utf8')
    print(rows)


if __name__ == '__main__':
    main()
