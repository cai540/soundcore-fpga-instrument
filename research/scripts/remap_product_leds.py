"""Build a pin-only revision from a frozen, verified complete product image.

All non-constraint inputs must remain byte-identical after normalizing the
snapshot directory prefix. Existing RTL checks are reused only with that proof;
the new placement, routing, timing and final pin report are checked separately.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--base-release', required=True)
parser.add_argument('--layout', required=True)
parser.add_argument('--build-dir', required=True)
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
release_path = ROOT / args.base_release / 'release.json'
release = json.loads(release_path.read_text(encoding='utf-8'))
BASE = ROOT / 'build' / release_path.parent.name
OUT = ROOT / args.build_dir
assert BASE.resolve() != OUT.resolve(), 'Never overwrite the verified baseline'
firmware = Path(release['firmware'])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(firmware) == release['sha256']
assert release['standard_i2s_selected'] and release['routed_pins_verified']
assert all(t['passed'] for t in release['tests'])
layout = json.loads((ROOT / args.layout).read_text(encoding='utf-8'))
leds = layout['leds']
assert layout['schema_version'] == 1 and [x['led'] for x in leds] == list(range(1, 8))
for led in leds:
    assert led['row'] in ['A', 'B'] and layout['minimum_group'] <= led['group'] <= 20
    assert led['position'] == led['row'] + str(led['group'])
    assert led['header_pin'] == 2 * led['group'] - (led['row'] == 'A')
    assert led['position'] not in layout['occupied_positions_to_preserve']
assert len({x['ball'] for x in leds}) == len({x['position'] for x in leds}) == 7

SRC = OUT / 'baseline'
for p in (BASE / 'baseline').rglob('*'):
    if not p.is_file():
        continue
    target = SRC / p.relative_to(BASE / 'baseline')
    target.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix in ['.v', '.vh', '.cst', '.sdc']:
        target.write_text(p.read_text(encoding='utf-8').replace(BASE.as_posix(), OUT.as_posix()), encoding='utf-8')
    else:
        shutil.copyfile(p, target)
NAME = 'soundcore_speaker_omr_60k'
cst = SRC / 'board' / (NAME + '.cst')
original = cst.read_text(encoding='utf-8')
text = original
for led in leds:
    signal = f"pad_led_o[{led['led']-1}]"
    text, count = re.subn(r'IO_LOC "' + re.escape(signal) + r'" [^;]+;',
                          f'IO_LOC "{signal}" {led["ball"]};', text)
    assert count == 1, signal
text = re.sub(r'// 2026-10-31: J13 A4.*?// three groups[^\n]*\n', '', text, flags=re.S)
text = '// LED layout: ' + ', '.join(x['position'] for x in leds) + '; all groups >=8.\n' + text
cst.write_text(text, encoding='utf-8')
def pins(body):
    return dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([^;]+);', body))
before, after = pins(original), pins(text)
signals = {f'pad_led_o[{i}]' for i in range(7)}
assert set(before) == set(after) and len(set(after.values())) == len(after)
assert all(before[k] == after[k] for k in before if k not in signals)
assert {k: after[k] for k in signals} == {f"pad_led_o[{x['led']-1}]": x['ball'] for x in leds}
attributes = lambda body: dict(re.findall(r'IO_PORT\s+"([^"]+)"\s+([^;]+);', body))
assert attributes(original) == attributes(text)

proof = []
for p in (SRC).rglob('*'):
    if not p.is_file() or p == cst:
        continue
    prior = BASE / 'baseline' / p.relative_to(SRC)
    if p.suffix in ['.v', '.vh', '.sdc']:
        equal = p.read_text(encoding='utf-8') == prior.read_text(encoding='utf-8').replace(BASE.as_posix(), OUT.as_posix())
    else:
        equal = p.read_bytes() == prior.read_bytes()
    assert equal, 'Unexpected source change: ' + str(p)
    proof.append({'file':p.relative_to(SRC).as_posix(), 'baseline_sha256':sha(prior), 'snapshot_sha256':sha(p)})
tree = ET.parse(BASE / (NAME + '.gprj'))
for item in tree.findall('./FileList/File'):
    path = Path(item.attrib['path'])
    if path.is_relative_to(BASE / 'baseline'):
        item.set('path', (SRC / path.relative_to(BASE / 'baseline')).as_posix())
    elif path.is_file():
        proof.append({'external_input':str(path), 'sha256':sha(path)})
project = OUT / (NAME + '.gprj')
tree.write(project, encoding='utf-8', xml_declaration=True)
meta = json.loads((BASE / 'build_metadata.json').read_text(encoding='utf-8'))
meta.update(baseline_firmware_sha256=release['sha256'], baseline_user_code=release['user_code'],
            led_positions=[x['position'] for x in leds],
            led_balls={f"pad_led_o[{x['led']-1}]":x['ball'] for x in leds},
            modified_copied_files=['board/' + NAME + '.cst'],
            led_layout=str(ROOT / args.layout), rtl_unchanged_verified=True,
            pressure_profile_unchanged=True, port_electrical_settings_unchanged=True,
            hardware_layout_verified=False,
            tests_reused_from=str(BASE / 'tests.json'), sram_written=False, flash_written=False)
(OUT / 'build_metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'verification_reuse.json').write_text(json.dumps({'baseline_release':str(release_path), 'baseline_firmware_sha256':release['sha256'], 'normalization':'Only replace the frozen baseline directory prefix; all other HDL, tables and config bytes unchanged', 'files':proof}, ensure_ascii=False, indent=2), encoding='utf-8')
shutil.copyfile(BASE / 'tests.json', OUT / 'tests.json')
shutil.copyfile(ROOT / args.layout, OUT / 'led_layout.json')
tcl = OUT / 'build.tcl'
tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n', encoding='utf-8')
print(json.dumps({'prepared':str(OUT), 'positions':meta['led_positions'], 'unchanged_inputs':len(proof)}, ensure_ascii=False), flush=True)
if not args.prepare_only:
    tool = 'D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
    with (OUT / 'build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([tool, str(tcl)], cwd=OUT, stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0, 'Build failed; inspect build.log'
    print(json.dumps({'tool_exit_code':0, 'build_dir':str(OUT)}))
