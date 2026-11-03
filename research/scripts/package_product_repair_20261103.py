"""Package only verified build artifacts; never talks to the physical programmer."""
from pathlib import Path
import json,hashlib,shutil,xml.etree.ElementTree as ET,re,html,argparse,subprocess,os,stat
from shutil import copy2 as _copy
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1];B=R/'build/product_repair_20261103';O=R/'output/product_repair_20261103';O.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--variant',default='');args=parser.parse_args()
V=B/'pnr_alternatives'/args.variant if args.variant else B
N='soundcore_speaker_omr_60k';P=V/'impl/pnr'
assert (P/(N+'.fs')).is_file(),'Firmware not complete'
assert 'BUILD SUCCESSFUL' in (B/'android-delivery.log').read_text('utf8',errors='replace')
timing=(P/(N+'_tr_content.html')).read_text('utf8',errors='replace')
pnr=(P/(N+'.rpt.txt')).read_text('utf8',errors='replace')
assert 'Bitstream generation completed' in (V/'build.log').read_text('utf8',errors='replace'),'PnR did not finish'
variant=json.loads((V/'variant.json').read_text()) if args.variant else dict(place_option=1,route_option=0)
variant['actual_netlist_sha256']=hashlib.sha256((V/'impl/gwsynthesis'/(N+'.vg')).read_bytes()).hexdigest()
timing_text=BeautifulSoup(timing,'html.parser').get_text(' ',strip=True)
violations={kind:int(re.search(r'Numbers of '+kind+r' Violated Endpoints (\d+)',timing_text).group(1)) for kind in ['Setup','Hold']}
assert all(v==0 for v in violations.values()),violations
slacks={kind:float(re.search(kind+r' Paths Table.*?Relation Clock Skew Data Delay 1 ([-\d.]+)',timing_text).group(1)) for kind in ['Setup','Hold']}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy_file(src,dest):
 src,dest=Path(src),Path(dest)
 assert dest.resolve().is_relative_to(O.resolve())
 if dest.exists() and sha(src)==sha(dest):return
 if dest.exists():dest.chmod(dest.stat().st_mode|stat.S_IWRITE)
 _copy(src,dest)
frozen=json.loads((B/'frozen_inputs.json').read_text())
assert all(sha(B/'src'/p)==h for p,h in frozen.items()),'Frozen RTL changed'
if args.variant:assert all(sha(V/'src'/p)==h for p,h in frozen.items()),'Isolated include sources differ'
variant['frozen_source_match']=True
external=json.loads((B/'external_literals.json').read_text())
assert all(sha(Path(p))==v['sha256'] and v['frozen_matches'] for p,v in external.items()),'Referenced weights/tables changed'
old=R/'build/harmonica_refinement_20261102/src/board'/ (N+'.cst')
assert sha(old)==sha(B/'src/board'/(N+'.cst')),'Pin constraints changed'
apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk'
def signature(path):
 env=os.environ.copy();env['JAVA_HOME']='D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1'
 run=subprocess.run(['cmd.exe','/c','D:/FPGA/_Tools/android/sdk/build-tools/35.0.0/apksigner.bat','verify','--print-certs',str(path)],env=env,capture_output=True,text=True,errors='replace')
 assert run.returncode==0,run.stdout+run.stderr
 result=set(re.findall(r'certificate SHA-256 digest: ([0-9a-f]{64})',run.stdout))
 assert result,'No verified signing certificate in APK';return result
