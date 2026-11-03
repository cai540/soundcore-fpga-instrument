"""Verify evidence and publish App 0.3 without touching board firmware."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile,datetime,difflib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/vocal_app_20261028';OUT=ROOT/'output/vocal_app_20261028'
OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((BUILD/'baseline_sha256.json').read_text())
for name,digest in baseline.items():assert sha(BUILD/'baseline'/name)==digest,'Baseline changed: '+name
old=json.loads((BUILD/'baseline/build/mono_recognition_20261028/release.json').read_text(encoding='utf-8'))
assert sha(Path(old['firmware']))==old['sha256']
for name,digest in old['hardware_source_sha256'].items():assert sha(ROOT/name)==digest,'Hardware changed: '+name
expression=json.loads((ROOT/'build/expression_20261028/release.json').read_text(encoding='utf-8'))
assert sha(Path(expression['firmware']))==expression['sha256']
assert sha(Path(old['apk']))==old['apk_sha256'],'Published 0.2 APK changed'
allowed={'app/android/app/build.gradle.kts',*['app/android/app/src/main/java/cn/soundcore/instrument/'+n+'.kt'
 for n in ['MainActivity','MelodyAudio','MelodyPanel','MelodyRecognition','StudioScreen']],
 'app/android/app/src/test/java/cn/soundcore/instrument/MelodyFixtureTest.kt'}
changed=[n for n,h in baseline.items() if n.endswith(('.kt','.kts','.xml')) and sha(ROOT/n)!=h]
assert set(changed)==allowed,changed
diff=[]
for n in changed:diff.extend(difflib.unified_diff((BUILD/'baseline'/n).read_text(encoding='utf-8').splitlines(True),
 (ROOT/n).read_text(encoding='utf-8').splitlines(True),fromfile='baseline/'+n,tofile=n))
(BUILD/'changes.diff').write_text(''.join(diff),encoding='utf-8')
assert 'BUILD SUCCESSFUL' in (BUILD/'android_final_build.log').read_text(encoding='utf-8-sig')
tests=[]
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 t=ET.parse(p).getroot();assert int(t.attrib['failures'])==0 and int(t.attrib['errors'])==0,p
 tests.append({'suite':t.attrib['name'],'tests':int(t.attrib['tests'])})
assert sum(t['tests'] for t in tests)==42
lint=ET.parse(ROOT/'app/android/app/build/reports/lint-results-debug.xml').getroot()
issues=[{'id':i.attrib['id'],'severity':i.attrib['severity']} for i in lint.findall('issue')]
assert all(i['severity'] not in ['Error','Fatal'] for i in issues)
audio=json.loads((BUILD/'real_audio_validation.json').read_text(encoding='utf-8'))
assert len(audio)==2 and all(x['pitch_agreement_with_same_config_python']>.98 and x['voiced_frame_agreement_with_python']>.97 for x in audio)
capture=json.loads((BUILD/'audio_capture_sources.json').read_text())
src=ROOT/'app/android/app/src/main/java/cn/soundcore/instrument'
for n,digest in capture.items():assert sha(src/n)==digest,'Audio capture stale: '+n
endpoints=json.loads((BUILD/'endpoint_validation.json').read_text());assert len(endpoints)==2 and all(e['passed'] for e in endpoints)
apk=ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk'
meta=json.loads((apk.parent/'output-metadata.json').read_text())['elements'][0]
assert meta['versionCode']==3 and meta['versionName']=='0.3-vocal-candidate'
certificate=lambda p:re.search(r'certificate SHA-256 digest:\s*(\S+)',p.read_text(encoding='utf-8-sig'))[1]
assert certificate(BUILD/'apk_certificate.log')==certificate(BUILD/'baseline_certificate.log')
for p in (ROOT/'app/android/app/src/main').rglob('*'):
 if p.is_file():assert p.stat().st_mtime<=apk.stat().st_mtime,'Source newer than APK: '+str(p)
with zipfile.ZipFile(apk) as z:
 license=z.read('assets/open_source_licenses/librosa-ISC.txt').decode()
 assert 'ISC License' in license and 'librosa development team' in license
 assert not any('python' in n.lower() or n.endswith('.mp3') for n in z.namelist()),'Unexpected embedded recognition input/model'
def copy(p,name):
 target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
target=OUT/'声芯_人声识谱_v0.3_候选版.apk';copy(apk,target.name)
for p in (ROOT/'app/android/app/src').rglob('*'):
 if p.is_file():copy(p,Path('source/app/android/app/src')/p.relative_to(ROOT/'app/android/app/src'))
copy(ROOT/'app/android/app/build.gradle.kts','source/app/android/app/build.gradle.kts')
for name in ['vocal_app_2026-10-28.md','vocal_app_review_2026-10-28.md']:
 copy(ROOT/'docs'/name,Path('说明')/name)
for item in audio:
 copy(Path(item['source']),Path('原人声素材')/Path(item['source']).name)
 for n in ['android_score.json','android_notes.csv','android_track.csv','recognized.mid','events.mem','android_upload.hex',
  'android_upload_meta.vh','endpoint.log','tb_vocal_endpoint.v','android_run.log','python_reference_key.json']:
  copy(Path(item['directory'])/n,Path('evidence/real_audio')/item['name']/n)
for p in BUILD.glob('*.log'):copy(p,Path('evidence')/p.name)
for p in BUILD.glob('*.json'):copy(p,Path('evidence')/p.name)
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):copy(p,Path('evidence/unit_tests')/p.name)
copy(ROOT/'app/android/app/build/reports/lint-results-debug.xml','evidence/lint-results-debug.xml')
copy(BUILD/'changes.diff','evidence/changes.diff')
for n in ['check_vocal_app_audio.py','check_vocal_app_endpoint.py','package_vocal_app.py']:
 copy(ROOT/'scripts'/n,Path('source/scripts')/n)
copy(BUILD/'CheckVocalAudio.java','source/CheckVocalAudio.java')
data={'created':datetime.datetime.now().astimezone().isoformat(),'version':meta['versionName'],'version_code':3,
 'status':'software_integrated_pending_physical_phone_and_board_acceptance','apk':str(target),'apk_sha256':sha(apk),
 'certificate_sha256':certificate(BUILD/'apk_certificate.log'),'can_update_existing_apk':True,
 'android_tests':tests,'android_test_count':42,'lint_issues':issues,'real_audio':audio,'endpoint_checks':endpoints,
 'recognition_runs_inside_app':True,'python_or_cloud_required_by_app':False,'audio_file_fingerprint_matching_used':False,
 'hardware_and_protocol_unchanged':True,'compatible_firmware':old['firmware'],'compatible_firmware_sha256':old['sha256'],
 'saved_result_algorithm_version':2,'previous_apk_preserved':True,'source_sha256':capture,
 'sram_written':False,'flash_written':False,'physical_microphone_verified':False,'android_decoder_verified_on_device':False,
 'app_ui_screenshot_verified':False,'physical_ble_verified':False,'physical_listening_verified':False,
 'manual_note_accuracy_measured':False,'measured_phone_processing_ms':None,'measured_end_to_end_latency_ms':None,
 'limits':{'seconds':40,'events':512,'midi':[60,94],'input':'clean monophonic voice or instrument; no mixed accompaniment/chords'},
 'known_limits':['Real microphone, Android decoder, new UI and wireless hardware remain unverified',
  'Reference trajectory agreement is implementation parity, not ground-truth note accuracy',
  'Vocal articulation and onset boundaries can still be imperfect; listen before uploading',
  'Device score is volatile RAM and requires matching FD96 firmware; no programming performed']}
(BUILD/'release.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
copy(BUILD/'release.json','evidence/release.json')
(OUT/'先读我.txt').write_text('''声芯 0.3 人声识谱候选版
安装本目录APK，可覆盖旧版，签名一致。
入口：曲目 → 录一段，接着奏 → 人声 / 哼唱。
录音和选择音频都调用手机本地新算法。两份素材分别为30秒和35.8秒，均小于40秒上限。
原人声素材是输入；根目录“新版App识别试听”是实际新App类生成的参考电子音输出。
先选文件识别并试听，再测试另一设备播放、手机麦克风收音。后者尚未完成实际验收。
传到FPGA需配套FD96识谱固件，本次没有烧录。两只老虎结果适配音域时整体升2个半音，小星星保持原调。
42项单元测试、静态检查、两份真实文件的参考轨迹对照和传谱/自主播放仿真通过。
手机麦克风、实际UI、无线及实板听感仍待验收，不把桌面运算时间当作手机性能。
''',encoding='utf-8-sig')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files}
(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
archive=OUT/'录音再演奏_App0.3_验证包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
print(json.dumps({'apk':str(target),'sha256':sha(apk),'version':meta['versionName'],'tests':42,'package':str(archive),
 'new_algorithm_integrated':True,'phone_hardware_verified':False,'programmed':False},ensure_ascii=False,indent=2))
