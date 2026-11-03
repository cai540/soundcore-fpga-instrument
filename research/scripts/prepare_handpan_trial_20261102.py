"""Freeze an isolated full-product handpan candidate. Never programs a device."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET
import prepare_low_latency_20261101 as base
R=Path(__file__).resolve().parents[1];O=R/'build/handpan_trial_20261102';NAME=base.NAME

def freeze(build=False):
    base.OUT=O
    base.freeze(False)
    p=O/(NAME+'.gprj');tree=ET.parse(p);files=tree.find('./FileList')
    target=O/'src/rtl/handpan_modal32.v';target.parent.mkdir(parents=True,exist_ok=True)
    text=(R/'rtl/handpan_modal32.v').read_text(encoding='utf8')
    sine=O/'src/rtl/handpan_sine.mem';shutil.copy2(R/'rtl/handpan_sine.mem',sine)
    target.write_text(text.replace((R/'rtl/handpan_sine.mem').as_posix(),sine.as_posix()),encoding='utf8')
    ET.SubElement(files,'File',path=target.as_posix(),type='file.verilog',enable='1')
    tree.write(p,encoding='utf8',xml_declaration=True)
    before=O/'before/board/soundcore_speaker_omr_60k.cst';now=O/'src/board/soundcore_speaker_omr_60k.cst'
    assert before.read_bytes()==now.read_bytes(),'Pin assignments changed'
    inputs={f.relative_to(O/'src').as_posix():hashlib.sha256(f.read_bytes()).hexdigest()for f in (O/'src').rglob('*')if f.is_file()}
    (O/'frozen_inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf8')
    (O/'build.tcl').write_text(f'open_project {{{p.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 00004850\nrun all\n',encoding='utf8')
    if build:
        with (O/'build.log').open('w',encoding='utf8')as log:
            run=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(O/'build.tcl')],cwd=O,stdout=log,stderr=subprocess.STDOUT)
        assert run.returncode==0,'Inspect build.log'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');a=p.parse_args();freeze(a.build)
