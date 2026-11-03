"""Rebase/freeze the complete EAE0 product; never programs any device."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'build/k5_lamp_follow_20261101'
OUT=ROOT/'build/natural_seven_20261101';NAME='soundcore_speaker_omr_60k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(source,target):target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def sources():
    tree=ET.parse(BASE/(NAME+'.gprj'));items=[]
    for node in tree.findall('./FileList/File'):
        p=Path(node.get('path'));rel=p.relative_to(BASE/'baseline')if p.is_relative_to(BASE/'baseline')else Path('rtl')/p.name
        items.append((node,p,rel))
    return tree,items
def initialize():
    marker=OUT/'baseline_sources.json'
    if marker.exists():print('Already initialized; working changes preserved');return
    OUT.mkdir(parents=True,exist_ok=True);_,items=sources();records=[]
    release=json.loads((BASE/'programming_latest_flash.json').read_text(encoding='utf8'))
    assert release['expected_user_code']=='0x0000EAE0'
    assert sha(Path(release['firmware']))==release['sha256']
    for _,p,rel in items:
        working=ROOT/rel
        if working.exists():save(working,OUT/'before'/rel)
        save(p,working);records.append({'relative':rel.as_posix(),'baseline':str(p),'baseline_sha256':sha(p)})
    for folder in ['app/android/app/src/main/java','app/android/app/src/test/java','web/phone-lab-20261030/lib']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file():save(p,OUT/'before'/p.relative_to(ROOT))
    for name in ['app/android/app/build.gradle.kts','app/android/app/src/main/AndroidManifest.xml',
        'rtl/expression_normalized.mem','rtl/expression_raw.mem','scripts/generate_expression_profile.py']:
        save(ROOT/name,OUT/'before'/name)
    # Restore the V1 ROMs actually used by EAE0, not the pending timbre candidate.
    for name in ['expression_normalized.mem','expression_raw.mem']:
        source=ROOT/'build/timbre_pressure_repair_20261101/before/rtl'/name
        assert source.exists();save(source,ROOT/'rtl'/name)
    marker.write_text(json.dumps(records,indent=2),encoding='utf8')
    print(json.dumps({'baseline':'EAE0','files':len(records),'pins_unchanged':True,'pending_E2B1_kept_separate':True}))
def freeze(build=False):
    tree,items=sources();src=OUT/'src';records=[]
    extras=['rtl/pitch_layout.v','rtl/note_step_table72.v']
    for node,old,rel in items:
        p=ROOT/rel;target=src/rel;save(p,target);node.set('path',target.as_posix());records.append({'relative':rel.as_posix(),'origin':str(p),'sha256':sha(p)})
    filelist=tree.find('./FileList')
    for name in extras:
        p=ROOT/name;target=src/name;save(p,target);ET.SubElement(filelist,'File',path=target.as_posix(),type='file.verilog',enable='1')
    assets={};queue=list(src.rglob('*.v'))+list(src.rglob('*.vh'));visited=set()
    while queue:
        p=queue.pop(0)
        if p in visited:continue
        visited.add(p)
        text=p.read_text(encoding='utf8')
        for literal in re.findall(r'"(D:/FPGA/Projects/soundcore_2026/[^"\n]+)"',text):
            original=Path(literal)
            if not original.is_file() or original.is_relative_to(src):continue
            target=src/'assets'/(hashlib.sha256(literal.encode()).hexdigest()[:8]+'_'+original.name)
            if literal not in assets:
                save(original,target);assets[literal]={'path':target.as_posix(),'sha256':sha(target)}
                if target.suffix in ['.v','.vh']:queue.append(target)
        for original,data in assets.items():text=text.replace(original,data['path'])
        p.write_text(text,encoding='utf8')
    for data in assets.values():data['sha256']=sha(Path(data['path']))
    project=OUT/(NAME+'.gprj');tree.write(project,encoding='utf8',xml_declaration=True)
    inputs={p.relative_to(src).as_posix():sha(p)for p in src.rglob('*')if p.is_file()}
    (OUT/'frozen_inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf8')
    (OUT/'build_metadata.json').write_text(json.dumps({'baseline_user_code':'0x0000EAE0','pitch_layout':2,'midi_min':36,'midi_max':107,
        'manual_octaves':5,'manual_natural_notes':35,'voices':32,'assets':assets,'source_records':records,'sram_written':False,'flash_written':False},indent=2),encoding='utf8')
    tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nrun all\n',encoding='utf8')
    print('Frozen complete natural-note product',len(inputs),'files')
    if build:
        with (OUT/'build.log').open('w',encoding='utf8')as log:
            result=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode==0,'Inspect build.log'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--init',action='store_true');p.add_argument('--freeze',action='store_true');p.add_argument('--build',action='store_true');a=p.parse_args()
    if a.init:initialize()
    if a.freeze or a.build:freeze(a.build)
