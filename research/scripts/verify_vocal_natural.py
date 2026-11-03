"""Read-only software/RTL checks for the 0.7 recording recognition release.
This script never opens a programmer or scans a physical device.
"""
from pathlib import Path
import os,json,subprocess,hashlib,xml.etree.ElementTree as ET,difflib,csv
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_natural_20261029'
JDK=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=lambda c:os.pathsep.join(map(str,[c,stdlib,B]))
assert 'BUILD SUCCESSFUL' in (B/'android_verified.log').read_text(encoding='utf-8-sig')
tests=[]
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 t=ET.parse(p).getroot();assert int(t.get('failures'))==int(t.get('errors'))==0
 tests.append({'suite':t.get('name'),'tests':int(t.get('tests'))})
test_count=sum(x['tests'] for x in tests);assert test_count==143,test_count
lint=ET.parse(ROOT/'app/android/app/build/reports/lint-results-debug.xml').getroot()
assert not any(x.get('severity') in ['Error','Fatal'] for x in lint.findall('issue'))
for p,h in json.loads((B/'audio_class_sha256.json').read_text(encoding='utf8')).items():assert sha(ROOT/p)==h,p

subprocess.run([str(JDK/'javac.exe'),'-cp',cp(B/'frozen_classes'),'-d',str(B),str(ROOT/'scripts/support/CheckInstrumentIsolation.java')],check=True)
isolation={}
for key,classes in [('old',ROOT/'build/vocal_refine_20261029/frozen_classes'),('new',B/'frozen_classes')]:
 r=subprocess.run([str(JDK/'java.exe'),'-Dfile.encoding=UTF-8','-cp',cp(classes),'CheckInstrumentIsolation'],capture_output=True,text=True,encoding='utf8')
 assert r.returncode==0,r.stderr;isolation[key]=r.stdout;(B/f'instrument_{key}.log').write_text(r.stdout,encoding='utf8')
assert isolation['old']==isolation['new']
(B/'instrument_isolation.json').write_text(json.dumps({'fixtures':6,'identical':True,'results':isolation},indent=2),encoding='utf8')

results=json.loads((B/'audio_results.json').read_text(encoding='utf8'));assert len(results)==21
def read(path):
 return [tuple(int(r[k]) for k in ['start_ms','duration_ms','midi']) for r in csv.DictReader(path.open(encoding='utf8'))]
def union(notes):
 out=[]
 for s,d,m in notes:
  assert d>0
  if out and out[-1][1]==s:out[-1][1]=s+d
  else:
   assert not out or out[-1][1]<s
   out.append([s,s+d])
 return out
stage_checks=[]
for item in results:
 if item['status']!='ok' or item['name'] not in ['zuguo','chilege']:continue
 d=Path(item['new']);old=Path(item['old'])
 stages={n:read(d/f'stage_{n}.csv') for n in ['seed','restored','quantized','final']}
 assert stages['seed']==read(old/'notes.csv'),'0.6 seed changed: '+str(d)
 assert stages['final']==read(d/'notes.csv')
 assert all(union(x)==union(stages['seed']) for x in stages.values()),str(d)
 original_starts={x[0] for x in stages['seed']};restored_starts={x[0] for x in stages['restored']}
 assert original_starts<=restored_starts
 assert len(stages['restored'])==len(stages['quantized'])
 for a,b in zip(stages['restored'],stages['quantized']):assert a[:2]==b[:2]
 final_starts={x[0] for x in stages['final']}
 assert (restored_starts-original_starts)<=final_starts,'Recovered boundary removed'
 stage_checks.append({'name':item['name'],'window':item['window'],'notes':{k:len(v) for k,v in stages.items()},'sounding_union_unchanged':True})
(B/'stage_invariants.json').write_text(json.dumps(stage_checks,indent=2),encoding='utf8')

os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
tool=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');endpoints=[]
for item in results:
 if not item.get('wire_fixture'):continue
 d=Path(item['new']);prefix=d.relative_to(ROOT).as_posix()
 source=(ROOT/'tb/tb_melody_upload_endpoint.v').read_text().replace('build/mono_recognition_20261028/fixtures',prefix).replace('notes!=12','notes!=`FIXTURE_NOTES')
 (d/'tb_endpoint.v').write_text(source)
 c=subprocess.run([str(tool/'iverilog.exe'),'-g2012','-s','tb_melody_upload_endpoint','-o',str(d/'endpoint.vvp'),str(d/'tb_endpoint.v'),
  *[str(ROOT/f'rtl/{m}.v') for m in ['uploaded_song_engine','ble_control_endpoint','ble_frame_parser']]],cwd=ROOT,capture_output=True,text=True)
 assert c.returncode==0,c.stderr
 r=subprocess.run([str(tool/'vvp.exe'),str(d/'endpoint.vvp')],cwd=ROOT,capture_output=True,text=True,timeout=55)
 log=c.stdout+c.stderr+r.stdout+r.stderr;(d/'endpoint.log').write_text(log,encoding='utf8')
 assert r.returncode==0 and 'PASS:' in log and 'FATAL:' not in log,log
 endpoints.append({'name':item['name'],'passed':True,'output':log.strip()});print(item['name'],log.strip(),flush=True)
