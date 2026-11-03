from pathlib import Path
import json,re,zipfile,subprocess,os,xml.etree.ElementTree as ET,wave,math,struct
R=Path(__file__).resolve().parents[1];B=R/'build/natural_seven_20261101';O=R/'output/natural_seven_20261101'
m=json.loads((O/'release.json').read_text(encoding='utf8'));portable=B/'portable_check';portable.mkdir(exist_ok=True)
with zipfile.ZipFile(O/'七自然音_完整FPGA工程.zip')as archive:archive.extractall(portable)
files=[portable/n.get('path')for n in ET.parse(portable/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File')if n.get('type')=='file.verilog']
assert all(p.is_file()for p in files)
references=0
for file in list(portable.rglob('*.v'))+list(portable.rglob('*.vh')):
    for literal in re.findall(r'"(src/[^"\n]+)"',file.read_text(encoding='utf8')):
        assert (portable/literal).is_file(),literal;references+=1
os.environ['TEMP']=os.environ['TMP']=str(R/'tmp')
check=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012','-E','-o',str(B/'portable_preprocessed.v'),*map(str,files)],cwd=portable,capture_output=True,text=True)
assert check.returncode==0,check.stderr
evidence={'verilog_sources':len(files),'relative_references_checked':references,'relative_assets_exist':True,
    'portable_preprocessor_passed':True,'full_vendor_build':'frozen inputs separately passed complete Gowin synthesis and PNR',
    'note':'Icarus whole-board elaboration cannot substitute for the vendor clock/IO primitive build.'}
(O/'验收证据/portable_source_check.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
audio=[];rate=16000
for midi in [60,62,64,65,67,69,71]:
    for i in range(5600):
        env=max(0,min(1,i/160,(5599-i)/240));audio.append(round(7000*env*math.sin(2*math.pi*440*2**((midi-69)/12)*i/rate)))
    audio.extend([0]*1280)
with wave.open(str(O/'C调七自然音_音高示意_非实机音色.wav'),'wb')as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(struct.pack('<'+'h'*len(audio),*audio))
text=f'''# 七自然音配套版本

程序修改、仿真、完整布局布线及APK构建已完成。本次未烧录SRAM或Flash，真机听感与手机蓝牙联动仍待实际验收。

## 演奏规则

- 实体七片和APP默认七键对应当前大调的1—7；音区按八度切换。默认C调、音区3，即C4、D4、E4、F4、G4、A4、B4。
- C调五个音区：C2—B2、C3—B3、C4—B4、C5—B5、C6—B6。K1降低八度，K2提高八度，其他按键/灯环分工保留。
- APP演奏设置可选12个大调；“完整十二音”一屏显示七个白键、五个黑键，最多七个手机同时持音。32个独立合成声部与释放尾音保留。
- 指引自动选择音区；遇临时升降音，按亮起的键就会发出准确目标音。手机黑白键按准确音高判定。
- 歌曲播放及指引采用该曲配置，结束恢复手动配置；OLED普通页显示例如“C调3 音量16 关”，保留歌词、力度与识别进度。

## 配套文件

- 固件：声芯乐动_七自然音_完整版_20261101.fs，UserCode {m['user_code']}。完整音响外放版，引脚约束与已安装EAE0一致。
- APK：声芯乐动_0.16_七自然音_双识别离线版.apk，版本号16，与0.15同签名，可覆盖安装。两种识别仍使用内置算法/模型，没有INTERNET权限，无需API或环境配置。
- 新APK须配套本固件。旧固件会显示升级提示并禁用演奏/传谱，防止音高误读；手机离线识别、编辑和试听仍可使用。
- 每调手动七键覆盖35个自然音；底层精确音域为C2—B7，共72个半音。识别/导谱保留原始升降音，只在超出整段音域时建议整体移调。
- 原保存旋律以MIDI存储，重新传入使用新格式；FPGA兼容旧曲谱格式。两首内置歌曲的原始音高、时值及歌词时钟保留。
- 网页源代码已同步自然音与八度映射，未发布到线上网站。
- 本次调整映射与联动，不表示识别算法已经达到95%或99%的音乐准确率验收。未验收E2B1音色/7号力度候选独立保留，本版沿用EAE0参数。

## 检查结果

- RTL：{m['rtl_checks']}项通过。覆盖12调×5音区×7自然音、72音高、32768组编码/变调、32声部225/256拍完成、399个内置指引目标、新旧各222项事务、实际Kotlin传谱、五键/灯环/OLED、FPGA识谱及13980个I2S输出字。
- Android：{m['android']['tests']-m['android']['skipped']}项通过、{m['android']['skipped']}项跳过，零失败；APK构建及lint通过，实际Compose渲染已检查。
- 网页：37项测试、TypeScript检查通过；lint无错误，保留3项警告。
- 完整Gowin布局布线：Logic {m['resources']['Logic']}，BSRAM {m['resources']['BSRAM']}，DSP {m['resources']['DSP']}。音频时钟要求12.288MHz，报告Fmax {m['actual_fmax_mhz']}MHz。工具结果不等同于真机延迟测量。
- 原35个DDS频率和630组音色参数逐项一致，物理引脚约束逐字节一致；没有下载操作。

## 复现及证据

解压“七自然音_完整FPGA工程.zip”，使用Gowin V1.9.11.03 Education打开工程，或在解压目录执行gw_sh build.tcl。工程采用相对资源路径，包含FPGA模型、音色、曲谱和歌词ROM。

工作区可运行python scripts/check_natural_seven.py及python scripts/prepare_natural_seven_20261101.py --build；APP位于app/android，使用现有JDK17/SDK执行Gradle testDebugUnitTest assembleDebug lintDebug。

“验收证据”保留仿真、时序及构建清单。“界面预览”是实际Compose渲染，并非手机实拍。“C调七自然音_音高示意_非实机音色.wav”采用正弦波，仅核对音高关系，不代表FPGA实机音色。
'''
(O/'使用说明.md').write_text(text,encoding='utf8')
print(json.dumps({'user_code':m['user_code'],'fmax_mhz':m['actual_fmax_mhz'],'resources':m['resources'],'portable':evidence},ensure_ascii=False))
