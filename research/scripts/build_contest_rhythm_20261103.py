"""Preserve B703, add only a non-blocking rhythm-light tap. Never programs a board."""
from pathlib import Path
import shutil,hashlib,json,subprocess,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1];BASE=R/'build/product_repair_20261103'
B=R/'build/contest_audit_20261103/firmware';N='soundcore_speaker_omr_60k';B.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads((BASE/'frozen_inputs.json').read_text())
assert all(sha(BASE/'src'/p)==h for p,h in expected.items())
shutil.copytree(BASE/'src',B/'src',dirs_exist_ok=True)
for p in ['board/pressure_i2s_panel_oled_ble_experiment_top.v','rtl/guide_rhythm_cue.v','rtl/poly_synth32_tm.v','rtl/synth_voice.v']:
 shutil.copy2(R/p,B/'src'/p)
old=(BASE/'src').as_posix();new=(B/'src').as_posix()
for p in (B/'src').rglob('*'):
 if p.suffix in ('.v','.vh'):
  body=p.read_text(encoding='utf8').replace(old,new).replace('`include "rtl/',f'`include "{new}/rtl/')
  if p.name=='pressure_i2s_panel_oled_ble_experiment_top.v':
   import re
   reference=(BASE/'src/board/pressure_i2s_panel_oled_ble_experiment_top.v').read_text(encoding='utf8')
   catalog=re.search(r'`include "[^"\n]*product_song_catalog.vh"',reference)[0].replace(old,new)
   body=re.sub(r'`include "[^"\n]*product_song_catalog.vh"',catalog,body)
  p.write_text(body,encoding='utf8')
t=ET.parse(BASE/(N+'.gprj'))
for p in t.findall('./FileList/File'):p.set('path',p.get('path').replace(old,new))
ET.SubElement(t.find('FileList'),'File',path=(B/'src/rtl/guide_rhythm_cue.v').as_posix(),type='file.verilog',enable='1')
project=B/(N+'.gprj');t.write(project,encoding='utf8',xml_declaration=True)
(B/'frozen_inputs.json').write_text(json.dumps({p.relative_to(B/'src').as_posix():sha(p) for p in (B/'src').rglob('*')if p.is_file()},indent=2))
script=B/'build.tcl';script.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000B713\nset_option -place_option 4\nset_option -route_option 0\nrun all\n')
with (B/'build.log').open('w',encoding='utf8')as log:
 result=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(script)],cwd=B,stdout=log,stderr=subprocess.STDOUT)
print(f'B713 full build exit={result.returncode}; no programming')
raise SystemExit(result.returncode)
