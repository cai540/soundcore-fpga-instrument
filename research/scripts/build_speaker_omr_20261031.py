"""Build an isolated MAX98357A I2S variant of the verified complete OMR image."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/fpga_omr_20261031'
OUT=ROOT/'build/speaker_omr_20261031'
SRC=OUT/'baseline'
SRC.mkdir(parents=True,exist_ok=True)
old=ET.parse(BASE/'gowin_integrated/soundcore_omr_60k.gprj')
snapshot=BASE/'baseline'
for p in snapshot.rglob('*'):
    if not p.is_file():continue
    target=SRC/p.relative_to(snapshot);target.parent.mkdir(parents=True,exist_ok=True)
    if p.suffix in ['.v','.vh','.cst','.sdc']:
        target.write_text(p.read_text(encoding='utf-8').replace(snapshot.as_posix(),SRC.as_posix()),encoding='utf-8')
    else:shutil.copyfile(p,target)

# Preserve all non-audio ports and the early/expression/upload/OMR configuration.
wrapper=SRC/'board/soundcore_melody_top.v'
text=wrapper.read_text(encoding='utf-8')
assert '.HEADPHONE_OUTPUT(1)'in text and '.EARLY_FORCE_ENABLE(1)'in text and '.CONTINUOUS_EXPRESSION(1)'in text
text=text.replace('module soundcore_melody_top','module soundcore_speaker_omr_top').replace('.HEADPHONE_OUTPUT(1)','.HEADPHONE_OUTPUT(0)')
for old_name,new_name in [('HP_BCK','dac_bclk'),('HP_WS','dac_lrclk'),('HP_DIN','dac_din')]:text=text.replace(old_name,new_name)
text=text.replace('    output wire PA_EN\n','').replace('    output wire guide_button_led_o,','    output wire guide_button_led_o')
text=text.replace("    assign PA_EN=1'b0;\n",'')
text=text.replace('// Opt-in early-pressure experiment. Saved profile is compiled in; no manual boot calibration.',
                  '// Complete MAX98357A speaker variant: standard I2S, early pressure, expression, uploaded score and OMR.')
wrapper.write_text(text,encoding='utf-8')
controls=SRC/'rtl/front_panel_five_keys.v';text=controls.read_text(encoding='utf-8')
assert text.count("volume_level <= 5'd16;")==1
controls.write_text(text.replace("volume_level <= 5'd16;","volume_level <= 5'd6;"),encoding='utf-8')

cst=SRC/'board/soundcore_speaker_omr_60k.cst'
shutil.copyfile(ROOT/'board/pressure_i2s_panel_oled_ble_experiment_60k.cst',cst)
def pin_map(path):return dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([^;]+);',path.read_text(encoding='utf-8')))
a,b=pin_map(snapshot/'board/soundcore_headphone_60k.cst'),pin_map(cst)
assert all(a[k]==b[k]for k in set(a)&set(b))
assert {k:b[k]for k in set(b)-set(a)}=={'dac_bclk':'Y21','dac_lrclk':'Y22','dac_din':'AB21'}
assert len(set(b.values()))==len(b)
changes=[]
for p in SRC.rglob('*'):
    if not p.is_file():continue
    prior=snapshot/p.relative_to(SRC)
    if not prior.exists():continue
    previous=prior.read_text(encoding='utf-8').replace(snapshot.as_posix(),SRC.as_posix())if p.suffix in ['.v','.vh','.cst','.sdc']else None
    equal=p.read_text(encoding='utf-8')==previous if previous is not None else p.read_bytes()==prior.read_bytes()
    if not equal:changes.append(str(p.relative_to(SRC)).replace('\\','/'))
assert sorted(changes)==['board/soundcore_melody_top.v','rtl/front_panel_five_keys.v'],changes

project=OUT/'soundcore_speaker_omr_60k.gprj'
tree=old.getroot()
for item in tree.findall('./FileList/File'):
    p=Path(item.attrib['path'])
    if p==snapshot/'board/soundcore_headphone_60k.cst':p=cst
    elif p.is_relative_to(snapshot):p=SRC/p.relative_to(snapshot)
    item.set('path',p.as_posix())
ET.ElementTree(tree).write(project,encoding='utf-8',xml_declaration=True)
tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf-8')
meta={'baseline_firmware_sha256':'9c97b48663a22e4b0f88f5195cf587106e6e35b5dacef8f56964e3ff9870f3a1',
      'audio_path':'MAX98357A_standard_I2S','startup_volume':6,'model_crc32':3866258960,
      'modified_copied_files':changes,'shared_pin_count':len(set(a)&set(b)),'shared_pins_unchanged':True,
      'old_audio_pins_removed':{k:a[k]for k in set(a)-set(b)},'speaker_pins':{k:b[k]for k in set(b)-set(a)},
      'sram_written':False,'flash_written':False}
(OUT/'build_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
tool='D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
with (OUT/'build.log').open('w',encoding='utf-8')as log:
    result=subprocess.run([tool,str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0,'Speaker build failed: read build.log'
print(json.dumps({'tool_exit_code':result.returncode,'output':str(OUT)}))