assert len(endpoints)==7
(B/'endpoint_checks.json').write_text(json.dumps(endpoints,indent=2),encoding='utf8')

baseline=json.loads((B/'baseline_sha256.json').read_text(encoding='utf8'));changes=[];diff=[]
for name,h in baseline.items():
 original=B/'baseline'/name;assert sha(original)==h,'Frozen original changed: '+name
 assert (ROOT/name).exists(),name
 if sha(ROOT/name)!=h:
  changes.append(name)
  diff+=list(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True),(ROOT/name).read_text(encoding='utf8').splitlines(True),fromfile='0.6/'+name,tofile='0.7/'+name))
expected={'app/android/app/build.gradle.kts','app/android/app/src/main/java/cn/soundcore/instrument/MelodyRecognition.kt'}
assert set(changes)==expected,changes
helpers=['VocalBoundaryEvidence','VocalEventRestoration','TonalPitchRefinement','TonalBoundaryCoalescing','VocalNaturalRefinement']
for name in [*['app/android/app/src/main/java/cn/soundcore/instrument/'+n+'.kt' for n in helpers],
 *['app/android/app/src/test/java/cn/soundcore/instrument/'+n+'Test.kt' for n in helpers]]:
 diff+=list(difflib.unified_diff([], (ROOT/name).read_text(encoding='utf8').splitlines(True),fromfile='/dev/null',tofile='0.7/'+name))
(B/'changes.diff').write_text(''.join(diff),encoding='utf8')
previous=json.loads((ROOT/'build/melody_workbench_20261028/release.json').read_text(encoding='utf8'))
for name,h in previous['hardware_source_sha256'].items():assert sha(ROOT/name)==h,'Hardware changed: '+name
assert sha(Path(previous['firmware']))==previous['firmware_sha256']
old=json.loads((B/'baseline/build/vocal_refine_20261029/release.json').read_text(encoding='utf8'))
assert sha(Path(old['apk']))==old['apk_sha256'],'Published 0.6 APK changed'
apk=ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk'
metadata=json.loads((apk.parent/'output-metadata.json').read_text())['elements'][0]
assert metadata['versionCode']==7 and metadata['versionName']=='0.7-natural-melody'
env={**os.environ,'JAVA_HOME':str(JDK.parent)}
r=subprocess.run(['D:/FPGA/_Tools/android/sdk/build-tools/35.0.0/apksigner.bat','verify','--verbose','--print-certs',str(apk)],env=env,capture_output=True,text=True)
assert r.returncode==0 and previous['certificate_sha256'] in r.stdout,r.stdout+r.stderr
(B/'apk_certificate.log').write_text(r.stdout+r.stderr,encoding='utf8')
for p in (ROOT/'app/android/app/src/main').rglob('*'):
 if p.is_file():assert p.stat().st_mtime<=apk.stat().st_mtime,'APK older than source: '+str(p)
report={'version':metadata['versionName'],'apk_source':str(apk),'apk_sha256':sha(apk),
 'certificate_sha256':previous['certificate_sha256'],'android_tests':tests,'android_test_count':test_count,
 'real_audio_windows':len(results),'endpoint_checks':endpoints,'instrument_isolation_fixtures':6,
 'existing_firmware_compatible':previous['firmware'],'existing_firmware_sha256':previous['firmware_sha256'],
 'hardware_unchanged':True,'old_artifacts_preserved':True,'previous_06_apk':old['apk'],'sources_changed':changes,
 'algorithm_version':5,'song_templates_in_recognizer':False,'source_clock_preserved':True,
 'physical_phone_verified':False,'physical_ble_verified':False,'physical_board_verified':False,
 'flash_written':False,'sram_written':False,'hardware_scanned':False,
 'quality_claim':'distance to curated reference plus measured-change preservation, not independent ground truth or word alignment'}
(B/'release.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(f'Verified {test_count} JUnit, {len(results)} PCM windows, {len(endpoints)} RTL playbacks, 6 unchanged instrument fixtures.')
