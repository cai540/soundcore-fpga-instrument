"""Freeze the accepted 8936 product; change only its indicator output cone."""
from pathlib import Path
import hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/native_panel_playback_20261031';OUT=ROOT/'build/k5_lamp_follow_20261101';SRC=OUT/'baseline'
NAME='soundcore_speaker_omr_60k';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((ROOT/'output/native_panel_playback_20261031/release.json').read_text(encoding='utf-8'))
assert sha(Path(release['firmware']))==release['sha256']
old='assign guide_button_led=ui_state==RUN || (ui_state==PAUSE && blink);'
new='assign guide_button_led=!(demo_mode ? player_finished : guide_finished) &&\n        (ui_state==RUN || (ui_state==PAUSE && blink));'
changed=['rtl/front_panel_product.v','board/pressure_i2s_panel_oled_ble_experiment_top.v'];proof=[]
for p in (BASE/'baseline').rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(BASE/'baseline').as_posix();target=SRC/rel;target.parent.mkdir(parents=True,exist_ok=True)
    if p.suffix in ['.v','.vh','.cst','.sdc']:
        original=p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix());text=original
        if rel==changed[0]:
            assert text.count(old)==1 and text.count('input wire player_finished,')==1
            text=text.replace('input wire player_finished,','input wire player_finished,\n    input wire guide_finished,').replace(old,new)
            assert text.replace('input wire player_finished,\n    input wire guide_finished,','input wire player_finished,').replace(new,old)==original
        elif rel==changed[1]:
            before='.player_finished(autoplay_finished),.bank(ui_bank)'
            after='.player_finished(autoplay_finished),.guide_finished(guide_complete),.bank(ui_bank)'
            assert text.count(before)==1;text=text.replace(before,after)
            assert text.replace(after,before)==original
        else:assert text==original
        target.write_text(text,encoding='utf-8')
    else:shutil.copyfile(p,target)
    if rel not in changed:proof.append({'file':rel,'snapshot_sha256':sha(target),'baseline_sha256':sha(p)})
p=ROOT/'rtl/front_panel_product.v';text=p.read_text(encoding='utf-8')
if old in text:p.write_text(text.replace('input wire player_finished,','input wire player_finished,\n    input wire guide_finished,').replace(old,new),encoding='utf-8')
tree=ET.parse(BASE/(NAME+'.gprj'))
for item in tree.findall('./FileList/File'):
    p=Path(item.attrib['path'])
    if p.is_relative_to(BASE/'baseline'):item.set('path',(SRC/p.relative_to(BASE/'baseline')).as_posix())
    elif p.is_file():proof.append({'external_input':str(p),'sha256':sha(p)})
project=OUT/(NAME+'.gprj');tree.write(project,encoding='utf-8',xml_declaration=True)
for name in ['tests.json','panel_menu_tests.json']:shutil.copyfile(BASE/name,OUT/name)
proof_data={'changed_files':changed,'files':proof,'scope':'Only K5 indicator completion gating plus its completion input connection. The new input is read only by the LED output assignment; all pre-existing panel registers and controls are byte-identical after removing that assignment/port edit. All audio/model/song/IO inputs unchanged.'}
(OUT/'verification_reuse.json').write_text(json.dumps(proof_data,ensure_ascii=False,indent=2),encoding='utf-8')
binary=OUT/'lamp_test.vvp'
c=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012','-s','tb_k5_lamp_follow','-o',str(binary),str(ROOT/'tb/tb_k5_lamp_follow.v'),str(SRC/'rtl/front_panel_product.v')],capture_output=True,text=True,cwd=ROOT)
assert c.returncode==0,(c.stdout,c.stderr)
r=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe',str(binary)],capture_output=True,text=True,cwd=ROOT,timeout=20)
passed=r.returncode==0 and 'PASS:'in r.stdout
lamp_tests=[{'test':'tb_k5_lamp_follow','passed':passed,'output':r.stdout+r.stderr}]
(OUT/'lamp_tests.json').write_text(json.dumps(lamp_tests,ensure_ascii=False,indent=2),encoding='utf-8');print(r.stdout+r.stderr,flush=True);assert passed
meta=json.loads((BASE/'build_metadata.json').read_text(encoding='utf-8'))
meta.update(k5_lamp_follow=True,baseline_firmware_sha256=release['sha256'],baseline_user_code=release['user_code'],modified_copied_files=changed,tests_reused_from=str(BASE/'tests.json'),panel_tests_reused_from=str(BASE/'panel_menu_tests.json'),rtl_unchanged_verified=False,sram_written=False,flash_written=False)
(OUT/'build_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf-8')
print('Building full product; only lamp output cone changed',flush=True)
with (OUT/'build.log').open('w',encoding='utf-8')as log:r=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
assert r.returncode==0,'inspect build.log'
print('Complete Gowin build PASS',flush=True)
