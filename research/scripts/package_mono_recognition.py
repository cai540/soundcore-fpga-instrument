"""Verify and package the bounded monophonic recognition candidate; never programs hardware."""
from pathlib import Path
import datetime,difflib,hashlib,html,json,re,shutil,xml.etree.ElementTree as ET,zipfile
from check_organic_build import timing

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/mono_recognition_20261028'
OUT=ROOT/'output/mono_recognition_20261028'
PNR=BUILD/'gowin/impl/pnr';NAME='soundcore_melody_60k'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

baseline=json.loads((BUILD/'baseline_sha256.json').read_text())
changed=[]
for name,digest in baseline.items():
 assert sha(BUILD/'baseline'/name)==digest,'Frozen baseline changed: '+name
 assert (ROOT/name).exists(),name
 if sha(ROOT/name)!=digest:changed.append(name)
allowed={'rtl/ble_control_endpoint.v','board/pressure_i2s_panel_oled_ble_experiment_top.v',
 'app/android/app/src/main/AndroidManifest.xml',*['app/android/app/src/main/java/cn/soundcore/instrument/'+x+'.kt'
  for x in ['BleController','CommandQueue','MainActivity','Protocol','StudioScreen']]}
assert set(changed)==allowed,changed
previous=json.loads((BUILD/'baseline/build/expression_20261028/release.json').read_text(encoding='utf-8'))
assert sha(Path(previous['firmware']))==previous['sha256'],'Previous 74FD candidate changed'

rtl=json.loads((BUILD/'rtl_checks.json').read_text())
assert len(rtl)==8 and all(t['passed'] for t in rtl)
legacy=['tb_audio_song_full_playback','tb_lyric_position','tb_song_lyric_continuous',
 'tb_song_lyric_oled_flow','tb_score_midi_review_rom','tb_product_song_guide',
 'tb_song_word_articulation','tb_oled_karaoke_render','tb_oled_karaoke_integration']
for test in legacy:
 log=(BUILD/('legacy_'+test+'.log')).read_text()
 assert 'PASS:' in log and 'FATAL:' not in log,test
assert '\nOK\n' in (BUILD/'legacy_data_test.log').read_text()
android=[]
for path in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 suite=ET.parse(path).getroot()
 assert int(suite.attrib['failures'])==0 and int(suite.attrib['errors'])==0,path
 android.append({'suite':suite.attrib['name'],'tests':int(suite.attrib['tests'])})
assert sum(x['tests'] for x in android)==36
assert 'BUILD SUCCESSFUL' in (BUILD/'android_final_build.log').read_text(encoding='utf-8-sig')
lint=ET.parse(ROOT/'app/android/app/build/reports/lint-results-debug.xml').getroot()
issues=[{'id':x.attrib['id'],'severity':x.attrib['severity']} for x in lint.findall('issue')]
assert all(x['severity'] not in ('Error','Fatal') for x in issues)
fixture=json.loads((BUILD/'fixtures/recognition_metrics.json').read_text())
assert fixture['correct_pitches']==12 and fixture['events']==15 and fixture['max_boundary_error_ms']<=60

assert 'Bitstream generation completed' in (BUILD/'gowin_build.log').read_text(encoding='utf-8-sig')
timing_result=timing((PNR/(NAME+'_tr_content.html')).read_text())
assert not any(timing_result['violations'].values()) and min(timing_result['setup_slack_ns'],timing_result['hold_slack_ns'])>=0
rpt=(PNR/(NAME+'.rpt.txt')).read_text();resources={}
for key in ['Logic','Register','CLS','BSRAM','DSP']:
 m=re.search(r'^\s*'+key+r'\s*\|\s*(\d+)/(\d+)',rpt,re.M);assert m,key
 used,total=map(int,m.groups());assert used<=total
 resources[key]={'used':used,'total':total,'utilization_percent':round(used*100/total,2)}
pin_html=(PNR/(NAME+'.pin.html')).read_text();anchor=pin_html.index('<h2><a name="Pinout_by_Port_Name"')
table=pin_html[anchor:pin_html.index('</table>',anchor)];pins={}
for row in re.findall(r'<tr[^>]*>(.*?)</tr>',table,re.S):
 cells=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
 if len(cells)>=5 and cells[0]!='Port Name':pins[cells[0]]=cells[2].split('/')[0]
assert pins==previous['pins'],'External pins changed'
image=PNR/(NAME+'.fs')
project=ET.parse(BUILD/'gowin/soundcore_melody_60k.gprj')
hardware=[Path(x.attrib['path']) for x in project.findall('.//File')]
hardware+=list((ROOT/'rtl').glob('*.mem'))+list((ROOT/'board').glob('*.vh'))
hardware+=list((ROOT/'songs/rom_product_songs').glob('*.mem'))
for path in hardware:assert path.stat().st_mtime<=image.stat().st_mtime,'Source newer than image: '+str(path)
hardware_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in hardware}
apk=ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk'
for path in (ROOT/'app/android/app/src/main').rglob('*'):
 if path.is_file():assert path.stat().st_mtime<=apk.stat().st_mtime,'Source newer than APK: '+str(path)
assert (ROOT/'app/android/app/build.gradle.kts').stat().st_mtime<=apk.stat().st_mtime
apk_meta=json.loads((apk.parent/'output-metadata.json').read_text())['elements'][0]
assert apk_meta['versionCode']==2 and apk_meta['versionName']=='0.2-melody-candidate'

OUT.mkdir(parents=True,exist_ok=True)
def copy(source,dest):
 path=OUT/dest;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,path)
