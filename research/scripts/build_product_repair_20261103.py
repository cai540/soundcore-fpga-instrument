"""Freeze the A6C4 product with verified repair sources; never programs hardware."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]
BASE=R/'build/harmonica_refinement_20261102'
B=R/'build/product_repair_20261103'
N='soundcore_speaker_omr_60k'
CHANGED=['rtl/product_tools_engine.v','rtl/ble_control_endpoint.v','rtl/strike_voice_allocator32.v',
 'rtl/uploaded_song_engine.v','rtl/fsr_strike_detector.v','rtl/pressure_expression32.v','rtl/handpan_modal32.v','rtl/rock_voice_fx.v','board/soundcore_melody_top.v','board/pressure_i2s_additive32_core.v']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((BASE/'frozen_inputs.json').read_text())
assert all(sha(BASE/'src'/p)==h for p,h in frozen.items())
shutil.copytree(BASE/'src',B/'src',dirs_exist_ok=True)
for name in CHANGED:shutil.copy2(R/name,B/'src'/name)
old=(BASE/'src').as_posix();new=(B/'src').as_posix()
for f in (B/'src').rglob('*'):
 if f.suffix in ('.v','.vh'):f.write_text(f.read_text('utf8').replace(old,new),encoding='utf8')
tree=ET.parse(BASE/(N+'.gprj'))
for f in tree.findall('./FileList/File'):f.set('path',f.get('path').replace(old,new))
project=B/(N+'.gprj');tree.write(project,encoding='utf8',xml_declaration=True)
stage='syn' if '--syn-only' in sys.argv else 'all'
(B/'build.tcl').write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000B703\nset_option -place_option 1\nrun {stage}\n',encoding='utf8')
(B/'frozen_inputs.json').write_text(json.dumps({p.relative_to(B/'src').as_posix():sha(p) for p in (B/'src').rglob('*') if p.is_file()},indent=2))
print('Frozen B703 complete speaker candidate; Flash remains A6C4',flush=True)
with (B/'build.log').open('w',encoding='utf8') as log:
 result=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(B/'build.tcl')],cwd=B,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0,'Inspect product_repair_20261103/build.log'
print('synthesis finished' if stage=='syn' else 'PNR finished',flush=True)
