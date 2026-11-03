"""Verify evidence and publish the unprogrammed 0.4 workbench candidate."""
from pathlib import Path
import json,hashlib,re,shutil,zipfile,datetime,html,wave,csv
import xml.etree.ElementTree as ET
import numpy as np
import subprocess
from check_organic_build import timing

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/melody_workbench_20261028';OUT=ROOT/'output/melody_workbench_20261028'
PNR=B/'gowin_final/impl/pnr';NAME='soundcore_workbench_60k';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((B/'baseline_sha256.json').read_text(encoding='utf8'))
allowed={'app/android/app/build.gradle.kts',*['app/android/app/src/main/java/cn/soundcore/instrument/'+n+'.kt' for n in
 ['BleController','CommandQueue','MainActivity','MelodyAudio','MelodyPanel','Protocol']],
 *['rtl/'+n+'.v' for n in ['ble_control_endpoint','oled_status_ssd1315','uploaded_song_engine']],
 'board/pressure_i2s_panel_oled_ble_experiment_top.v','board/pressure_i2s_panel_oled_ble_experiment_60k.gprj','board/soundcore_headphone_60k.gprj'}
changed=[]
for name,digest in baseline.items():
 assert sha(B/'baseline'/name)==digest,'Frozen baseline changed: '+name
 if sha(ROOT/name)!=digest:changed.append(name)
assert set(changed)==allowed,changed
for filename in ['build/mono_recognition_20261028/release.json','build/expression_20261028/release.json']:
 old=json.loads((ROOT/filename).read_text(encoding='utf8'));assert sha(Path(old['firmware']))==old['sha256']
oldapp=json.loads((ROOT/'build/vocal_app_20261028/release.json').read_text(encoding='utf8'))
assert sha(Path(oldapp['apk']))==oldapp['apk_sha256']
assert 'BUILD SUCCESSFUL' in (B/'android_final_verified.log').read_text(encoding='utf-8-sig')
tests=[]
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 t=ET.parse(p).getroot();assert int(t.get('failures'))==0 and int(t.get('errors'))==0
 tests.append({'suite':t.get('name'),'tests':int(t.get('tests'))})
assert sum(t['tests'] for t in tests)==56
lint=ET.parse(ROOT/'app/android/app/build/reports/lint-results-debug.xml').getroot()
assert all(t.get('severity') not in ['Error','Fatal'] for t in lint.findall('issue'))
rtl=json.loads((B/'rtl_checks.json').read_text(encoding='utf8'));assert len(rtl)==9 and all(t['passed'] for t in rtl)
audio=json.loads((B/'real_audio_checks.json').read_text(encoding='utf8'));assert len(audio)==4
endpoints=json.loads((B/'actual_score_endpoint_checks.json').read_text(encoding='utf8'));assert len(endpoints)==4 and all(t['passed'] for t in endpoints)
for name,digest in json.loads((B/'audio_class_sha256.json').read_text(encoding='utf8')).items():
 assert sha(ROOT/name)==digest,'Audio evidence from stale classes: '+name
for item in audio:
 d=B/'real_audio'/item['name'];meta=json.loads((d/'android_score.json').read_text())
 assert meta['notes']==item['notes'] and meta['duration_ms']<=40000

assert 'Bitstream generation completed' in (B/'gowin_final.log').read_text(encoding='utf-8-sig')
timings=timing((PNR/(NAME+'_tr_content.html')).read_text());assert not any(timings['violations'].values())
assert timings['setup_slack_ns']>=0 and timings['hold_slack_ns']>=0
rpt=(PNR/(NAME+'.rpt.txt')).read_text();resources={}
for key in ['Logic','Register','BSRAM','DSP','CLS']:
 m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',rpt,re.M);assert m,key
 used,total=map(float,m.groups());assert used<=total;resources[key]={'used':used,'total':int(total)}
pin_html=(PNR/(NAME+'.pin.html')).read_text();anchor=pin_html.index('<h2><a name="Pinout_by_Port_Name"')
table=pin_html[anchor:pin_html.index('</table>',anchor)];pins={}
for row in re.findall(r'<tr[^>]*>(.*?)</tr>',table,re.S):
 cells=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
 if len(cells)>=5 and cells[0]!='Port Name':pins[cells[0]]=cells[2].split('/')[0]
