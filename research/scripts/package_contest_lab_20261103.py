"""Gate and package B713/App0.24, source evidence and laboratory instructions.
Never connects to the programmer. A generated image is not a hardware pass.
"""
from pathlib import Path
import hashlib,html,json,re,shutil,subprocess,os,stat,zipfile,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1];B=R/'build/contest_audit_20261103';F=B/'firmware';O=R/'output/contest_lab_20261103';N='soundcore_speaker_omr_60k';P=F/'impl/pnr'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def copy(src,dest):
 dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():
  if sha(src)==sha(dest):return
  dest.chmod(dest.stat().st_mode|stat.S_IWRITE)
 shutil.copy2(src,dest)
assert 'Bitstream generation completed' in (F/'build.log').read_text(encoding='utf8')
assert 'BUILD SUCCESSFUL' in (B/'android_final.log').read_text(encoding='utf8')
timing_html=(P/(N+'_tr_content.html')).read_text(encoding='utf8');text=BeautifulSoup(timing_html,'html.parser').get_text(' ',strip=True)
violations={k:int(re.search('Numbers of '+k+r' Violated Endpoints (\d+)',text)[1])for k in ('Setup','Hold')}
assert not any(violations.values())
soup=BeautifulSoup(timing_html,'html.parser')
slacks={}
for kind in ('Setup','Hold'):
 row=soup.find('a',attrs={'name':kind+'_Slack_Table'}).find_parent('h3').find_next('table').find_all('tr')[1]
 slacks[kind]=float(row.find_all('td')[1].get_text(strip=True))
 assert slacks[kind]>0
frozen=json.loads((F/'frozen_inputs.json').read_text())
assert all(sha(F/'src'/p)==h for p,h in frozen.items())
baseline=R/'build/product_repair_20261103';constraint='src/board/soundcore_speaker_omr_60k.cst'
assert sha(F/constraint)==sha(baseline/constraint)
expected=dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([A-Z]+\d+);',(F/constraint).read_text()))
pin_soup=BeautifulSoup((P/(N+'.pin.html')).read_text(),'html.parser')
actual={cells[0]:cells[2].split('/')[0]for row in pin_soup.find_all('table')[1].find_all('tr')[1:]if(cells:=[c.get_text(' ',strip=True)for c in row.find_all('td')])}
assert actual==expected and len(actual)==29
external=json.loads((baseline/'external_literals.json').read_text())
for path,entry in external.items():
 assert sha(path)==entry['sha256']
 assert all(sha(F/'src'/name)==entry['sha256'] for name in entry['frozen_matches'])
