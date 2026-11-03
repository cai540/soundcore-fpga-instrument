"""Verify 0.9 software, source clocks, regressions and upload simulation. No hardware access."""
from pathlib import Path
import os,csv,json,subprocess,hashlib,difflib,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_final_phrases_20261029';OLD=R/'build/vocal_phrase_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
JDK=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
def read(p):return [tuple(int(n[k]) for k in ['start_ms','duration_ms','midi']) for n in csv.DictReader(p.open(encoding='utf8'))]
def union(ns):
 out=[]
 for s,d,m in ns:
  assert d>=20 and 0<=m<=127 and s>=0
  if out and out[-1][1]==s:out[-1][1]=s+d
  else:
   assert not out or out[-1][1]<s
   out.append([s,s+d])
 return out
def label(ns):
 out={}
 for s,d,m in ns:
  for t in range(s,s+d,10):out[t]=m
 return out
assert 'BUILD SUCCESSFUL' in (B/'gradle.log').read_text(encoding='utf8')
tests=[]
for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 t=ET.parse(p).getroot();assert int(t.get('failures'))==int(t.get('errors'))==0
 tests.append({'suite':t.get('name'),'count':int(t.get('tests'))})
count=sum(t['count'] for t in tests);assert count>=200,count
lint=ET.parse(R/'app/android/app/build/reports/lint-results-debug.xml').getroot()
assert not any(t.get('severity') in ['Error','Fatal'] for t in lint.findall('issue'))
for p,h in json.loads((B/'audio_class_sha256.json').read_text()).items():assert sha(R/p)==h,p
manifest=json.loads((B/'baseline_sha256.json').read_text());changed=[];diff=[]
for name,h in manifest.items():
 assert sha(B/'baseline'/name)==h
 if sha(R/name)!=h:
  changed.append(name);diff+=list(difflib.unified_diff((B/'baseline'/name).read_text(encoding='utf8').splitlines(True),(R/name).read_text(encoding='utf8').splitlines(True),fromfile='0.8/'+name,tofile='0.9/'+name))
assert set(changed)=={'app/android/app/build.gradle.kts','app/android/app/src/main/java/cn/soundcore/instrument/MelodyRecognition.kt'},changed
for name in ['app/android/app/src/main/java/cn/soundcore/instrument/VocalContourProjection.kt','app/android/app/src/test/java/cn/soundcore/instrument/VocalContourProjectionTest.kt']:
 diff+=list(difflib.unified_diff([], (R/name).read_text(encoding='utf8').splitlines(True),fromfile='/dev/null',tofile='0.9/'+name))
(B/'changes.diff').write_text(''.join(diff),encoding='utf8')
source=(R/'app/android/app/src/main/java/cn/soundcore/instrument/VocalContourProjection.kt').read_text(encoding='utf8')
assert not any(t in source for t in ['兰亭序','牵丝戏','敕勒歌','祖国','wodezuguo','File(','readText','getResource','SourceLocation','lyrics'])
items=json.loads((B/'audio_results.json').read_text(encoding='utf8'));assert len(items)==34,len(items)
regressions=[];allchanges=[]
for it in items:
 if it['status']!='ok':continue
 d=Path(it['new']);old=OLD/'audio'/it['name']/it['window'];before=read(d/'stage_before_contour.csv');after=read(d/'notes.csv')
 assert after==read(d/'stage_final.csv') and union(before)==union(after)
 if (old/'notes.csv').exists():assert before==read(old/'notes.csv'),('upstream regression',d)
 assert (d/'original_pitch.s16').stat().st_size==(d/'analysis.f32').stat().st_size//2
 changes=list(csv.DictReader((d/'contour_changes.csv').open()))
 for c in changes:allchanges.append({'name':it['name'],'window':it['window'],'source_ms':round(it['offset_seconds']*1000)+int(c['start_ms']),**c})
 if it['name']=='zuguo':
  offset=round(it['offset_seconds']*1000);a=label(before);z=label(after)
  changed_times=[t+offset for t in a if a[t]!=z[t]]
  assert all(78700<=t<=79320 or 83500<=t<=86110 for t in changed_times),('accepted other region changed',d,changed_times)
 elif it['window'] in ['first40','nursery'] or it['name']=='chilege':
  assert before==after,('accepted audio changed',d,changes)
 regressions.append({'name':it['name'],'window':it['window'],'old_notes':len(before),'new_notes':len(after),'changes':changes,'sounding_union_preserved':True})
