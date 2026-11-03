"""Package only after actual Gowin PNR and Android checks pass. Never programs a device."""
from pathlib import Path
import re,json,shutil,hashlib,xml.etree.ElementTree as ET,zipfile,csv,html,stat
from bs4 import BeautifulSoup
import markdown
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';O=R/'output/acceptance_20261102';N='soundcore_speaker_omr_60k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists():q.chmod(stat.S_IREAD|stat.S_IWRITE)
 shutil.copy2(p,q)
def read(p):return p.read_text(encoding='utf8')
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf8')
def ziptree(folder,target):
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5)as z:
  for p in sorted(folder.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(folder))

def package():
 O.mkdir(parents=True,exist_ok=True)
 log=read(B/'build.log');assert 'ERROR'not in log,'Gowin has errors; do not deliver a stale bitstream'
 fs=B/'impl/pnr'/(N+'.fs');assert fs.exists()and fs.stat().st_mtime>=(B/'build.tcl').stat().st_mtime
 assert re.search(r'//UserCode:\s*0x0000a623\b',read(fs),re.I),'Unexpected bitstream UserCode'
 assert 'A623'in read(B/'build.tcl')
 timing_path=B/'impl/pnr'/(N+'_tr_content.html');assert timing_path.stat().st_mtime>=(B/'build.tcl').stat().st_mtime
 timing=BeautifulSoup(read(timing_path),'html.parser').get_text(' ',strip=True)
 violations={k:int(re.search(r'Numbers of '+k+r' Violated Endpoints (\d+)',timing)[1])for k in('Setup','Hold')};assert sum(violations.values())==0
 match=re.search(r'12\.288\(MHz\) ([\d.]+)\(MHz\)',timing);assert match and float(match[1])>12.288
 rpt=read(B/'impl/pnr'/(N+'.rpt.txt'))
 resource={}
 for key in('Logic','Register','CLS','BSRAM','DSP'):
  m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/(\d+)',rpt,re.M);assert m,key
  resource[key]={'used':float(m[1]),'available':int(m[2])};assert float(m[1])<=int(m[2])
 assert 'BUILD SUCCESSFUL'in read(B/'android_all_checks.log')
 suites=[ET.parse(p).getroot()for p in(R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
 junit={k:sum(int(s.get(k,'0'))for s in suites)for k in('tests','failures','errors','skipped')};assert junit['failures']==junit['errors']==0 and junit['tests']>=300
 skipped_tests=[s.get('name','')+'.'+t.get('name','')for s in suites for t in s.findall('testcase')if t.find('skipped')is not None]
 baseline=json.loads(read(B/'baseline_hashes.json'));assert all(sha(R/p)==h for p,h in baseline['recognition_assets'].items())
 protected=[p for p in baseline['files']if p.endswith('.cst')or p in ['rtl/expression_normalized.mem','rtl/expression_raw.mem','rtl/synth_voice.v','rtl/song_event_player.v','rtl/front_panel_product.v','rtl/pressure_expression32.v']]
 assert all(sha(R/p)==baseline['files'][p]for p in protected)
 inputs=json.loads(read(B/'frozen_inputs.json'));assert all(sha(B/'src'/p)==h for p,h in inputs.items())
 voices=json.loads(read(B/'voices32_results.json'));assert voices['voices']==32 and voices['max_frame_cycles']<256
 dsp=json.loads(read(B/'dsp_results.json'));assert all(t['passed']for t in dsp['tests'])
 capacity=json.loads(read(B/'record_capacity_results.json'));assert capacity['samples']==64000
 regress=json.loads(read(R/'build/low_latency_20261101/tests/results.json'));assert all(x['passed']for x in regress)
 apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk';assert apk.exists()
 with zipfile.ZipFile(apk)as z:
  for p,h in baseline['recognition_assets'].items():
   name='assets/'+p.split('/assets/',1)[1];assert hashlib.sha256(z.read(name)).hexdigest()==h,('APK asset mismatch',name)
 copy(apk,O/'声芯乐动_0.22_验收版.apk');copy(fs,O/'声芯乐动_A623_完整音响版.fs')
 evidence=O/'evidence';evidence.mkdir(exist_ok=True)
 for p in B.glob('*.json'):
  if not p.name.startswith('pre_'):copy(p,evidence/p.name)
 for p in B.glob('*.log'):
  if not p.name.startswith('pre_'):copy(p,evidence/p.name)
 for name in ['record_bytes.txt','record_decoded.txt','record_filtered.txt','record_crc.txt','record_full_bytes.txt','record_full_filtered.txt','record_full_crc.txt','fft_complex.txt','fft_vendor_complex.txt','analysis_vectors.txt','analysis_vendor_vectors.txt','phase_bitmap.txt','phase_vendor_bitmap.txt','oled_analysis_frames.hex','voices32_i2s.txt']:
  copy(B/name,evidence/name)
 for name in [N+'.rpt.txt',N+'.pin.html',N+'.tr.html',N+'_tr_content.html',N+'_tr_cata.html']:
  copy(B/'impl/pnr'/name,evidence/name)
 copy(B/'impl/gwsynthesis'/(N+'_syn.rpt.html'),evidence/(N+'_syn.rpt.html'))
 shutil.copytree(B/'latency',evidence/'latency',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.vvp'))
 copy(R/'build/low_latency_20261101/tests/results.json',evidence/'legacy_regression_results.json')
 for p in(R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):copy(p,evidence/'android'/p.name)
 copy(R/'app/android/app/build/reports/lint-results-debug.txt',evidence/'android/lint-results-debug.txt')
 for p in(R/'app/android/app/src/test/snapshots/images').glob('*ToolsSnapshotsTest*.png'):copy(p,O/'previews'/p.name)
 for p in(R/'app/android/app/src/main/assets/scores').glob('*.json'):copy(p,O/'scores'/p.name)
 copy(R/'docs/acceptance_lab_20261102.md',O/'实验室验收手册.md');copy(R/'docs/product_tools_protocol.md',O/'协议与实现说明.md')
 for name in ['lab_audio_inspect.py','check_lab_analysis.py']:copy(R/'scripts'/name,O/'lab_tools'/name)
 # Portable FPGA project is the exact frozen source, with path-only rebasing.
 source=O/'source';fpga=source/'fpga';fpga.mkdir(parents=True,exist_ok=True)
 shutil.copytree(B/'src',fpga/'src',dirs_exist_ok=True)
 prefix=(B/'src').as_posix()+'/'
 for p in(fpga/'src').rglob('*'):
  if p.suffix in('.v','.vh','.sdc','.cst'):write(p,read(p).replace(prefix,'src/'))
 tree=ET.parse(B/(N+'.gprj'))
 for f in tree.findall('./FileList/File'):f.set('path',f.get('path').replace(prefix,'src/'))
 tree.write(fpga/(N+'.gprj'),encoding='utf8',xml_declaration=True)
 write(fpga/'build.tcl',f'open_project ./{N}.gprj\nset_option -top_module soundcore_speaker_omr_top\nset_option -user_code 0000A623\nrun all\n')
 write(fpga/'build.ps1',"param([string]$GowinShell='D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')\n$ErrorActionPreference='Stop'\nPush-Location -LiteralPath $PSScriptRoot\ntry { & $GowinShell 'build.tcl'; if ($LASTEXITCODE -ne 0) { throw 'Build failed' } } finally { Pop-Location }\n")
 for p in(fpga/'src').rglob('*.v'):
  assert 'D:/FPGA/'not in read(p),(p,'unrebased absolute asset path')
 # APK production source, without local SDK paths, signing keys or build caches.
 shutil.copytree(R/'app/android',source/'app/android',dirs_exist_ok=True,ignore=shutil.ignore_patterns('build','.gradle','local.properties','.kotlin','*.jks','*.keystore'))
 shutil.copytree(R/'tests/fixtures',source/'tests/fixtures',dirs_exist_ok=True)
 for p in(R/'scripts').glob('*20261102.py'):
  if p.name.startswith(('check_','generate_product','build_acceptance','render_acceptance')):copy(p,source/'reference_scripts'/p.name)
 for p in(R/'tb').glob('tb_tools*.v'):copy(p,source/'reference_tb'/p.name)
 for name in ['record_bytes.txt','record_decoded.txt','record_crc.txt','analysis_vectors.txt']:copy(B/name,source/'build/acceptance_20261102'/name)
 write(source/'重建说明.md',f'''# 重建说明

FPGA：在fpga目录执行build.ps1，或用Gowin1.9.11.03 Education打开{N}.gprj。目标GW5AT-LV60PG484AC1/I0，顶层soundcore_speaker_omr_top，UserCode0000A623。路径已改为本地相对路径；build.ps1不包含烧录操作。版本/布局种子可能影响重建二进制哈希。

Android：app/android为生产源码。配置JDK17、AndroidSDK36和Gradle8.13，执行gradle :app:assembleDebug即可重建APK。发行包不含本机local.properties、调试签名私钥或Gradle缓存。重建后签名可能与本包不同，不能保证直接覆盖手机上已安装版本。

reference_scripts和reference_tb是本轮仿真/分析源码，保留原项目目录合同以便回到原工作区复现。完整历史识别测试依赖原工作区历史数据；其执行结果在外层evidence/android。FPGA工程和APK生产编译不依赖这些历史试听文件。

第三方模型、库和许可证均随Android资产保留。内置识别资产24项与本轮开始时一致。本轮新增的是产品工具、硬件音频分析/压缩回传、映射和曲谱数据流程；没有新增模型训练结果。
''')
 hashes={p.relative_to(source).as_posix():sha(p)for p in source.rglob('*')if p.is_file()and p!=source/'source_hashes.json'};write(source/'source_hashes.json',json.dumps(hashes,ensure_ascii=False,indent=2))
 ziptree(source,O/'配套源码.zip')
 # Blank physical records intentionally contain no simulated measurements.
 with(O/'硬件实测记录.csv').open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.writer(f);w.writerow(['case_id','音色','音区','琴片','力度','音效','重复次数','输入判据','输出判据','延迟ms','LRCLK_Hz','活动声部','原始CSV','实际结论'])
  for timbre in ['二胡','口琴']:
   for pad in range(1,8):w.writerow([f'{timbre}-3-{pad}',timbre,3,pad,'正常',0,20,'','','','','','','待测'])
  for n in(4,8,16,32):w.writerow([f'poly-{n}','检测正弦','','','','','','','', '', '',n,'','待测'])
 manifest={'firmware_user_code':'0x0000A623','apk_version':'0.22-product-tools-offline','programming_performed':False,
  'physical_acceptance':'not performed; operator CSV required','resources':resource,'timing':dict(violations,fmax_mhz=float(match[1]),constraint_mhz=12.288,external_io_not_certified=True),
  'android_junit':junit,'android_skipped_tests':skipped_tests,'new_dsp_tests':dsp,'voices':voices,'record_capacity':capacity,'latency_simulation':json.loads(read(B/'latency/summary.json')),
  'protected_pin_and_timbre_inputs':protected,'recognition_asset_count_unchanged':len(baseline['recognition_assets']),
  'site':{'version':8,'url':'https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/catalog.html','audience':'original owner-only access preserved'},
  'limits':['8-second8kHz IMA recording','32-point delayed mono phase plot','online catalogue preserves original sign-in restriction','handpan/metal retained in prior0.21 candidate','physical latency,actual LRCLK,force calibration and audio quality await hardware test']}
 manifest['files']={p.name:sha(p)for p in[O/'声芯乐动_0.22_验收版.apk',O/'声芯乐动_A623_完整音响版.fs',O/'配套源码.zip']}
 write(O/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
 summary=f'''# 本轮交付与验证

配套：App0.22 / A623完整音响固件。未执行任何硬件烧录。先按实验室手册测试SRAM，通过后再写Flash。

- 32声部：真实RTL I2S解码32个基频，独立关断/重触发/变调；每帧225/256时钟。仅仿真，未用App请求数量代替实际引擎计数。
- 新增真实波形、1024点FFT、延迟相图，同步OLED和App；7片自定义映射、完整8秒设备音频采集/回传/WAV导出；在线目录/JSON导入/缓存/试听/上传/指引。
- Android：{junit['tests']}项中{junit['tests']-junit['skipped']}项通过，跳过{junit['skipped']}项，失败{junit['failures']}，错误{junit['errors']}；跳过项为既有条件启用的长录音质量/训练导出及外部API联网测试，名称保留在manifest。assembleDebug、lintDebug成功。6幅新增Compose页面已渲染检查。
- Gowin：布局布线成功；Setup/Hold违例0/0；音频时钟约束12.288MHz，对应Fmax{match[1]}MHz。静态时序不代替外部I/O和实板测量。
- Logic {resource['Logic']['used']:g}/{resource['Logic']['available']}；CLS {resource['CLS']['used']:g}/{resource['CLS']['available']}；BSRAM {resource['BSRAM']['used']:g}/118；DSP {resource['DSP']['used']:g}/118。
- 16工况数字链路预检：ADC阶跃到首个非零I2S最大1.218ms，到|PCM|≥64最大2.973ms。该门限不是可听阈值；功放/喇叭和物理抖动仍待测。
- 既有引脚/按钮逻辑与音色数据保护项一致；24项内置识别资产哈希一致。原有正常功能完成回归，新模型准确率没有在本轮重新认证。

必须实测：供电/七片力度、OLED和五键冷启动、32频谱及单声部改变、实际LRCLK、压力→I2S/功放延迟及抖动、音效听感、实际蓝牙回传耗时与断线重读。硬件实测记录.csv初始留空。

新增范围与限制：相图32点（单声道及延迟信号），设备录音8kHz压缩、最长8秒；在线目录沿用原站登录权限。手碟/金属暂留原候选版。本包沿用现有力度标定，第7片满格需现场确认。

本轮代码审查修正了回复归属、切页停止、空操作误清普通声部、机身优先级、完整帧锁存、厂商RAM模式和重复录音token等问题。没有把仿真标成硬件验收。
'''
 write(O/'交付说明.md',summary)
 make_html(O,summary)
 write(O/'SHA256SUMS.txt','\n'.join(f'{sha(p)}  {p.relative_to(O).as_posix()}'for p in sorted(O.rglob('*'))if p.is_file()and p.name!='SHA256SUMS.txt'))
 print(json.dumps({'output':str(O),'junit':junit,'resources':resource,'fmax_mhz':match[1]},ensure_ascii=False,indent=2))

def make_html(out,summary):
 css='''body{margin:0;background:#f3f6f7;color:#172f3c;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1120px;margin:32px auto;padding:36px;background:white;border-radius:20px}h1{font-size:32px;line-height:1.4}h2{margin-top:48px;padding-top:14px;border-top:1px solid #dbe4e8}h3{margin-top:30px}a{color:#087b70}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:11px;border:1px solid #dbe4e8;text-align:left}th{background:#eff5f4}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2f5;padding:18px;border-radius:10px;font:13px/1.7 Consolas,monospace}code{overflow-wrap:anywhere}img{max-width:100%;height:auto}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.cards figure{margin:0;border:1px solid #dbe4e8;border-radius:18px;padding:12px}.cards img{max-height:550px;display:block;margin:auto}.badge{display:inline-block;padding:8px 15px;background:#e4f6f1;border-radius:20px;margin-right:10px}nav{background:#edf5f2;padding:18px;border-radius:12px}footer{font-size:13px;color:#607d8b;margin-top:40px}@media(max-width:650px){main{margin:0;padding:20px;border-radius:0}h1{font-size:26px}table{display:block;overflow:auto}td,th{min-width:110px}}@media print{body{background:white}main{margin:0;padding:0}.cards,.downloads,nav{display:none}a{color:black}h2{break-after:avoid}tr{break-inside:avoid}}'''
 lab=markdown.markdown(read(out/'实验室验收手册.md'),extensions=['tables','fenced_code','toc'])
 write(out/'实验室验收手册.html',f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声芯 · 实验室验收手册</title><style>{css}</style><main><a href="验收导航.html">‹ 返回验收导航</a>{lab}</main></html>')
 cards=''.join(f'<figure><img src="previews/{html.escape(p.name)}" alt="{html.escape(p.stem)}"><figcaption>实际Compose渲染 · 页面测试样张</figcaption></figure>'for p in sorted((out/'previews').glob('*ToolsSnapshotsTest*.png')))
 body=markdown.markdown(summary,extensions=['tables','fenced_code'])
 write(out/'验收导航.html',f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声芯乐动 · 验收导航</title><style>{css}</style><main><span class="badge">App0.22 / A623</span><span class="badge">软件验证与现场实测分开</span><h1>声芯乐动：准备进入实验室</h1><nav class="downloads"><a href="声芯乐动_0.22_验收版.apk">安装APK</a> · <a href="声芯乐动_A623_完整音响版.fs">完整音响固件FS</a> · <a href="配套源码.zip">配套源码</a> · <a href="实验室验收手册.html">实验室完整手册</a> · <a href="硬件实测记录.csv">空白实测表</a> · <a href="manifest.json">构建与验证清单</a></nav>{body}<h2>先看真实数字证据</h2><p>下面均为仿真/软件验证结果，现场需要另采实板数据。</p><img src="previews/32声部_仿真频谱.png" alt="32声部RTL I2S频谱"><audio controls src="32声部_I2S仿真试听.wav"></audio><p>约0.34秒真实RTL I2S解码片段，32半音密集簇，仅用于检测，不作为音乐音色试听。</p><img src="previews/16工况_数字延迟仿真.png" alt="16工况数字延迟仿真"><h2>App新增工具页面</h2><p>图形使用真实RTL分析向量；示例设备状态仅存在于测试夹具中，不进入APK数据源。</p><div class="cards">{cards}</div><h2>实验室重点</h2><p>借四通道示波器、10X探头和逻辑分析仪。CH1测压力分压中点；数字方案另三路测MAX模块BCLK/LRCLK/DIN。功放方案用差分探头，或两路对公共地测OUT+、OUT−后相减。SPK−不是公共地。</p><p><a href="实验室验收手册.html">按顺序打开完整手册 →</a></p><footer>本包没有执行硬件烧录；先SRAM，验收通过再Flash。物理测试结果和第三方模型准确率不由截图或RTL仿真替代。</footer></main></html>''')

if __name__=='__main__':package()