code=re.search(r'UserCode:\s*(0x[0-9a-fA-F]+)',(P/(N+'.fs')).read_bytes()[:1600].decode('ascii',errors='replace'))[1]
assert int(code,16)==0xb713
tests=[ET.parse(p).getroot()for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
totals={k:sum(int(x.get(k,'0'))for x in tests)for k in ('tests','failures','errors','skipped')}
assert totals['tests']>=330 and totals['failures']==totals['errors']==0
rtl=json.loads((B/'rtl_checks/results.json').read_text());assert len(rtl)==7 and all(r['passed']for r in rtl)
voice=json.loads((B/'voices/voices32_results.json').read_text());assert voice['voices']==32 and voice['max_frame_cycles']<=256 and voice['residual_ratio']<.02
latency=json.loads((B/'latency_final/summary.json').read_text());weak=json.loads((B/'latency_final_weak/summary.json').read_text())
assert latency['cases']==weak['cases']==70 and latency['max_step_to_abs64_i2s_ms']<5 and weak['max_step_to_abs8_i2s_ms']<5
apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk'
env=os.environ.copy();env['JAVA_HOME']='D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1'
sign=subprocess.run(['cmd.exe','/c','D:/FPGA/_Tools/android/sdk/build-tools/35.0.0/apksigner.bat','verify','--print-certs',str(apk)],env=env,capture_output=True,text=True)
assert sign.returncode==0,sign.stdout+sign.stderr
cert=re.search(r'certificate SHA-256 digest: ([0-9a-f]{64})',sign.stdout)[1]
assert cert=='d6d6a066cddaf6267acf014430bf0dd3e12ce0027f6a4a055c3bcdde5f320abc'
gradle=(R/'app/android/app/build.gradle.kts').read_text();assert 'versionCode = 24' in gradle and '0.24-scope-lab' in gradle
copy(apk,O/'声芯乐动_0.24_示波器验收版.apk');copy(P/(N+'.fs'),O/'声芯乐动_B713_完整音响_节奏指引_ADSR.fs')
E=O/'验证记录';E.mkdir(exist_ok=True)
for src,name in [(B/'android_final.log','Android构建与检查.log'),(R/'app/android/app/build/reports/lint-results-debug.txt','AndroidLint.txt'),
 (F/'build.log','FPGA完整构建.log'),(F/'frozen_inputs.json','冻结源SHA256.json'),(F/'build.tcl','构建选项.tcl'),
 (B/'rtl_checks/results.json','受影响RTL测试.json'),(B/'rtl_checks/icarus_compatibility.json','仿真兼容处理说明.json'),
 (B/'voices/voices32_results.json','32声部I2S仿真.json'),(B/'voices/tb_tools_voices_i2s.log','32声部独立控制.log'),
 (B/'latency_final/summary.json','强阶跃70组_非实测.json'),(B/'latency_final/physical_latency.csv','强阶跃70组_非实测.csv'),
 (B/'latency_final_weak/summary.json','弱阶跃70组_8计数门限_非实测.json'),(B/'latency_final_weak/physical_latency.csv','弱阶跃70组_8计数门限_非实测.csv'),
 (B/'latency_weak/simulation.log','弱阶跃64计数未通过5ms_保留失败.log'),
 (R/'docs/product_tools_protocol.md','工具协议.md'),(B/'source/source_manifest.json','官方赛题来源SHA256.json')]:copy(src,E/name)
for name in [N+'.rpt.txt',N+'_tr_content.html',N+'.pin.html']:copy(P/name,E/name)
for name in ('lab_pcm_check.py','lab_latency_summary.py','lab_audio_inspect.py'):copy(R/'scripts'/name,O/'数据分析脚本'/name)
for test in rtl:copy(B/'rtl_checks'/(test['test']+'.log'),E/(test['test']+'.log'))
copy(R/'scripts/check_contest_completion_20261103.py',E/'RTL测试复现.py')
copy(R/'scripts/simulation_sources.py',E/'simulation_sources.py')
with zipfile.ZipFile(O/'B713冻结源与本轮修改.zip','w',zipfile.ZIP_DEFLATED)as archive:
 for p in (F/'src').rglob('*'):
  if p.is_file():archive.write(p,'frozen/src/'+p.relative_to(F/'src').as_posix())
 archive.write(F/(N+'.gprj'),'frozen/'+N+'.gprj')
 archive.write(F/'build.tcl','frozen/build.tcl')
 for name in ['scripts/build_contest_rhythm_20261103.py','scripts/preflight_latency_20261101.py','scripts/check_contest_completion_20261103.py','scripts/simulation_sources.py','tb/tb_product_adsr.v','tb/tb_guide_rhythm_cue.v','tb/tb_contest_guide_top.v']:
  archive.write(R/name,name)
 for name in ('ScopeAnalysis.kt','LiveAudioScope.kt','LiveScopePlot.kt','ScopeWorkbench.kt','ProductToolsController.kt','ProductToolsPanel.kt','ProductTools.kt'):
  archive.write(R/'app/android/app/src/main/java/cn/soundcore/instrument'/name,'android_changes/'+name)
 archive.writestr('说明.txt','冻结源和GPRJ保留实际构建时的D:/FPGA绝对路径，供本工作区复现；不是跨电脑免配置工程。Gowin软件/仿真库须自行安装。不得把仿真结果写成实测。')
manifest=dict(firmware=code,app='0.24-scope-lab',programmed=False,physical_acceptance='pending',
 official_url='https://www.gowinsemi.com.cn/university/match2026',atomic_requirements=34,
 android_tests=totals,rtl_tests=rtl,timing_violations=violations,slacks_ns=slacks,pins_unchanged=actual,
 active_voices_simulated=32,frames_max_cycles=voice['max_frame_cycles'],actual_sample_rate_hardware_hz=None,
 digital_latency_strong_ms=latency['max_step_to_abs64_i2s_ms'],digital_latency_weak_at_abs8_ms=weak['max_step_to_abs8_i2s_ms'],
 weak_at_abs64_under5ms=False,physical_latency_ms=None,zero_jitter_measured=False,
 signer_sha256=cert,frozen_sources_verified=True,external_literal_hashes_verified=True,
 limitations=['ADC/amp/physical timing and audibility pending','phone microphone and BLE timing require a real phone','mono delayed XY is not a two-channel phase meter','9600-baud snapshots are not continuous PCM'],
 artifacts={p.relative_to(O).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.rglob('*')if p.is_file()and p.name not in ('release_manifest.json','完整验收包.zip')})
(O/'先读这里.txt').write_text('声芯乐动 0.24 / B713 验收准备包\n\n1. 安装APK覆盖旧版，书架/识谱/录音算法沿用0.23，新增示波器。\n2. 本轮没有烧录；B713是完成布局布线、数字检查的完整音响候选，先SRAM验收再决定Flash。29引脚约束没变。\n3. 看“实验室随身检查卡.pdf”，细节看“明日实验室详细指导.pdf/html”；34项完整对照在CSV/JSON。\n4. 先测32活跃可闻独立声部×实际Fs，再测压力到功放总延迟/抖动，最后测全部联动。实测表为空，不填虚构数据。\n5. 波形/频谱/XY全屏可横放手机。麦克风为手机现场声音；FPGA快照是硬件分析但受9600串口带宽限制。\n6. 源码快照保留本工作区原路径，不等同于跨电脑免配置项目。\n\n没有把数字预检当成<5ms物理保证，也没有宣称已测零抖动。',encoding='utf8')
manifest['artifacts']['先读这里.txt']=dict(bytes=(O/'先读这里.txt').stat().st_size,sha256=sha(O/'先读这里.txt'))
(O/'release_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(output=str(O),user_code=code,android=totals,slacks=slacks,rtl=len(rtl)),ensure_ascii=False,indent=2))
