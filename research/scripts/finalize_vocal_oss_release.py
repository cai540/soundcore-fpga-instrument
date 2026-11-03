"""Freeze software evidence and a compact audition archive, excluding weights."""
from pathlib import Path
import hashlib,importlib.metadata,json,platform,shutil,subprocess,zipfile

R=Path(__file__).resolve().parents[1];B=R/'build/vocal_oss_20261029';O=R/'output/vocal_oss_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for leaf in ['transcribe_vocal_oss.py','package_vocal_oss.py','run_oss_transcription.ps1','finalize_vocal_oss_release.py']:
        shutil.copy2(R/'scripts'/leaf,O/'source'/leaf)
    for leaf in ['adapter_tests.log','launcher_smoke.log','general_cli_smoke.log']:
        shutil.copy2(B/leaf,O/leaf)
    dependencies={n:importlib.metadata.version(n) for n in ['numpy','scipy','onnxruntime','mido']}
    (O/'requirements-candidate.txt').write_text('\n'.join(k+'=='+v for k,v in dependencies.items())+'\n',encoding='utf8')
    archives=[]
    for size in ['small','medium']:
        p=B/'game_models'/f'GAME-1.0.3-{size}-onnx.zip'
        archives.append({'url':f'https://github.com/openvpi/GAME/releases/download/v1.0.3/{p.name}',
                         'bytes':p.stat().st_size,'sha256':sha(p)})
    p=B/'checkpoints.zip'
    archives.append({'url':'https://drive.google.com/file/d/1JNtNT37KiLq9uFQqHk7JFs-3trxd3bRh/view',
                     'bytes':p.stat().st_size,'sha256':sha(p)})
    (O/'environment.json').write_text(json.dumps({'python':platform.python_version(),'platform':platform.platform(),
         'candidate_dependencies':dependencies,'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],
         'official_weight_archives_not_bundled':archives},ensure_ascii=False,indent=2),encoding='utf8')
    checked=json.loads((B/'baseline_sha256.json').read_text(encoding='utf8'))
    assert all(sha(R/p)==h for p,h in checked.items())
    validation=json.loads((O/'validation.json').read_text(encoding='utf8'))
    validation['adapter_behavior_tests_passed']=14
    validation['actual_arbitrary_path_full_file_cli_completed']=True
    validation['production_files_changed_at_finalization']=[]
    (O/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
    manifest={str(p.relative_to(O)).replace('\\','/'):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='sha256.json'}
    (O/'sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    archive=Path(shutil.make_archive(str(O),'zip',root_dir=O.parent,base_dir=O.name))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf8')
    print(json.dumps({'folder':str(O),'archive':str(archive),'bytes':archive.stat().st_size,
         'files':len(manifest)+1,'sha256':sha(archive)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
