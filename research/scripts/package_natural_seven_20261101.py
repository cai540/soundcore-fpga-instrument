"""Package a matched candidate only after software/PNR gates. Never programs hardware."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET,zipfile,os
R=Path(__file__).resolve().parents[1];B=R/'build/natural_seven_20261101';O=R/'output/natural_seven_20261101'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
checks=json.loads((B/'tests/results.json').read_text(encoding='utf8'));assert len(checks)>=21 and all(x['passed']for x in checks)
units=[ET.parse(p).getroot()for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
test_counts={key:sum(int(t.get(key,'0'))for t in units)for key in ['tests','failures','errors','skipped']}
assert test_counts['tests']>=257 and test_counts['failures']==test_counts['errors']==0,test_counts
assert 'BUILD SUCCESSFUL' in (B/'android_checks.log').read_text(encoding='utf8')
lint=ET.parse(R/'app/android/app/build/reports/lint-results-debug.xml').getroot()
lint_counts={k:sum(n.get('severity')==k for n in lint.findall('issue'))for k in ['Error','Fatal','Warning']}
assert lint_counts['Error']==lint_counts['Fatal']==0
assert 'fail 0' in (B/'web_tests.log').read_text(encoding='utf8')
assert not (B/'web_typecheck.log').read_text(encoding='utf8').strip()
assert '0 errors' in (B/'web_lint.log').read_text(encoding='utf8')
src=B/'src';frozen=json.loads((B/'frozen_inputs.json').read_text(encoding='utf8'))
assert all(sha(src/name)==digest for name,digest in frozen.items()),'Frozen inputs changed during build'
meta=json.loads((B/'build_metadata.json').read_text(encoding='utf8'))
assert all(sha(Path(rec['origin']))==rec['sha256']for rec in meta['source_records']),'Working RTL no longer matches candidate'
old_steps=[int(v)for v in re.findall(r'phase_step = 32.d(\d+)',(R/'rtl/note_step_table35.v').read_text(encoding='utf8'))if int(v)>0]
new_steps=[int(v)for v in re.findall(r'phase_step=32.d(\d+)',(R/'rtl/note_step_table72.v').read_text(encoding='utf8'))]
assert old_steps==new_steps[24:59],'Existing DDS pitches changed'
for name in ['expression_raw.mem','expression_normalized.mem']:
    old=(R/'build/timbre_pressure_repair_20261101/before/rtl'/name).read_text(encoding='utf8').split()
    new=(R/'rtl'/name).read_text(encoding='utf8').split();assert len(new)==1296
    for timbre in range(2):assert old[timbre*315:(timbre+1)*315]==new[timbre*648+216:timbre*648+531]
fs=B/'impl/pnr/soundcore_speaker_omr_60k.fs'
assert fs.stat().st_mtime>=(B/'frozen_inputs.json').stat().st_mtime,'Final bitstream is stale'
log=(B/'build.log').read_text(encoding='utf8',errors='replace')
assert 'Placement and routing completed'in log and 'ERROR ('not in log
report=(B/'impl/pnr/soundcore_speaker_omr_60k.rpt.txt').read_text(encoding='utf8')
resources={name:re.search(r'^  '+name+r'\s+\|\s*([^|\n]+)',report,re.M)[1].strip()for name in ['Logic','BSRAM','DSP']}
timing=(B/'impl/pnr/soundcore_speaker_omr_60k_tr_content.html').read_text(encoding='utf8')
frequency=re.search(r'<td>12\.288\(MHz\)</td>\s*<td>([\d.]+)\(MHz\)</td>',timing)
assert frequency and float(frequency[1])>=12.288
baseline=R/'build/k5_lamp_follow_20261101/baseline/board/soundcore_speaker_omr_60k.cst'
assert sha(src/'board/soundcore_speaker_omr_60k.cst')==sha(baseline)
user_code=re.search(r'UserCode:\s*(0x[\da-fA-F]+)',fs.read_text(encoding='ascii'))[1]
sdk=Path('D:/FPGA/_Tools/android/sdk/build-tools/35.0.0');os.environ['JAVA_HOME']='D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1'
apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk'
def cert(path):
    p=subprocess.run([str(sdk/'apksigner.bat'),'verify','--print-certs',str(path)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    return re.search(r'certificate SHA-256 digest: (\w+)',p.stdout)[1]
cert_hash=cert(apk)
assert cert_hash==cert(R/'output/builtin_recognition_20261101/声芯乐动_0.15_双识别内置离线版.apk')
badging=subprocess.run([str(sdk/'aapt2.exe'),'dump','badging',str(apk)],capture_output=True,text=True,encoding='utf8').stdout
assert "versionCode='16'"in badging and 'android.permission.INTERNET'not in badging
O.mkdir(parents=True,exist_ok=True)
firmware=O/'声芯乐动_七自然音_完整版_20261101.fs';app=O/'声芯乐动_0.16_七自然音_双识别离线版.apk'
copy(fs,firmware);copy(apk,app)
for name in ['tests/results.json','android_checks.log','android_snapshots.log','web_tests.log','web_typecheck.log','web_lint.log','build_metadata.json','frozen_inputs.json']:
    copy(B/name,O/'验收证据'/Path(name).name)
for name in ['soundcore_speaker_omr_60k.rpt.txt','soundcore_speaker_omr_60k_tr_content.html','soundcore_speaker_omr_60k.pin.html']:
    copy(B/'impl/pnr'/name,O/'验收证据'/name)
for p in (R/'app/android/app/src/test/snapshots/images').glob('*NaturalPitch*png'):copy(p,O/'界面预览'/p.name)
copy(R/'config/pitch_layout_v2.json',O/'pitch_layout_v2.json')
# Relocatable FPGA sources. Runtime include/ROM paths are relative to build.tcl.
project=ET.parse(B/'soundcore_speaker_omr_60k.gprj')
for n in project.findall('./FileList/File'):n.set('path',Path(n.get('path')).relative_to(B).as_posix())
archive=O/'七自然音_完整FPGA工程.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
    for p in src.rglob('*'):
        if not p.is_file():continue
        data=p.read_bytes()
        if p.suffix in ['.v','.vh']:
            data=data.decode('utf8').replace(src.as_posix(),'src').encode('utf8')
        z.writestr(p.relative_to(B).as_posix(),data)
    z.writestr('soundcore_speaker_omr_60k.gprj',ET.tostring(project.getroot(),encoding='utf8',xml_declaration=True))
    z.writestr('build.tcl','set task_project_root [file dirname [file normalize [info script]]]\ncd $task_project_root\nopen_project [file join $task_project_root soundcore_speaker_omr_60k.gprj]\nset_option -top_module soundcore_speaker_omr_top\nrun all\n')
    z.write(R/'config/pitch_layout_v2.json','pitch_layout_v2.json')
release={'baseline':'EAE0','user_code':user_code,'pitch_layout':2,'voices':32,'manual_notes_per_key':35,'natural_octaves':5,
    'exact_midi_range':[36,107],'rtl_checks':len(checks),'android':test_counts,'android_lint':lint_counts,
    'resources':resources,'target_audio_mhz':12.288,'actual_fmax_mhz':float(frequency[1]),'io_constraints_sha256':sha(baseline),
    'apk_certificate_sha256':cert_hash,'apk_no_internet_permission':True,'web_source_updated':True,'web_published':False,
    'sram_written':False,'flash_written':False,'hardware_acceptance':'pending',
    'assets':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)}for p in [firmware,app,archive]}}
(O/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(release,ensure_ascii=False,indent=2))