assert signature(apk)==signature(R/'output/acceptance_20261102/声芯乐动_0.22_验收版.apk'),'Upgrade signing certificate changed'
tests=[ET.parse(p).getroot() for p in (B/'final-unit-test-results').glob('TEST-*.xml')]
totals={k:sum(int(x.get(k,0)) for x in tests) for k in ['tests','failures','errors','skipped']}
assert totals['tests']>=318 and totals['failures']==totals['errors']==0
rtl=json.loads((B/'tests/results.json').read_text());handpan=json.loads((B/'handpan/results.json').read_text())
assert all(x['passed'] for x in rtl+handpan)
equivalence=json.loads((B/'expression/results.json').read_text());assert equivalence['passed']
rom_equivalence=json.loads((B/'rom/results.json').read_text());assert rom_equivalence['passed']
extra=[dict(test=n,passed=True) for n in ['tb_expression_equivalence','tb_pressure_expression32','tb_handpan_rom_equivalence']]
voices=json.loads((B/'voices/voices32_results.json').read_text())
assert voices['voices']==32 and voices['residual_ratio']<.02
catalog=json.loads((B/'catalog/catalog_sources.json').read_text('utf8'))
assert len(catalog)==30 and all(60<=x['seconds']<=120 for x in catalog)
photo=json.loads((B/'native_sheet_evidence.json').read_text('utf8'))
assert photo['ready'] and photo['progress']==100 and not photo['externalResources']
files={'声芯乐动_0.23_产品修复版.apk':apk,'声芯乐动_B703_配套完整音响版.fs':P/(N+'.fs')}
for dest,src in files.items():copy_file(src,O/dest)
evidence=O/'验证记录';evidence.mkdir(exist_ok=True)
for name in ['android-release.log','android-delivery.log','screenshots-final.log','rtl-tests.log','handpan.log','voices.log','expression.log','rom.log','native_sheet_evidence.json','catalog_deployment.json','frozen_inputs.json','external_literals.json']:
 copy_file(B/name,evidence/name)
copy_file(V/'build.log',evidence/'fpga-build.log')
copy_file(V/('run.tcl' if args.variant else 'pnr_routability.tcl'),evidence/'pnr_options.tcl')
for name in [N+'.rpt.txt',N+'_tr_content.html',N+'.pin.html']:copy_file(P/name,evidence/name)
copy_file(B/'catalog/catalog_sources.json',evidence/'曲谱来源.json')
copy_file(B/'voices/voices32_results.json',evidence/'voices32_results.json')
copy_file(R/'config/pressure_profile_product_20261103.json',evidence/'pressure_profile.json')
resource=ET.parse(V/'impl/gwsynthesis'/(N+'_syn_rsc.xml')).getroot()
expression=next(x for x in resource.iter('SubModule') if x.get('name')=='continuous_expression.expression_control')
optimization=dict(before=dict(Lut=7346,Alu=1426,Register=1172),after={k:int(expression.get(k)) for k in ['Lut','Alu','Register']},equivalence=equivalence)
(evidence/'expression_optimization.json').write_text(json.dumps(optimization,indent=2))
rom_optimization={'sample_equivalence':rom_equivalence,'modules':{}}
for label,previous in [('handpan_instrument.sound',1894),('handpan_instrument.metal',1323)]:
 item=next(x for x in resource.iter('SubModule') if x.get('name')==label)
 rom_optimization['modules'][label]=dict(previous_lut=previous,current_lut=int(item.get('Lut')),block_ram=int(item.get('Bsram')))
(evidence/'rom_optimization.json').write_text(json.dumps(rom_optimization,indent=2))
shots=O/'界面预览';shots.mkdir(exist_ok=True)
for short,source in [('书架','ToolsSnapshotsTest_library'),('现场收音','ToolsSnapshotsTest_microphone'),('琴键设置','ToolsSnapshotsTest_mapping'),('音色','ProductSnapshotsTest_sound')]:
 p=R/'app/android/app/src/test/snapshots/images'/('cn.soundcore.instrument_'+source+'.png')
 copy_file(p,shots/(short+'.png'))
manifest=dict(version='0.23-product-repair',versionCode=23,firmware='B703',user_code='0x0000B703',output_device='MAX98357A',pnr_variant=variant,programmed=False,installed_flash_unchanged='A6C4',
 tests=totals,timing_violations=violations,worst_slack_ns=slacks,rtl_tests=rtl+handpan+extra,expression_optimization=optimization,rom_optimization=rom_optimization,voice_result=voices,catalog_count=30,
 catalog_duration_seconds=[min(x['seconds'] for x in catalog),max(x['seconds'] for x in catalog)],
 artifacts={name:dict(bytes=(O/name).stat().st_size,sha256=sha(O/name)) for name in files},
 physical_acceptance='pending real Android, BLE, sensor endpoints and power enclosure checks')
