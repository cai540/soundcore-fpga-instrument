"""Reuse the verified EAE0 netlist; change only B10's physical drive strength."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/k5_lamp_follow_20261101'
OUT = ROOT / 'build/k5_lamp_drive16_20261101'
SRC = OUT / 'baseline'
NAME = 'soundcore_speaker_omr_60k'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
release = json.loads((ROOT / 'output/k5_lamp_follow_20261101/release.json').read_text(encoding='utf-8'))
assert release['flash_verified'] and release['user_code'] == '0x0000EAE0'
assert sha(Path(release['firmware'])) == release['sha256']

def port_rows(path):
    result = {}
    for row in html.fromstring(path.read_bytes()).xpath('//tr'):
        cells = [' '.join(c.text_content().split()) for c in row.xpath('./td')]
        if len(cells) == 20 and '/' in cells[2]:
            result[cells[0]] = cells
    return result

def validate_result():
    proof_path = OUT / 'verification_reuse.json'
    proof_data = json.loads(proof_path.read_text(encoding='utf-8'))
    meta_path = OUT / 'build_metadata.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    for item in proof_data['files']:
        p = Path(item['external_input']) if 'external_input' in item else SRC / item['file']
        assert sha(p) == item.get('sha256', item.get('snapshot_sha256'))
    netlist = OUT / 'impl/gwsynthesis' / (NAME + '.vg')
    actual_hash = sha(netlist)
    # Gowin may rerun synthesis automatically for a newly opened project.
    reused = actual_hash == proof_data.get('frozen_netlist_sha256', proof_data['netlist_sha256'])
    proof_data['frozen_netlist_sha256'] = proof_data.get('frozen_netlist_sha256', proof_data['netlist_sha256'])
    proof_data['netlist_sha256'] = actual_hash
    proof_data['synthesis_reused'] = reused
    if not reused:
        proof_data['scope'] = 'All RTL and memories are byte-identical to EAE0; only B10 DRIVE=8 becomes DRIVE=16. Gowin automatically regenerated synthesis; placement, routing, timing and bitstream generation rerun.'
    proof_path.write_text(json.dumps(proof_data, ensure_ascii=False, indent=2), encoding='utf-8')
    meta.update(synthesis_reused=reused, synthesis_regenerated=not reused, netlist_sha256=actual_hash)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    before = port_rows(BASE / 'impl/pnr' / (NAME + '.pin.html'))
    after = port_rows(OUT / 'impl/pnr' / (NAME + '.pin.html'))
    assert after.keys() == before.keys()
    for port, expected in before.items():
        wanted = expected.copy()
        if port == 'guide_button_led_o':
            wanted[8] = '16'
        assert after[port] == wanted, (port, after[port], wanted)
    assert (OUT / 'impl/pnr' / (NAME + '.fs')).stat().st_size > 1000000
    (OUT / 'lamp_drive_report_check.json').write_text(json.dumps({
        'passed': True, 'lamp_port': after['guide_button_led_o'],
        'all_other_port_properties_unchanged': True, 'netlist_sha256': actual_hash,
        'synthesis_reused': reused}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PNR verified: B10 16mA, all other port properties unchanged; synthesis reused=' + str(reused), flush=True)

if sys.argv[1:] == ['--validate-only']:
    validate_result()
    raise SystemExit(0)
assert not (OUT / 'impl').exists(), 'Preserve an existing build; do not overwrite it'

cst_rel = 'board/soundcore_speaker_omr_60k.cst'
old = 'IO_PORT "guide_button_led_o" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;'
new = old.replace('DRIVE=8', 'DRIVE=16')
proof = []
for p in (BASE / 'baseline').rglob('*'):
    if not p.is_file():
        continue
    rel = p.relative_to(BASE / 'baseline').as_posix()
    target = SRC / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if rel == cst_rel:
        original = p.read_text(encoding='utf-8')
        assert original.count(old) == 1
        changed = original.replace(old, new)
        assert changed.replace(new, old) == original
        target.write_text(changed, encoding='utf-8')
    else:
        shutil.copyfile(p, target)
        assert sha(p) == sha(target)
    proof.append({'file': rel, 'snapshot_sha256': sha(target), 'baseline_sha256': sha(p)})

tree = ET.parse(BASE / (NAME + '.gprj'))
for item in tree.findall('./FileList/File'):
    p = Path(item.attrib['path'])
    if p.is_relative_to(BASE / 'baseline'):
        item.set('path', (SRC / p.relative_to(BASE / 'baseline')).as_posix())
    elif p.is_file():
        proof.append({'external_input': str(p), 'sha256': sha(p)})
project = OUT / (NAME + '.gprj')
tree.write(project, encoding='utf-8', xml_declaration=True)

for name in ['tests.json', 'panel_menu_tests.json', 'lamp_tests.json']:
    shutil.copyfile(BASE / name, OUT / name)
    assert all(t['passed'] for t in json.loads((OUT / name).read_text(encoding='utf-8')))
shutil.copytree(BASE / 'impl/gwsynthesis', OUT / 'impl/gwsynthesis')
netlist = OUT / 'impl/gwsynthesis' / (NAME + '.vg')
assert sha(netlist) == sha(BASE / 'impl/gwsynthesis' / (NAME + '.vg'))

pin_file = BASE / 'impl/pnr' / (NAME + '.pin.html')
previous_ports = port_rows(pin_file)
assert previous_ports['guide_button_led_o'][2] == 'B17/1'
assert previous_ports['guide_button_led_o'][8] == '8'
pin_tree = html.fromstring(pin_file.read_bytes())
bonded = []
for row in pin_tree.xpath('//tr'):
    cells = [' '.join(c.text_content().split()) for c in row.xpath('./td')]
    if len(cells) == 18 and cells[0].endswith('/1'):
        bonded.append(cells)
other_drive = sum(int(c[8]) for c in previous_ports.values()
                  if c[2].endswith('/1') and c[0] != 'guide_button_led_o'
                  and c[4] in ['out', 'io'] and c[8].isdigit())
bank_check = {'bank': 1, 'bonded_io_count': len(bonded), 'bank_dc_limit_ma': len(bonded) * 8,
              'other_assigned_output_drive_sum_ma': other_drive, 'candidate_lamp_drive_ma': 16,
              'conservative_assigned_drive_sum_ma': other_drive + 16,
              'candidate_resistor_ohm': 270, 'resistor_tolerance_fraction': 0.05,
              'candidate_resistor_bound_ma_at_3v465': 3.465 / (270 * 0.95) * 1000,
              'source': 'https://cdn.gowinsemi.com.cn/DS981.pdf, GW5AT-60 Table 3-28 and bank DC current note',
              'measured_current': False}
assert bank_check['conservative_assigned_drive_sum_ma'] < bank_check['bank_dc_limit_ma']
assert bank_check['candidate_resistor_bound_ma_at_3v465'] < 16
(OUT / 'lamp_electrical_check.json').write_text(json.dumps(bank_check, ensure_ascii=False, indent=2), encoding='utf-8')
proof_data = {'changed_files': [cst_rel], 'files': proof,
              'scope': 'All RTL, memories and synthesized netlist are byte-identical to EAE0. Only B10 LVCMOS33 DRIVE=8 becomes DRIVE=16. Placement, routing, timing and bitstream generation are rerun.',
              'synthesis_reused_from': str(BASE / 'impl/gwsynthesis'), 'netlist_sha256': sha(netlist)}
(OUT / 'verification_reuse.json').write_text(json.dumps(proof_data, ensure_ascii=False, indent=2), encoding='utf-8')
meta = json.loads((BASE / 'build_metadata.json').read_text(encoding='utf-8'))
meta.update(baseline_firmware_sha256=release['sha256'], baseline_user_code=release['user_code'],
            modified_copied_files=[cst_rel], tests_reused_from=str(BASE / 'tests.json'),
            panel_tests_reused_from=str(BASE / 'panel_menu_tests.json'), rtl_unchanged_verified=True,
            lamp_drive_ma=16, lamp_control_position='B10', lamp_ground_position='B6',
            lamp_recommended_resistor_ohm=270, lamp_resistor_change_pending=True,
            lamp_electrical_check=bank_check, synthesis_reused=True, netlist_sha256=sha(netlist),
            sram_written=False, flash_written=False, lamp_physical_verified=False,
            apk=release['apk'])
(OUT / 'build_metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
tcl = OUT / 'build.tcl'
tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun pnr\n', encoding='utf-8')
print('EAE0 netlist and all RTL hashes verified; B10 drive 8->16 only. Running PNR.', flush=True)
with (OUT / 'build.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe', str(tcl)],
                            cwd=OUT, stdout=log, stderr=subprocess.STDOUT)
assert result.returncode == 0, 'Inspect build.log'
validate_result()
