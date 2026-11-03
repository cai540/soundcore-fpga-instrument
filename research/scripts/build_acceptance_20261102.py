"""Freeze and build the complete A623 acceptance candidate. Never programs hardware."""
from pathlib import Path
import sys,re,shutil,hashlib,json,subprocess,xml.etree.ElementTree as ET,argparse
import prepare_low_latency_20261101 as base
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';NAME=base.NAME
EXTRA=['product_tools_engine.v','product_tools_subsystem.v','product_audio_analyzer.v','audio_record_adpcm.v','oled_analysis_columns.v',
 'pitch_layout.v','note_step_table72.v','handpan_modal32.v','rock_voice_fx.v']
def freeze():
 B.mkdir(parents=True,exist_ok=True);tree,items=base.sources();filelist=tree.find('./FileList');copied=set()
 for node,old,rel in items:
  source=R/rel;target=B/'src'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
  node.set('path',target.as_posix());copied.add(source.name)
 for name in EXTRA:
  if name not in copied:
   target=B/'src/rtl'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'rtl'/name,target)
   ET.SubElement(filelist,'File',path=target.as_posix(),type='file.verilog',enable='1');copied.add(name)
 shutil.copy2(R/'rtl/instrument_attack.vh',B/'src/rtl/instrument_attack.vh')
 assets={};pending=list((B/'src').rglob('*.v'))+list((B/'src').rglob('*.vh'));seen=set()
 while pending:
  p=pending.pop()
  if p in seen:continue
  seen.add(p);s=p.read_text('utf8').replace('"rtl/instrument_attack.vh"','"src/rtl/instrument_attack.vh"')
  for literal in re.findall(r'"(D:/FPGA/Projects/soundcore_2026/[^"\n]+)"',s):
   original=Path(literal)
   if not original.is_file()or original.is_relative_to(B/'src'):continue
   if literal not in assets:
    target=B/'src/assets'/(hashlib.sha256(literal.encode()).hexdigest()[:8]+'_'+original.name)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target);assets[literal]=target
    if target.suffix in('.v','.vh'):pending.append(target)
   s=s.replace(literal,assets[literal].as_posix())
  if p.name=='product_audio_analyzer.v':s='`define TOOLS_GOWIN_RAM\n'+s
  p.write_text(s,encoding='utf8')
 project=B/(NAME+'.gprj');tree.write(project,encoding='utf8',xml_declaration=True)
 (B/'build.tcl').write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000A623\nrun all\n',encoding='utf8')
 hashes={p.relative_to(B/'src').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in (B/'src').rglob('*')if p.is_file()}
 (B/'frozen_inputs.json').write_text(json.dumps(hashes,indent=2))
 print('Frozen',len(hashes),'inputs; UserCode A623; no programmer',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');a=p.parse_args();freeze()
 if a.build:
  with(B/'build.log').open('w',encoding='utf8')as log:
   r=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(B/'build.tcl')],cwd=B,stdout=log,stderr=subprocess.STDOUT)
  assert r.returncode==0,'Inspect build/acceptance_20261102/build.log'
  print('Gowin completed',flush=True)
