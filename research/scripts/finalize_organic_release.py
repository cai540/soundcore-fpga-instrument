"""Validate and record the organic-timbre software release without programming hardware."""
from pathlib import Path
import argparse, hashlib, json, subprocess, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--out', default='build/organic_20261027')
parser.add_argument('--label', default='organic')
parser.add_argument('--build-log', default='gowin_pipeline.log')
args = parser.parse_args()
OUT = ROOT / args.out

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))

build = read_json('build_validation.json')
firmware = Path(build['firmware'])
assert sha(firmware) == build['sha256']
assert not any(build['violations'].values())
regression = read_json('regression.json')
assert len(regression) == 10 and all(x['passed'] for x in regression)
pipeline = (OUT / 'pipeline.log').read_text()
assert 'PASS: 900 bit-exact frames' in pipeline and 'FATAL:' not in pipeline

protected = read_json('protected.json')
for name, expected in protected.items():
    assert sha(ROOT / name) == expected, 'Protected file changed: ' + name
audio = read_json('audio_metrics.json')
for name, expected in audio['source_sha256'].items():
    assert sha(ROOT / name) == expected, 'Preview source changed: ' + name

project = ROOT / 'board/pressure_i2s_panel_oled_ble_experiment_60k.gprj'
inputs = [project]
for entry in ET.parse(project).findall('.//File'):
    path = (project.parent / entry.attrib['path']).resolve()
    assert path.is_file(), str(path)
    assert path.stat().st_mtime <= firmware.stat().st_mtime, 'Build input changed: ' + str(path)
    inputs.append(path)

previews = {}
for path in sorted(OUT.glob('*.mp3')):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    duration = float(json.loads(probe.stdout)['format']['duration'])
    assert duration > 5
    if path.name in (f'zuguo_{args.label}_20s.mp3', f'chilege_{args.label}_20s.mp3'):
        assert 20 <= duration < 20.1
    previews[path.name] = dict(path=str(path), duration_seconds=duration, sha256=sha(path))
assert {f'zuguo_{args.label}_20s.mp3', f'chilege_{args.label}_20s.mp3'} <= previews.keys()

evidence = ['regression.log', 'pipeline.log', args.build_log, 'scan.log',
            'build_validation.json', 'audio_metrics.json', 'spectral_texture_check.png']
if (OUT / 'hiss_validation.json').is_file():
    evidence.append('hiss_validation.json')
    hiss = read_json('hiss_validation.json')
    assert hiss['texture_source_sha256'] == sha(ROOT / 'rtl/instrument_texture.v')
    for measurement in hiss['measurements']:
        if 'texture_change_db' in measurement:
            assert measurement['texture_change_db'] < -22
            assert measurement['residual_texture_rms_fraction'] < .01
for name in ['timing_report.html', 'resource_report.txt']:
    if (OUT / name).is_file():
        evidence.append(name)
report = dict(
    description='Algorithmic harmonica breath and erhu bow texture; smooth onset retained',
    build=build, regression=regression, pipeline_bit_exact_frames=900,
    clocks_per_voice=4, clocks_per_32_voices=128, clocks_per_sample=256,
    audio=audio, previews=previews, protected_files_unchanged=len(protected),
    revision_label=args.label,
    build_inputs_sha256={str(p.relative_to(ROOT)): sha(p) for p in inputs},
    evidence_sha256={name: sha(OUT / name) for name in evidence},
    hardware=dict(scan_result='No Gowin devices found', sram_written=False,
                  flash_written=False, speaker_listening_verified=False),
)
(OUT / 'release.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(firmware=build['firmware'], user_code=build['user_code'],
                      protected_unchanged=len(protected), build_inputs=len(inputs),
                      previews=len(previews), audio_tests=len(regression),
                      programmed=False), ensure_ascii=False, indent=2))