(B/'regression_checks.json').write_text(json.dumps(regressions,ensure_ascii=False,indent=2),encoding='utf8')
(B/'all_contour_changes.json').write_text(json.dumps(allchanges,ensure_ascii=False,indent=2),encoding='utf8')
cp=lambda c:os.pathsep.join(map(str,[c,stdlib,B]))
subprocess.run([str(JDK/'javac.exe'),'-cp',cp(B/'frozen_classes'),'-d',str(B),str(R/'scripts/support/CheckInstrumentIsolation.java')],check=True)
isolations={}
for key,c in [('old',OLD/'frozen_classes'),('new',B/'frozen_classes')]:
 run=subprocess.run([str(JDK/'java.exe'),'-cp',cp(c),'CheckInstrumentIsolation'],capture_output=True,text=True,encoding='utf8');assert run.returncode==0,run.stderr
 isolations[key]=run.stdout
assert isolations['old']==isolations['new']
(B/'instrument_isolation.json').write_text(json.dumps(isolations,indent=2),encoding='utf8')
os.environ.update(TEMP=str(R/'tmp'),TMP=str(R/'tmp'));tool=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');endpoints=[]
for it in items:
 if not it.get('wire_fixture'):continue
 d=Path(it['new']);prefix=d.relative_to(R).as_posix()
 test=(R/'tb/tb_melody_upload_endpoint.v').read_text().replace('build/mono_recognition_20261028/fixtures',prefix).replace('notes!=12','notes!=`FIXTURE_NOTES')
 (d/'tb_endpoint.v').write_text(test)
 c=subprocess.run([str(tool/'iverilog.exe'),'-g2012','-s','tb_melody_upload_endpoint','-o',str(d/'endpoint.vvp'),str(d/'tb_endpoint.v'),*[str(R/f'rtl/{m}.v') for m in ['uploaded_song_engine','ble_control_endpoint','ble_frame_parser']]],cwd=R,capture_output=True,text=True);assert c.returncode==0,c.stderr
 run=subprocess.run([str(tool/'vvp.exe'),str(d/'endpoint.vvp')],cwd=R,capture_output=True,text=True,timeout=55)
 log=c.stdout+c.stderr+run.stdout+run.stderr;(d/'endpoint.log').write_text(log,encoding='utf8')
 assert run.returncode==0 and 'PASS:' in log and 'FATAL:' not in log,log
 endpoints.append({'name':it['name'],'passed':True,'log':log});print(it['name'],'endpoint pass',flush=True)
assert len(endpoints)==7
hardware=json.loads((R/'build/melody_workbench_20261028/release.json').read_text(encoding='utf8'))
for p,h in hardware['hardware_source_sha256'].items():assert sha(R/p)==h
assert sha(Path(hardware['firmware']))==hardware['firmware_sha256']
old=json.loads((B/'baseline/build/vocal_phrase_20261029/release.json').read_text(encoding='utf8'))
assert sha(Path(old['apk']))==old['apk_sha256']
apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk'
meta=json.loads((apk.parent/'output-metadata.json').read_text())['elements'][0];assert meta['versionCode']==9
run=subprocess.run(['D:/FPGA/_Tools/android/sdk/build-tools/35.0.0/apksigner.bat','verify','--verbose','--print-certs',str(apk)],env={**os.environ,'JAVA_HOME':str(JDK.parent)},capture_output=True,text=True)
assert run.returncode==0 and old['certificate_sha256'] in run.stdout
(B/'apk_certificate.log').write_text(run.stdout+run.stderr,encoding='utf8')
for p in (R/'app/android/app/src/main').rglob('*'):
 if p.is_file():assert p.stat().st_mtime<=apk.stat().st_mtime
report={'version':meta['versionName'],'algorithm_version':7,'apk_source':str(apk),'apk_sha256':sha(apk),'certificate_sha256':old['certificate_sha256'],
 'android_tests':tests,'android_test_count':count,'real_audio_windows':len(items),'whole_source_songs':4,'endpoint_checks':endpoints,
 'instrument_isolation_fixtures':6,'sources_changed':changed,'contour_changes':allchanges,'hardware_unchanged':True,
 'firmware':hardware['firmware'],'firmware_sha256':hardware['firmware_sha256'],'old_apk_preserved':True,
 'physical_phone_verified':False,'physical_ble_verified':False,'physical_board_verified':False,'flash_written':False,'sram_written':False,
 'single_app_clip_limit_seconds':40,'full_song_preview_method':'independent 40s original-PCM chunks stitched on source clock'}
(B/'release.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('PASS',count,'unit tests;',len(items),'real PCM windows;',len(endpoints),'upload RTL fixtures; hardware unchanged.',flush=True)
