"""Freeze and build the LED-remapped, uniform-pressure complete speaker image."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/speaker_omr_20261031'
NAME = 'soundcore_speaker_omr_60k'
parser = argparse.ArgumentParser()
parser.add_argument('--prepare-only', action='store_true')
parser.add_argument('--calibrate-ai6', action='store_true')
args = parser.parse_args()
OUT = ROOT / ('build/speaker_led_pressure_calibrated_20261031' if args.calibrate_ai6 else 'build/speaker_led_pressure_20261031')
SRC = OUT / 'baseline'

for p in (BASE / 'baseline').rglob('*'):
    if not p.is_file():
        continue
    target = SRC / p.relative_to(BASE / 'baseline')
    target.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix in ('.v', '.vh', '.cst', '.sdc'):
        target.write_text(p.read_text(encoding='utf-8').replace(BASE.as_posix(), OUT.as_posix()), encoding='utf-8')
    else:
        target.write_bytes(p.read_bytes())

changed = ['board/pressure_i2s_additive32_core.v', 'rtl/pressure_expression32.v']
if args.calibrate_ai6:
    changed+=['rtl/fsr_strike_detector.v']
    profile_path=ROOT/'config/pressure_profile_ai6_20261031.json'
    profile=json.loads(profile_path.read_text(encoding='utf-8'))
    profile_id=zlib.crc32(json.dumps(profile,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())&0xffffffff
    assert f"PRESSURE_PROFILE_ID=32'h{profile_id:08x}" in (ROOT/'rtl/fsr_strike_detector.v').read_text(encoding='utf-8')
for name in changed:
    (SRC / name).write_text((ROOT / name).read_text(encoding='utf-8'), encoding='utf-8')
cst = SRC / 'board' / (NAME + '.cst')
# Reproduce this historical layout from its frozen baseline even when the
# current product CST has moved to another connector layout.
expected = dict(zip((f'pad_led_o[{i}]' for i in range(7)), ['A14', 'A13', 'B16', 'B15', 'A16', 'A15', 'A20']))
body=cst.read_text(encoding='utf-8')
for signal,ball in expected.items():
    body,count=re.subn(r'IO_LOC "'+re.escape(signal)+r'" [^;]+;',f'IO_LOC "{signal}" {ball};',body)
    assert count==1,signal
cst.write_text(body,encoding='utf-8')
def pins(path):
    return dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([^;]+);', path.read_text(encoding='utf-8')))
old = pins(BASE / 'baseline/board' / (NAME + '.cst'))
new = pins(cst)
assert set(old) == set(new) and len(set(new.values())) == len(new)
assert {k: new[k] for k in new if k.startswith('pad_led_o')} == expected
assert all(new[k] == old[k] for k in new if k not in expected)
assert not set(expected.values()) & {'E14', 'E13', 'C15', 'C14', 'B13', 'C13'}

tree = ET.parse(BASE / (NAME + '.gprj'))
for item in tree.findall('./FileList/File'):
    path = Path(item.attrib['path'])
    if path.is_relative_to(BASE / 'baseline'):
        item.set('path', (SRC / path.relative_to(BASE / 'baseline')).as_posix())
project = OUT / (NAME + '.gprj')
tree.write(project, encoding='utf-8', xml_declaration=True)
metadata = json.loads((BASE / 'build_metadata.json').read_text(encoding='utf-8'))
metadata.update(
    baseline_firmware_sha256=hashlib.sha256((BASE / 'impl/pnr' / (NAME + '.fs')).read_bytes()).hexdigest(),
    modified_copied_files=changed + ['board/' + NAME + '.cst'],
    shared_pin_count=22, shared_pins_unchanged=True, speaker_pins={'dac_bclk':'Y21','dac_lrclk':'Y22','dac_din':'AB21'},
    led_positions=['A4','B4','A5','B5','A7','B7','A8'], led_balls=expected,
    uniform_pad_velocity=True, expression_exact_endpoints=True,
    channel7_hardware_cause_verified=False, pressure_profile_unchanged=True,
    sram_written=False, flash_written=False)
metadata.pop('old_audio_pins_removed', None)
if args.calibrate_ai6:
    metadata.update(pressure_profile_unchanged=False,base_pressure_curve_unchanged=True,
                    calibrated_input_scale_q12=profile['channel_input_scale_q12'],
                    input_scale_evidence=profile['input_scale_evidence'],pressure_profile_id=f'{profile_id:08x}')
    for name in ['config/pressure_profile_ai6_20261031.json','rtl/pressure_profile_config.vh','rtl/pressure_profile_curve.vh']:
        target=SRC/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
(OUT / 'build_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
tcl = OUT / 'build.tcl'
tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n', encoding='utf-8')
print(json.dumps({'prepared':str(OUT), 'led_positions':metadata['led_positions'], 'unchanged_other_pins':22}), flush=True)
if not args.prepare_only:
    tool = 'D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
    with (OUT / 'build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([tool, str(tcl)], cwd=OUT, stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0, 'Build failed; see build.log'
    print(json.dumps({'tool_exit_code':result.returncode, 'output':str(OUT)}))