old=json.loads((ROOT/'build/mono_recognition_20261028/release.json').read_text(encoding='utf8'))
assert pins==old['pins'],'Physical pin mapping changed'
firmware=PNR/(NAME+'.fs');assert firmware.exists()
project=ET.parse(B/'gowin_final/soundcore_workbench_60k.gprj')
hardware=[Path(x.get('path')) for x in project.findall('.//File')]
hardware+=list((ROOT/'board').glob('*.mem'))+list((ROOT/'board').glob('*.vh'))+list((ROOT/'rtl').glob('*.mem'))+list((ROOT/'songs/rom_product_songs').glob('*.mem'))
for p in hardware:assert p.stat().st_mtime<=firmware.stat().st_mtime,'Source newer than firmware: '+str(p)
apk=ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk'
meta=json.loads((apk.parent/'output-metadata.json').read_text())['elements'][0]
assert meta['versionCode']==4 and meta['versionName']=='0.4-melody-workbench'
cert=re.search(r'certificate SHA-256 digest:\s*(\S+)',(B/'apk_certificate.log').read_text(encoding='utf-8-sig'))[1]
assert cert==oldapp['certificate_sha256']
for p in (ROOT/'app/android/app/src/main').rglob('*'):
 if p.is_file():assert p.stat().st_mtime<=apk.stat().st_mtime,'Source newer than APK: '+str(p)

def copy(p,name):
 target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True)
 # Gowin's FS may be read-only; identical already-published content needs no overwrite.
 if target.exists() and sha(target)==sha(p):return target
 shutil.copy2(p,target);return target
target_apk=copy(apk,'声芯_录音工作台_v0.4_候选版.apk')
target_fs=copy(firmware,'firmware/soundcore_headphone_workbench_20261028.fs')
for p in set(hardware):copy(p,Path('source')/p.relative_to(ROOT))
for p in (ROOT/'app/android/app/src').rglob('*'):
 if p.is_file():copy(p,Path('source')/p.relative_to(ROOT))
copy(ROOT/'app/android/app/build.gradle.kts','source/app/android/app/build.gradle.kts')
for name in ['check_melody_workbench.py','generate_capture_oled.py','render_capture_oled.py','evaluate_melody_reference.py','check_workbench_audio.py','package_melody_workbench.py','check_organic_build.py']:
 copy(ROOT/'scripts'/name,Path('source/scripts')/name)
copy(ROOT/'scripts/support/CheckVocalAudio.java','source/scripts/support/CheckVocalAudio.java')
for p in (ROOT/'examples/melody_reference').iterdir():copy(p,Path('参考与核对')/p.name)
for p in (B/'reference').glob('*.json'):copy(p,Path('参考与核对')/p.name)
for p in (B/'reference').glob('*.md'):copy(p,Path('参考与核对')/p.name)
for name in ['melody_workbench_2026-10-28.md','melody_workbench_review_2026-10-28.md']:
 copy(ROOT/'docs'/name,Path('说明')/name)
for p in (ROOT/'tb').glob('tb_capture*.v'):copy(p,Path('source/tb')/p.name)
for name in ['tb_uploaded_song_engine.v','tb_ble_realtime_endpoint.v','tb_ble_extended_state.v','tb_oled_force_geometry.v','tb_oled_product_text.v']:
 copy(ROOT/'tb'/name,Path('source/tb')/name)
for name in ['tb_melody_product_integration.v','tb_uploaded_song_engine.v','CheckVocalAudio.java','changes.diff']:
 copy(B/name,Path('evidence')/name)
for p in B.glob('*.json'):copy(p,Path('evidence')/p.name)
for p in B.glob('*.log'):copy(p,Path('evidence')/p.name)
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):copy(p,Path('evidence/unit_tests')/p.name)
for suffix in ['.rpt.txt','_tr_content.html','.pin.html']:copy(PNR/(NAME+suffix),Path('evidence/gowin')/(NAME+suffix))
for p in (B/'gowin_final').glob('*.tcl'):copy(p,Path('source/build/gowin_final')/p.name)
copy(B/'gowin_final/soundcore_workbench_60k.gprj','source/build/gowin_final/soundcore_workbench_60k.gprj')

