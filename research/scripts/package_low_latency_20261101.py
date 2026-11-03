"""Package only checked low-latency artifacts. Never writes a connected device."""
from pathlib import Path
import os,json,re,hashlib,shutil,subprocess,zipfile,xml.etree.ElementTree as ET,csv
R=Path(__file__).resolve().parents[1];B=R/'build/low_latency_20261101';O=R/'output/low_latency_20261101'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,q):
    q.parent.mkdir(parents=True,exist_ok=True)
    # Gowin marks the generated FS read-only. Repeated packaging of identical
    # artifacts should not try to truncate that protected copy.
    if q.exists() and sha(p)==sha(q):return
    if q.exists():q.chmod(q.stat().st_mode | 0o200)
    shutil.copy2(p,q)
checks=json.loads((B/'tests/results.json').read_text(encoding='utf8'))
assert len(checks)==23 and all(x['passed'] for x in checks)
pcm=json.loads((B/'pcm/summary.json').read_text(encoding='utf8'));assert pcm['passed']
latency=json.loads((B/'latency/summary.json').read_text(encoding='utf8'))
fallback=json.loads((B/'latency_fallback/summary.json').read_text(encoding='utf8'))
fallback_all=json.loads((B/'latency_fallback_all/summary.json').read_text(encoding='utf8'))
assert latency['cases']==70 and latency['max_step_to_abs64_i2s_ms']<5
assert fallback['cases']==2 and fallback['max_step_to_abs64_i2s_ms']<5
assert fallback_all['cases']==70 and fallback_all['max_step_to_abs64_i2s_ms']<5
units=[ET.parse(p).getroot()for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
counts={k:sum(int(t.get(k,'0'))for t in units)for k in ['tests','failures','errors','skipped']}
assert counts['tests']>=269 and counts['failures']==counts['errors']==0
assert 'BUILD SUCCESSFUL'in (B/'android_checks.log').read_text(encoding='utf8')
lint=ET.parse(R/'app/android/app/build/reports/lint-results-debug.xml').getroot()
lint_counts={k:sum(n.get('severity')==k for n in lint.findall('issue'))for k in ['Error','Fatal','Warning']}
assert lint_counts['Error']==lint_counts['Fatal']==0
src=B/'src';frozen=json.loads((B/'frozen_inputs.json').read_text(encoding='utf8'))
assert all(sha(src/n)==h for n,h in frozen.items())
meta=json.loads((B/'build_metadata.json').read_text(encoding='utf8'))
assert all(sha(Path(x['origin']))==x['sha256']for x in meta['source_records'])
old_src=R/'build/natural_seven_20261101/src'
old_meta=json.loads((R/'build/natural_seven_20261101/build_metadata.json').read_text(encoding='utf8'))
for name in ['expression_raw.mem','expression_normalized.mem']:
    key=(R/'rtl'/name).as_posix()
    assert meta['assets'][key]['sha256']==old_meta['assets'][key]['sha256']
for name in ['pitch_layout.v','note_step_table72.v',
    'expressive_texture.v','audio_effects_product.v','fsr_strike_detector.v','mcp3208_scan.v']:
    assert (src/'rtl'/name).read_text(encoding='utf8').replace(src.as_posix(),'SRC')==\
        (old_src/'rtl'/name).read_text(encoding='utf8').replace(old_src.as_posix(),'SRC'),name
cst=src/'board/soundcore_speaker_omr_60k.cst'
assert sha(cst)==sha(R/'build/natural_seven_20261101/src/board/soundcore_speaker_omr_60k.cst')
fs=B/'impl/pnr/soundcore_speaker_omr_60k.fs'
assert fs.stat().st_mtime>=(B/'frozen_inputs.json').stat().st_mtime
log=(B/'build.log').read_text(encoding='utf8',errors='replace')
assert 'Placement and routing completed'in log and 'ERROR ('not in log
report=(B/'impl/pnr/soundcore_speaker_omr_60k.rpt.txt').read_text(encoding='utf8')
resources={n:re.search(r'^  '+n+r'\s+\|\s*([^|\n]+)',report,re.M)[1].strip()for n in ['Logic','BSRAM','DSP']}
timing=(B/'impl/pnr/soundcore_speaker_omr_60k_tr_content.html').read_text(encoding='utf8')
fmax=float(re.search(r'<td>12\.288\(MHz\)</td>\s*<td>([\d.]+)\(MHz\)</td>',timing)[1]);assert fmax>=12.288
code=re.search(r'UserCode:\s*(0x[\da-fA-F]+)',fs.read_text(encoding='ascii'))[1]
sdk=Path('D:/FPGA/_Tools/android/sdk/build-tools/35.0.0');os.environ['JAVA_HOME']='D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1'
apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk'
signed=subprocess.run([str(sdk/'apksigner.bat'),'verify','--print-certs',str(apk)],capture_output=True,text=True)
assert signed.returncode==0
cert=re.search(r'certificate SHA-256 digest: (\w+)',signed.stdout)[1]
old=json.loads((R/'output/natural_seven_20261101/release.json').read_text(encoding='utf8'))
assert cert==old['apk_certificate_sha256']
manifest=subprocess.run([str(sdk/'aapt2.exe'),'dump','badging',str(apk)],capture_output=True,text=True,encoding='utf8').stdout
assert "versionCode='17'"in manifest and 'android.permission.INTERNET'not in manifest
O.mkdir(parents=True,exist_ok=True)
firmware=O/'声芯乐动_低延迟_完整音响版_20261101.fs';app=O/'声芯乐动_0.17_低延迟_双识别离线版.apk'
copy(fs,firmware);copy(apk,app)
for name in ['tests/results.json','pcm/summary.json','pcm/comparison.log','latency/summary.json',
    'latency/physical_latency.csv','latency/simulation.log','latency_fallback/summary.json',
    'latency_fallback/physical_latency.csv','latency_fallback/simulation.log',
    'latency_fallback_all/summary.json','latency_fallback_all/physical_latency.csv','latency_fallback_all/simulation.log','build.log',
    'android_checks.log','build_metadata.json','frozen_inputs.json','baseline.json','unchanged_product_check.json']:
    copy(B/name,O/'evidence'/name)
for p in (B/'diffs').glob('*.diff'):copy(p,O/'evidence/diffs'/p.name)
for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    copy(p,O/'evidence/android'/p.name)
for name in ['soundcore_speaker_omr_60k.rpt.txt','soundcore_speaker_omr_60k_tr_content.html','soundcore_speaker_omr_60k.pin.html']:
    copy(B/'impl/pnr'/name,O/'evidence'/name)
project=ET.parse(B/'soundcore_speaker_omr_60k.gprj')
for n in project.findall('./FileList/File'):n.set('path',Path(n.get('path')).relative_to(B).as_posix())
archive=O/'低延迟_完整FPGA工程.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
    for p in src.rglob('*'):
        if not p.is_file():continue
        data=p.read_bytes()
        if p.suffix in ['.v','.vh']:data=data.decode('utf8').replace(src.as_posix(),'src').encode('utf8')
        z.writestr(p.relative_to(B).as_posix(),data)
    z.writestr('soundcore_speaker_omr_60k.gprj',ET.tostring(project.getroot(),encoding='utf8',xml_declaration=True))
    z.writestr('build.tcl','set task_project_root [file dirname [file normalize [info script]]]\ncd $task_project_root\nopen_project [file join $task_project_root soundcore_speaker_omr_60k.gprj]\nset_option -top_module soundcore_speaker_omr_top\nrun all\n')
    z.write(R/'config/pitch_layout_v2.json','pitch_layout_v2.json')
# Compare identical test cases and thresholds, rather than comparing unrelated maxima.
old_rows=list(csv.DictReader((R/'build/latency_preflight_20261101/physical_latency.csv').open()))
new_rows=list(csv.DictReader((B/'latency/physical_latency.csv').open()))
lookup={(x['timbre'],x['bank'],x['pad']):x for x in new_rows}
matched=[lookup[(x['timbre'],x['bank'],x['pad'])]for x in old_rows]
comparison={'matched_cases':len(matched),'old_max_abs64_ms':max(float(x['step_to_abs64_i2s_ns']) for x in old_rows)/1e6,
    'new_max_abs64_ms':max(float(x['step_to_abs64_i2s_ns'])for x in matched)/1e6,
    'old_forced_fallback_max_abs64_ms':4.30658891,'new_forced_fallback_max_abs64_ms':fallback['max_step_to_abs64_i2s_ms']}
for x in old_rows:
    y=lookup[(x['timbre'],x['bank'],x['pad'])]
    assert float(y['step_to_abs64_i2s_ns'])<=float(x['step_to_abs64_i2s_ns'])
(O/'evidence/latency_comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf8')
changed=['rtl/poly_synth32_tm.v','rtl/synth_voice.v','rtl/instrument_attack.vh',
    'app/android/app/build.gradle.kts',
    'app/android/app/src/main/java/cn/soundcore/instrument/BleController.kt',
    'app/android/app/src/main/java/cn/soundcore/instrument/BleWritePacer.kt',
    'app/android/app/src/main/java/cn/soundcore/instrument/RealtimeNotes.kt',
    'app/android/app/src/main/java/cn/soundcore/instrument/CommandQueue.kt',
    'app/android/app/src/test/java/cn/soundcore/instrument/BleWritePacerTest.kt',
    'tb/tb_low_latency_attack.v','tb/tb_low_latency_pcm.v','tb/tb_compact_remote_release.v',
    'scripts/prepare_low_latency_20261101.py','scripts/check_low_latency_20261101.py',
    'scripts/check_low_latency_pcm.py','scripts/preflight_latency_20261101.py',
    'scripts/package_low_latency_20261101.py','scripts/finalize_low_latency_20261101.py',
    'docs/plans/2026-11-01-low-latency.md']
for name in changed:copy(R/name,O/'source'/name)
assert apk.stat().st_mtime>=max((R/n).stat().st_mtime for n in changed if n.startswith('app/') and '/src/main/'in n),'APK is older than changed production sources'
release={'parent_candidate':'7B69','installed_flash_last_confirmed':'EAE0','user_code':code,'apk_version':17,
    'rtl_checks':len(checks),'android':counts,'android_lint':lint_counts,'resources':resources,'fmax_mhz':fmax,
    'audio_clock_mhz':12.288,'pins_unchanged':True,'io_constraints_sha256':sha(cst),'midi_range':[36,107],
    'natural_octaves':5,'voices':32,'apk_certificate_sha256':cert,'apk_no_internet_permission':True,
    'attack_samples':{'harmonica':128,'erhu':256},'uart_baud_unchanged':9600,
    'latency':{k:v for k,v in latency.items()if k!='source_hashes'},'comparison':comparison,
    'fallback_all_octaves':{k:v for k,v in fallback_all.items()if k!='source_hashes'},
    'sram_written':False,'flash_written':False,'physical_latency_measured':False,'phone_bluetooth_measured':False,
    'assets':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size}for p in [firmware,app,archive]},
    'android_changed_source_hashes':{name:sha(R/name)for name in changed if name.startswith('app/')}}
(O/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in release.items()if k not in ['assets','latency','android_changed_source_hashes']},ensure_ascii=False,indent=2))