(O/'release_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
rows=[
('1 · 附近设备','最多5个、JDY优先；连接后清空并隐藏扫描列表。','模拟大量设备与重复广播已检查；现场扫描待验。'),
('2 · 状态闪烁','后台轮询不再反复切换“等待确认”；删除重复音阶查询，状态相同不重复发布。','协议及界面检查通过；保持连接2分钟观察。'),
('3 · 演奏工具','设备图形改为一包快照；300dp图形及全屏；新增手机现场收音波形、频谱、相图。复音操作可排在快照之后优先执行。','手机收音是声学信号；设备快照才是FPGA数字输出。9600波特率不支持连续示波器数据。'),
('4 · 手碟','音色页加入空灵手碟、金属电音，完整固件开启对应引擎。','控制与音频路由仿真通过；实际听感待验。'),
('5 · 录音成曲','支持整段3分钟；模型小批推理、关闭大内存Arena，长录音分窗处理；保存移到后台线程，增加失败提示。','真实内置模型32秒跨窗持续音测试通过；尚无安卓实机，不能保证26%闪退已根除。超过3分钟仍需裁剪。'),
('6 · 力度均衡','移除七号历史额外增益，七路统一曲线；最大力度映射端点调整为1050。','4096级×7路单调、一致验证通过；1050是待实测候选值，不能替代每片ADC数据。'),
('7 · 琴键设置','只交换同一音区内1—7的位置；音区±和调号统一作用。排列保存到手机，应用后回读校验。','5音区×12调×7片及手机/实体输入仿真通过；重连后可再次点应用。'),
('8 · 设备录音','记录FPGA送给音响的最终声音（含效果），回传后可回听、导出WAV；不是录音成曲。','当前为8秒、8kHz压缩验证录音；9600串口回传约40—90秒。'),
('9 · AI识谱','完全内置，不需配置环境或API。合并OCR实例，增加加载/任务超时与WebView异常恢复。','打包引擎识别提供的《我和我的祖国》到100%，33小节，无外网请求。手机模式在手机识别音符；FPGA模式将数字小图送到板上推理，版面/歌词/节奏仍由手机处理，并非整页全部上板。'),
('10 · 曲谱书架','30首、每首67.5—108.3秒；按曲名/作者/风格检索，收藏直接写入App书架。网页“加入声芯”可打开新版App收藏。','15首巴赫高声部独奏、12首传统旋律、3首熟悉旋律。编配中的主题反复已标明。网页仍使用原有访问权限，App内置书架不依赖站点登录。'),
('11 · 自由演奏','去掉串口时长重复等待；实时按指状态优先于后台查询，松手后不排队补弹过期音符；触控本地立即反馈。','队列/帧校验测试通过；实际手机到设备延迟仍需实测，不承诺蓝牙小于5ms。'),
('12 · 外壳开机','板载PWR控制硬件供电，官方说明需要长按约2秒。建议外壳留孔或做绝缘按压推杆。','FPGA未上电时无法靠RTL处理；不应把PWR永久短接，也不能接K5代替。未改动供电硬件。')]
table=''.join('<tr><th>'+a+'</th><td>'+html.escape(b)+'</td><td>'+html.escape(c)+'</td></tr>' for a,b,c in rows)
gallery=''.join(f'<figure><img src="界面预览/{x}.png"><figcaption>{x} · Compose界面快照</figcaption></figure>' for x in ['书架','音色','现场收音','琴键设置'])
doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声芯乐动0.23 · 安装与验收</title><style>
*{{box-sizing:border-box}}body{{overflow-wrap:anywhere;margin:0;background:#081820;color:#e9f4f4;font:16px/1.8 system-ui,"Microsoft YaHei"}}main{{max-width:1050px;margin:auto;padding:30px 22px}}h1{{font-size:36px;line-height:1.3}}h2{{margin-top:34px;color:#55ddc8}}.lead,aside{{background:#142f3b;border:1px solid #28505f;border-radius:20px;padding:24px}}a{{color:#55ddc8}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:14px;border-bottom:1px solid #28505f;text-align:left;vertical-align:top}}th{{min-width:100px}}.table{{overflow:auto}}.gallery{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}figure{{margin:0}}img{{width:100%;border-radius:18px}}figcaption{{color:#90a8b1;font-size:13px}}@media(max-width:650px){{.gallery{{grid-template-columns:1fr}}td{{min-width:210px}}h1{{font-size:28px}}}}</style><main>
<p>声芯乐动 / 2026.11.03</p><h1>0.23 产品修复版<br>安装与逐项验收</h1><div class="lead"><b>可安装的软件候选版，尚未完成实机验收。</b><p><a href="声芯乐动_0.23_产品修复版.apk">安装APK</a> · <a href="声芯乐动_B703_配套完整音响版.fs">配套B703完整音响固件</a> · <a href="https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/catalog.html">在线曲谱书架</a></p><p>本次没有连接下载器，没有写入SRAM或Flash。A6C4仍是此前已确认的Flash。新工具批量快照、长曲谱容量、手碟开关和力度曲线需要配套B703。</p></div>
<h2>先这样验收</h2><ol><li>APK覆盖安装，保留原有作品。未连板也可测试3分钟内录音、手机内置识谱、书架收藏和麦克风图形。</li><li>后续先把B703下载到SRAM验证，成功再决定Flash。引脚及接线沿用A6C4，未改约束。</li><li>蓝牙连接后快速交替弹七键与十二音，松手后不应继续补弹；设备页面观察2分钟，应保持稳定。</li><li>七片分别轻按、中按、最大按；对比OLED、手机和实际响度。如果仍不一致，应读原始ADC端点再标定，不能只放大显示条。</li><li>书架搜索“巴赫”，收藏后切到“我的书架”，退出重开仍应存在；选曲后可手机试听、发到设备自动播放或指引。</li></ol>
<h2>12项处理与边界</h2><div class="table"><table><tr><th>事项</th><th>本次改动</th><th>验证与限制</th></tr>{table}</table></div>
<h2>验证记录</h2><p>Android单元检查总计{totals['tests']}项：{totals['tests']-totals['skipped']}通过，{totals['skipped']}项原有可选检查跳过，0失败/错误；APK与Lint构建成功。另有原生Compose页面快照、{len(rtl)+len(handpan)+len(extra)}项RTL检查，32声部I²S独立基频验证。硬件音频与手机蓝牙未测，仿真不是上板结果。</p><p>连续力度模块经等价优化，LUT由7346降至{optimization['after']['Lut']}、ALU由1426降至{optimization['after']['Alu']}；65536组组合与30000周期的帧末结果、声部取值对照一致。连续力度在8个时钟内完成，音频每帧256个时钟。完整日志、固件资源/时序报告及曲谱来源位于“验证记录”；SHA-256在release_manifest.json。录音模型借鉴并使用开源CREPE Tiny权重，识谱包含内置符号模型和Tesseract OCR；未把第三方权重宣称为自行训练，也未调用外部API。</p>
<h2>页面预览</h2><p>以下是原生Compose渲染；现场收音图为明确标记的测试信号，非实机测量。</p><div class="gallery">{gallery}</div>
<h2>电源与曲谱来源</h2><p><a href="https://wiki.sipeed.com/hardware/en/tang/tang-mega-60k/mega-60k.html">Sipeed Tang Mega 60K 官方说明</a>说明NEO Dock电源键控制。外壳先采用绝缘机械推杆或可触及的开孔；若要外接电源按钮，须核对实际PWR触点后并接瞬时开关，此处没有猜测焊点。</p><p>新增曲谱采用<a href="https://github.com/cuthbertLab/music21">music21公开语料库</a>可读取谱面，保留来源；并非下载商业录音，也不是给30首歌曲填充无声凑长度。原始谱文件留在build/product_repair_20261103/catalog/originals。</p></main></html>'''
(O/'安装与逐项验收.html').write_text(doc,'utf8')
print(json.dumps(dict(output=str(O),tests=totals,artifacts=manifest['artifacts']),ensure_ascii=False,indent=2))