titles={'tigers':'两只老虎_演示片段','twinkle':'小星星_演示片段','tigers_holdout':'两只老虎_新片段60至90秒','twinkle_holdout':'小星星_新片段65至100秒'}
for item in audio:
 name=item['name'];d=B/'real_audio'/name
 for file in ['android_notes.csv','android_score.json','recognized.mid','events.mem','android_upload.hex','android_upload_meta.vh','endpoint.log','tb_endpoint.v']:
  copy(d/file,Path('evidence/real_audio')/name/file)
 original=np.fromfile(d/'analysis.f32',dtype='<f4');voice=(original.clip(-1,1)*28000).astype('<i2')
 melody=np.fromfile(d/'preview.s16',dtype='<i2');pad=np.zeros(len(voice),dtype='<i2');offset=item['first_ms']*16
 pad[offset:offset+min(len(melody),len(pad)-offset)]=melody[:min(len(melody),len(pad)-offset)]
 for kind,pcm in [('识别旋律',pad),('原声左_旋律右',np.column_stack([voice,pad]))]:
  dest=OUT/'试听'/(titles[name]+'_'+kind+'.wav');dest.parent.mkdir(exist_ok=True)
  with wave.open(str(dest),'wb') as w:w.setnchannels(1 if pcm.ndim==1 else 2);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm.tobytes())
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(dest),'-c:a','libmp3lame','-q:a','2',str(dest.with_suffix('.mp3'))],check=True)

report={'created':datetime.datetime.now().astimezone().isoformat(),'status':'software_and_rtl_verified_physical_acceptance_pending',
 'apk':str(target_apk),'apk_sha256':sha(target_apk),'version':meta['versionName'],'certificate_sha256':cert,
 'firmware':str(target_fs),'firmware_sha256':sha(target_fs),'user_code':re.search(r'//UserCode:\s*(\S+)',firmware.read_text())[1],
 'android_tests':tests,'android_test_count':sum(x['tests'] for x in tests),'rtl':rtl,'real_audio':audio,'actual_endpoint_checks':endpoints,
 'timing':timings,'resources':resources,'pins':pins,'sources_changed':changed,
 'hardware_source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in set(hardware)},
 'app_source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'app/android/app/src').rglob('*') if p.is_file()},
 'reference_annotation':'score-prior pitches, output/audio-assisted provisional boundaries; not human-verified or independent timing truth',
 'recognizer_song_specific_branches':False,'recognition_parameters_changed':False,'previous_apk_and_firmware_preserved':True,
 'physical_microphone_verified':False,'android_ui_verified':False,'android_decoder_verified':False,'physical_ble_verified':False,'physical_oled_verified':False,
 'sram_written':False,'flash_written':False,'hardware_scanned':False,'end_to_end_latency_measured':False,
 'limits':{'max_input_file_seconds':180,'max_score_seconds':40,'events':512,'midi':[60,94]}}
(B/'release.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');copy(B/'release.json','evidence/release.json')
(OUT/'先读我.txt').write_text('''声芯0.4录音工作台候选版，可覆盖0.3。
入口：曲目 → 录一段，接着奏。录音/选择文件 → 选0.25–40秒片段 → 听原声 → 识别 → 对照/点音符修正 → 传入设备 → 演奏/指引。
手机功能无需新硬件。OLED全过程需本包firmware中的配套固件；本轮没有烧录，旧固件自动降级。
OLED图片来自实际RTL像素和I2C验证，数值为测试输入，不是实物照片。保留七路力度和原数字尺寸。
参考逐音表含候选时间边界，未经人工逐音听审，不能将其核对距离当作独立准确率。
试听文件由实际新App编译类输出；“原声左_旋律右”便于用耳机对照。新片段来自同一原始录音，不是新歌手泛化试验。
真实手机收音、Android界面/解码、无线、OLED实物显示、音色及端到端延迟仍待验收。
''',encoding='utf-8-sig')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files};(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'录音工作台与OLED_0.4验证包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
print(json.dumps({'apk':str(target_apk),'sha256':sha(target_apk),'firmware':str(target_fs),'user_code':report['user_code'],
 'tests':report['android_test_count'],'rtl_checks':len(rtl),'timing':timings,'resources':resources,'package':str(archive),'programmed':False},ensure_ascii=False,indent=2))
