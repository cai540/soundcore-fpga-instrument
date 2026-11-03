"""Freeze A623 complete product plus the scoped reed revision. Never programs hardware."""
from pathlib import Path
import hashlib,json,re,shutil,xml.etree.ElementTree as ET,subprocess,argparse
R=Path(__file__).resolve().parents[1];BASE=R/'build/acceptance_20261102';B=R/'build/harmonica_refinement_20261102';N='soundcore_speaker_omr_60k'
CHANGED=['rtl/expressive_texture.v','rtl/expression_normalized.mem','rtl/expression_raw.mem','rtl/instrument_attack.vh','rtl/poly_synth32_tm.v']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
    original=json.loads((BASE/'frozen_inputs.json').read_text());assert all(sha(BASE/'src'/p)==h for p,h in original.items())
    shutil.copytree(BASE/'src',B/'src',dirs_exist_ok=True)
    for name in CHANGED:shutil.copy2(R/name,B/'src'/name)
    prefix=(BASE/'src').as_posix();new=(B/'src').as_posix();assets={}
    for f in(B/'src').rglob('*'):
        if f.suffix not in('.v','.vh'):continue
        s=f.read_text('utf8').replace(prefix,new).replace('"rtl/instrument_attack.vh"','"src/rtl/instrument_attack.vh"')
        for path in re.findall(r'"(D:/FPGA/Projects/soundcore_2026/[^"\n]+)"',s):
            source=Path(path)
            if not source.is_file()or source.is_relative_to(B/'src'):continue
            target=B/'src/assets'/(hashlib.sha256(path.encode()).hexdigest()[:8]+'_'+source.name)
            target.parent.mkdir(exist_ok=True);shutil.copy2(source,target);assets[path]=target.as_posix();s=s.replace(path,target.as_posix())
        f.write_text(s,encoding='utf8')
    # Legacy asset copies are intentionally preserved; the new source points
    # to the updated coefficient asset with the same literal-path hash.
    tree=ET.parse(BASE/(N+'.gprj'))
    for f in tree.findall('./FileList/File'):f.set('path',f.get('path').replace(prefix,new))
    project=B/(N+'.gprj');tree.write(project,encoding='utf8',xml_declaration=True)
    (B/'build.tcl').write_text(f'open_project {{{project.as_posix()}}}\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000A6C4\nrun all\n',encoding='utf8')
    frozen={p.relative_to(B/'src').as_posix():sha(p)for p in(B/'src').rglob('*')if p.is_file()}
    (B/'frozen_inputs.json').write_text(json.dumps(frozen,indent=2))
    for p in(B/'src').rglob('*.cst'):assert sha(p)==sha(BASE/'src'/p.relative_to(B/'src'))
    assert sha(B/'src/rtl/synth_voice.v')==sha(BASE/'src/rtl/synth_voice.v')
    (B/'build_metadata.json').write_text(json.dumps(dict(base='A623',user_code='0x0000A6C4',audio_output='MAX98357A standard I2S',modified=CHANGED,
        pins_unchanged=True,force_calibration_unchanged=True,app_version='0.22',sram_written=False,flash_written=False),indent=2))
    print('Frozen A6C4 complete product:',len(frozen),'files; no programmer',flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--build',action='store_true');args=a.parse_args();freeze()
    if args.build:
        with(B/'build.log').open('w',encoding='utf8')as log:
            r=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(B/'build.tcl')],cwd=B,stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0,'Inspect harmonica build.log';print('Gowin completed',flush=True)
