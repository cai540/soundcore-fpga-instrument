"""Freeze EAE0's complete product, replacing only stored sound/AI6 parameters."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/k5_lamp_follow_20261101'
OUT=ROOT/'build/timbre_pressure_repair_20261101'
SRC=OUT/'src';SRC.mkdir(parents=True,exist_ok=True)
NAME='soundcore_speaker_omr_60k'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((BASE/'programming_latest_flash.json').read_text(encoding='utf-8'))
assert release['expected_user_code']=='0x0000EAE0' and sha(Path(release['firmware']))==release['sha256']
changed={'rtl/expressive_texture.v','rtl/fsr_strike_detector.v'}
tree=ET.parse(BASE/(NAME+'.gprj'))
mapping={};records=[]
for entry in tree.findall('./FileList/File'):
    original=Path(entry.attrib['path'])
    rel=original.relative_to(BASE/'baseline') if original.is_relative_to(BASE/'baseline') else Path('external')/original.name
    working=ROOT/rel
    actual=working if rel.as_posix() in changed else original
    target=SRC/rel;target.parent.mkdir(parents=True,exist_ok=True)
    mapping[original.as_posix()]=target.as_posix()
    shutil.copy2(actual,target)
    records.append(dict(relative=rel.as_posix(),origin=str(actual),original_sha256=sha(original),copied_sha256=sha(target),modified=rel.as_posix() in changed))
    entry.set('path',target.as_posix())

# Resolve and freeze all literal synthesis assets, including coefficient ROMs.
# EAE0 referred to root ROMs directly; never edit its archived bitstream or source.
asset_map={}
for record in records:
    path=SRC/record['relative']
    if path.suffix not in ('.v','.vh'):continue
    text=path.read_text(encoding='utf-8')
    for literal in re.findall(r'"(D:/FPGA/Projects/soundcore_2026/[^"\n]+)"',text):
        original=Path(literal)
        if not original.is_file():continue
        target=SRC/'assets'/(hashlib.sha256(literal.encode()).hexdigest()[:8]+'_'+original.name)
        target.parent.mkdir(exist_ok=True)
        if literal not in asset_map:
            shutil.copy2(original,target)
            asset_map[literal]={'path':target.as_posix(),'sha256':sha(target)}
    for original,data in asset_map.items():text=text.replace(original,data['path'])
    path.write_text(text,encoding='utf-8')

for p in ['config/expression_profile_v2.json','config/pressure_profile_ai6_20261101.json','rtl/pressure_profile_config.vh','rtl/pressure_profile_curve.vh']:
    target=SRC/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,target)

project=OUT/(NAME+'.gprj');tree.write(project,encoding='utf-8',xml_declaration=True)
metadata=json.loads((BASE/'build_metadata.json').read_text(encoding='utf-8'))
metadata.update(baseline_user_code='0x0000EAE0',baseline_firmware_sha256=release['sha256'],
    modified_copied_files=sorted(changed),source_records=records,asset_records=asset_map,
    calibrated_input_scale_q12=[4096]*6+[4544],pressure_profile_id='fbb94330',
    pressure_profile_unchanged=False,input_scale_evidence=json.loads((ROOT/'config/pressure_profile_ai6_20261101.json').read_text(encoding='utf-8'))['input_scale_evidence'],
    expression_profile='config/expression_profile_v2.json',texture_shift=18,
    channel7_calibration_is_field_estimate=True,base_pressure_curve_unchanged=True,
    actual_channel7_adc_span_measured=False,hardware_audio_verified=False,
    sram_written=False,flash_written=False)
(OUT/'build_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf-8')
inputs={p.relative_to(SRC).as_posix():sha(p) for p in SRC.rglob('*') if p.is_file()}
(OUT/'frozen_inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
print(json.dumps({'frozen_files':len(inputs),'assets':len(asset_map),'baseline':'EAE0','audio_output':'MAX98357A standard I2S','pin_changes':False}),flush=True)
if __name__=='__main__' and '--build' in __import__('sys').argv:
    with (OUT/'build.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0,'Inspect build.log'
    print('Complete product Gowin build finished',flush=True)
