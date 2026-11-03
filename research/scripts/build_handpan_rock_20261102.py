"""Isolated 4852 full-product build; no programmer is invoked."""
from pathlib import Path
import argparse,hashlib,json,subprocess,shutil,xml.etree.ElementTree as ET
import prepare_handpan_trial_20261102 as trial
R=Path(__file__).resolve().parents[1];B=R/'build/handpan_rock_20261102'

def freeze():
    trial.O=B;trial.freeze(False)
    p=B/'soundcore_speaker_omr_60k.gprj';tree=ET.parse(p)
    for name in ['rock_voice_fx.v','rock_softclip.mem']:
        source=R/'rtl'/name;target=B/'src/rtl'/name
        if source.suffix=='.v':
            target.write_text(source.read_text(encoding='utf8').replace((R/'rtl/rock_softclip.mem').as_posix(),(B/'src/rtl/rock_softclip.mem').as_posix()),encoding='utf8')
            ET.SubElement(tree.find('./FileList'),'File',path=target.as_posix(),type='file.verilog',enable='1')
        else:shutil.copy2(source,target)
    tree.write(p,encoding='utf8',xml_declaration=True)
    (B/'frozen_inputs.json').write_text(json.dumps({f.relative_to(B/'src').as_posix():hashlib.sha256(f.read_bytes()).hexdigest()for f in (B/'src').rglob('*')if f.is_file()},indent=2),encoding='utf8')
    (B/'build.tcl').write_text(f'open_project {{{p.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 00004852\nrun all\n',encoding='utf8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');args=parser.parse_args()
    freeze()
    if args.build:
        with (B/'build.log').open('w',encoding='utf8')as log:
            run=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(B/'build.tcl')],cwd=B,stdout=log,stderr=subprocess.STDOUT)
        assert run.returncode==0,'Inspect build.log'
