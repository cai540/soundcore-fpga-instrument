from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/early_pressure_20261028';OUT.mkdir(parents=True,exist_ok=True)
BASE=OUT/'baseline';BASE.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((ROOT/'build/shared_pitch_20261028/release.json').read_text(encoding='utf-8'))
manifest=BASE/'source_sha256.json'
if not manifest.exists():
    for rel,expected in release['source_sha256'].items():
        assert sha(ROOT/rel)==expected,'Changed baseline input: '+rel
        target=BASE/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
    manifest.write_text(json.dumps(release['source_sha256'],indent=2),encoding='utf-8')
    shutil.copy2(ROOT/'build/shared_pitch_20261028/release.json',BASE/'release.json')
    shutil.copy2(ROOT/'build/shared_pitch_20261028/baseline/protected.json',BASE/'protected.json')
for rel,expected in json.loads(manifest.read_text()).items():assert sha(BASE/rel)==expected
legacy=BASE/'fsr_strike_detector_legacy.v'
expected=(BASE/'rtl/fsr_strike_detector.v').read_text().replace('module fsr_strike_detector #(','module fsr_strike_detector_legacy #(')
if not legacy.exists():legacy.write_text(expected,encoding='utf-8')
assert legacy.read_text()==expected
assert sha(Path(release['firmware']))==release['sha256']
print('Frozen C2B3 inputs and legacy detector; no hardware access.')
