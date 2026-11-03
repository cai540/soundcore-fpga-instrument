from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/expression_20261028';OUT.mkdir(parents=True,exist_ok=True)
BASE=OUT/'baseline';BASE.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((ROOT/'build/early_pressure_20261028/release.json').read_text(encoding='utf-8'))
manifest=BASE/'source_sha256.json'
if not manifest.exists():
    for name,h in release['source_sha256'].items():
        assert sha(ROOT/name)==h,'Baseline changed before freeze: '+name
        dest=BASE/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    manifest.write_text(json.dumps(release['source_sha256'],indent=2))
    shutil.copy2(ROOT/'build/early_pressure_20261028/release.json',BASE/'release.json')
    shutil.copy2(ROOT/'build/early_pressure_20261028/baseline/protected.json',BASE/'protected.json')
for name,h in json.loads(manifest.read_text()).items():assert sha(BASE/name)==h
assert sha(Path(release['firmware']))==release['sha256']
# Rename the full audio dependency chain for disabled-path bit-exact checks.
renames={'playable_synth32':'expression_legacy_playable_synth32','poly_synth32_tm':'expression_legacy_poly_synth32_tm',
    'instrument_texture':'expression_legacy_instrument_texture'}
for module in renames:
    import re
    text=(BASE/'rtl'/(module+'.v')).read_text()
    for old,new in renames.items():text=re.sub(r'\b'+old+r'\b',new,text)
    target=BASE/(renames[module]+'.v')
    if not target.exists():target.write_text(text)
    assert target.read_text()==text
print('Frozen1C8A sources and audio reference. No hardware access.')