target=ROOT/'build/soundcore_headphone_melody_20261028.fs'
if target.exists():assert sha(target)==sha(image),'Refuse to replace a published different firmware'
else:shutil.copy2(image,target)
copy(target,'firmware/soundcore_headphone_melody_20261028.fs')
copy(apk,'声芯_单乐器识谱_候选版.apk')
copy(Path(previous['firmware']),'rollback/soundcore_headphone_expression_74FD.fs')
for source,dest in [(NAME+'.rpt.txt','resource_report.txt'),(NAME+'_tr_content.html','timing_report.html'),(NAME+'.pin.html','pin_report.html')]:
 shutil.copy2(PNR/source,BUILD/dest);copy(PNR/source,'evidence/'+dest)

for path in hardware:copy(path,Path('source')/path.relative_to(ROOT))
for path in (ROOT/'app/android').rglob('*'):
 if path.is_file() and 'build' not in path.relative_to(ROOT/'app/android').parts and '.gradle' not in path.parts and path.name!='local.properties':
  copy(path,Path('source/app/android')/path.relative_to(ROOT/'app/android'))
for path in (BUILD/'fixtures').glob('*'):copy(path,Path('试听与测试旋律')/path.name)
for path in BUILD.glob('*.log'):copy(path,Path('evidence')/path.name)
for path in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):copy(path,Path('evidence/android')/path.name)
copy(ROOT/'app/android/app/build/reports/lint-results-debug.xml','evidence/android/lint-results-debug.xml')
for name in ['mono_recognition_2026-10-28.md','mono_recognition_review_2026-10-28.md']:
 copy(ROOT/'docs'/name,Path('说明')/name)
copy(ROOT/'docs/plans/2026-10-28-mono-recognition-implementation.md','说明/implementation.md')
for test in [x['test'] for x in rtl]+['tb_ble_extended_state','tb_ble_telemetry_scene']:
 copy(ROOT/'tb'/(test+'.v'),Path('source/tb')/(test+'.v'))
for name in ['check_mono_recognition.py','package_mono_recognition.py']:
 copy(ROOT/'scripts'/name,Path('source/scripts')/name)
copy(BUILD/'gowin/soundcore_melody_60k.gprj','source/build/mono_recognition_20261028/gowin/soundcore_melody_60k.gprj')
copy(BUILD/'gowin/build.tcl','source/build/mono_recognition_20261028/gowin/build.tcl')
code=re.search(r'//UserCode:\s*(\S+)',target.read_text())[1]
result={
 'created':datetime.datetime.now().astimezone().isoformat(),'status':'software_candidate_awaiting_phone_and_board_acceptance',
 'firmware':str(target),'sha256':sha(target),'user_code':code,
 'apk':str(OUT/'声芯_单乐器识谱_候选版.apk'),'apk_sha256':sha(apk),'apk_version':apk_meta['versionName'],
 'limits':{'max_seconds':40,'max_events':512,'midi_range':[60,94],'analysis_rate_hz':16000,'polyphonic_input':False},
 'android_tests':android,'android_test_count':36,'lint_issues':issues,
 'rtl_tests':rtl,'legacy_rtl_tests':legacy,'legacy_data_tests':4,
 'synthetic_fixture':fixture,'resources':resources,**timing_result,'pins':pins,'pins_unchanged':True,
 'hardware_source_sha256':hardware_hashes,'baseline_files':len(baseline),'changed_baseline_files':changed,
 'previous_firmware_unchanged':True,'baseline_user_code':previous['user_code'],
 'built_in_song_data_regression_passed':True,'board_score_persists_power_cycle':False,
 'phone_last_playable_score_saved':True,'cloud_required':False,
 'sram_written':False,'flash_written':False,'hardware_scan_performed':False,
 'physical_recording_verified':False,'physical_ble_verified':False,'physical_listening_verified':False,
 'app_screenshot_verified':False,'measured_end_to_end_latency_ms':None,
 'known_limitations':['Clean monophonic instrument input only; no chords or source separation',
  '40 seconds and 512 events; very fast ornaments may be merged','Phone microphone/decoder and new UI remain unverified on a real phone',
  'Actual JDY transfer and physical board playback/guide remain unverified','RAM score is lost on power-off; phone can re-upload',
  'Existing generic clock routing warning PR1014 remains; constrained timing has no violations']}
(BUILD/'release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
copy(BUILD/'release.json','evidence/release.json');copy(BUILD/'rtl_checks.json','evidence/rtl_checks.json')
(OUT/'先读我.txt').write_text('单乐器录音识谱候选版，尚未烧录。\n安装 APK 后进入 曲目 → 录一段，接着奏。\n先录或选择5–15秒清晰独奏，再试听。最长40秒，不支持和弦或带伴奏的歌曲。\n传入设备需要配套 firmware 中的耳机版候选固件；旧固件只能识别和手机试听。\n设备中的旋律断电丢失，手机保存最近可演奏旋律并可重传。\n麦克风、页面显示、实际蓝牙和实板听感尚待验收。\n试听与测试旋律中的 WAV/MIDI 是人工合成夹具，不是真实乐器实测。\n完整说明位于 说明 文件夹。\n',encoding='utf-8-sig')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files}
(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
archive=OUT/'单乐器录音识谱_候选版_20261028.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
print(json.dumps({'apk':result['apk'],'firmware':str(target),'user_code':code,'resources':resources,
 'setup_slack_ns':result['setup_slack_ns'],'hold_slack_ns':result['hold_slack_ns'],
 'package':str(archive),'programmed':False},ensure_ascii=False,indent=2))
