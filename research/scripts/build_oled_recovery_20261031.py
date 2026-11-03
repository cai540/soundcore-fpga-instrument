"""Freeze the full 05D8 product, changing only OLED startup and bus recovery."""
from pathlib import Path
import hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/speaker_led8_20261031'
OUT=ROOT/'build/oled_recovery_20261031'
SRC=OUT/'baseline'
NAME='soundcore_speaker_omr_60k'
changed=['rtl/oled_i2c_write2.v','rtl/oled_status_ssd1315.v','board/pressure_i2s_panel_oled_ble_experiment_top.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((ROOT/'output/speaker_led8_20261031/release.json').read_text(encoding='utf-8'))
assert sha(Path(release['firmware']))==release['sha256']
proof=[]
for p in (BASE/'baseline').rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(BASE/'baseline').as_posix()
    target=SRC/rel;target.parent.mkdir(parents=True,exist_ok=True)
    if rel=='board/pressure_i2s_panel_oled_ble_experiment_top.v':
        text=p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix())
        before='oled_status_ssd1315 #(.LONG_SONG_UI(1),.LYRIC_OVERLAY(1),.CAPTURE_OVERLAY(UPLOADED_SCORE_ENABLE)) display ('
        after='oled_status_ssd1315 #(.LONG_SONG_UI(1),.LYRIC_OVERLAY(1),.CAPTURE_OVERLAY(UPLOADED_SCORE_ENABLE),.POWERUP_CYCLES(1228800),.I2C_DIV(30)) display ('
        assert text.count(before)==1 and '.OMR_ENABLE(1)'in text
        text=text.replace(before,after)
        assert text.replace(after,before)==p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix())
        target.write_text(text,encoding='utf-8')
    elif rel in changed:
        text=(ROOT/rel).read_text(encoding='utf-8')
        text=text.replace((ROOT/'board').as_posix(),(SRC/'board').as_posix())
        target.write_text(text,encoding='utf-8')
    elif p.suffix in ['.v','.vh','.cst','.sdc']:
        target.write_text(p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix()),encoding='utf-8')
    else:shutil.copyfile(p,target)
    if rel not in changed:
        if p.suffix in ['.v','.vh','.cst','.sdc']:
            assert target.read_text(encoding='utf-8')==p.read_text(encoding='utf-8').replace(BASE.as_posix(),OUT.as_posix())
        else:assert p.read_bytes()==target.read_bytes()
        proof.append({'file':rel,'snapshot_sha256':sha(target),'baseline_sha256':sha(p)})

tree=ET.parse(BASE/(NAME+'.gprj'))
for item in tree.findall('./FileList/File'):
    p=Path(item.attrib['path'])
    if p.is_relative_to(BASE/'baseline'):item.set('path',(SRC/p.relative_to(BASE/'baseline')).as_posix())
    elif p.is_file():proof.append({'external_input':str(p),'sha256':sha(p)})
project=OUT/(NAME+'.gprj');tree.write(project,encoding='utf-8',xml_declaration=True)
meta=json.loads((BASE/'build_metadata.json').read_text(encoding='utf-8'))
meta.update(baseline_firmware_sha256=release['sha256'],baseline_user_code=release['user_code'],
            modified_copied_files=changed,rtl_unchanged_verified=False,
            oled_recovery=True,oled_powerup_cycles=1228800,oled_i2c_div=30,
            tests_reused_from=str(BASE/'tests.json'),sram_written=False,flash_written=False)
(OUT/'build_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'verification_reuse.json').write_text(json.dumps({'changed_files':changed,'files':proof,
    'scope':'Audio, pressure, buttons, song, BLE, model and all CST bytes unchanged after snapshot prefix relocation; seven audio/pressure regressions reused; OLED regressions rerun.'},ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(BASE/'tests.json',OUT/'tests.json')

tests=['tb_oled_pin_recovery','tb_oled_i2c_write2','tb_oled_reconnect',
       'tb_oled_dual_address','tb_oled_event_refresh','tb_oled_force_geometry',
       'tb_oled_karaoke_integration','tb_capture_oled_i2c']
iv='D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe'
vvp='D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe'
sources=[str(SRC/'rtl'/name) for name in ['oled_i2c_write2.v','oled_status_ssd1315.v','oled_lyric_columns.v','oled_capture_columns.v']]
results=[]
for test in tests:
    binary=OUT/'tests'/(test+'.vvp');binary.parent.mkdir(exist_ok=True)
    compilation=subprocess.run([iv,'-g2012','-s',test,'-o',str(binary),str(ROOT/'tb'/(test+'.v')),*sources],capture_output=True,text=True,cwd=ROOT)
    assert compilation.returncode==0,(compilation.returncode,compilation.stdout,compilation.stderr)
    run=subprocess.run([vvp,str(binary)],capture_output=True,text=True,cwd=ROOT,timeout=90)
    body=run.stdout+run.stderr
    passed=run.returncode==0 and 'PASS:' in body
    results.append({'test':test,'passed':passed,'output':body})
    (OUT/'oled_tests.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(test+': '+('PASS' if passed else body),flush=True)
    assert passed,test

tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf-8')
print('Building complete OLED recovery candidate',flush=True)
with (OUT/'build.log').open('w',encoding='utf-8') as log:
    build=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
assert build.returncode==0,'inspect build.log'
print('Complete Gowin build PASS',flush=True)
