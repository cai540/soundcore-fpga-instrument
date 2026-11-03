"""Build a source-linked requirement ledger and a practical laboratory handbook.
Digital evidence and blank physical data forms are kept separate.
"""
from pathlib import Path
import csv,hashlib,html,json,shutil,math
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether,Image
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

R=Path(__file__).resolve().parents[1];B=R/'build/contest_audit_20261103';O=R/'output/contest_lab_20261103'
O.mkdir(parents=True,exist_ok=True);(O/'数据表').mkdir(exist_ok=True);(O/'界面预览').mkdir(exist_ok=True)
OFFICIAL='https://www.gowinsemi.com.cn/university/match2026'
ADI='https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf'
TEK='https://www.tek.com/en/documents/whitepaper/abcs-probes-primer'
items=[]
def req(id,wording,function,source,lab,status='代码已实现；实物待测'):
 items.append(dict(id=id,requirement=wording,implementation=function,source=source,lab=lab,status=status))
req('D1','自研交互；至少2个独立可控演奏维度','七片压力选音/力度＋滑杆音高＋EC11颤音深度；五键控制产品状态','rtl/fsr_strike_detector.v; rtl/ec11_control.v; rtl/vibrato_bend.v','L04')
req('D2','FPGA硬件逐样本、逐声部计算；I²S到DAC','12.288MHz流水调度，32份独立状态，48kHz标准I²S至MAX98357A','rtl/poly_synth32_tm.v; rtl/i2s_stereo_tx.v; board/pressure_i2s_additive32_core.v','L02,L03')
req('D3','并行/流水优势；多音色、多表情、低延迟纯硬件','共享算术但相位/频率/包络不共享；ADC直达合成链路不经过手机','rtl/playable_synth32.v; rtl/pressure_expression32.v','L03,L05,L06')
req('B1.1','自主交互与准确动作采集','七路分压、ADC扫描、独立基线/门限/峰值/重触发；滑杆第八路','rtl/mcp3208_scan.v; rtl/fsr_strike_detector.v','L01,L04')
req('B1.2','至少2个独立维度；灵敏稳定、适配演奏','固定选音时改压力；固定压力时改滑音，再独立改颤音深度','rtl/pressure_expression32.v; rtl/vibrato_bend.v','L04,L11')
req('B2.1','完整音频生成链路全部HDL；逐样本运算','事件→分配器→相位/音色/ADSR→混音/效果→I²S；手机只发事件','rtl/strike_voice_allocator32.v; rtl/poly_synth32_tm.v; rtl/audio_effects_product.v','L02,L03,L12')
req('B2.2','控制到音频输出总延迟≤10ms','早触发、按声部服务、固定音频帧；实际功放输出仍须测量','scripts/preflight_latency_20261101.py','L05,L06','数字预检通过；总延迟未实测')
req('B2.3','杜绝软件串行运算滞后','实体演奏不经过Android；App最新按键状态邮箱，无历史音符FIFO','app/android/app/src/main/java/cn/soundcore/instrument/RealtimeNotes.kt','L05,L10')
req('B3.1','基础复音≥4；四路独立声部同时发声','同一产品引擎可测试4/8/16/32声部，不是用4条旋律数量替代声部','rtl/poly_synth32_tm.v; rtl/product_tools_engine.v','L03')
req('B3.2','所有音频按实时演奏事件逐音逐样本生成','内置曲目/上传曲谱都是音符事件；不是歌曲PCM播放器','rtl/song_event_player.v; rtl/uploaded_song_engine.v','L08,L12')
req('B3.3','支持单音实时变调','独立声部可重设频率；滑杆对现场演奏连续弯音','rtl/playable_synth32.v; rtl/product_tools_engine.v','L03,L04')
req('B3.4','ADSR包络调控','本轮补足真实Decay；保留既有柔和Attack，随后缓降5%至Sustain，松手Release；四参数自由编辑不在当前UI内','rtl/poly_synth32_tm.v; rtl/synth_voice.v; tb/tb_product_adsr.v','L07','补齐D阶段，数字回归；实物待测')
req('B3.5','多声部实时混音','32个输出逐帧累加、限幅；每帧必须按时完成','rtl/poly_synth32_tm.v; board/pressure_i2s_additive32_core.v','L03,L11')
req('B3.6','禁止预录PCM、预置音频推流、整段录音触发','模型识别后上传音符，再由FPGA合成；设备录音仅旁路采集/回传，不送回合成输入','rtl/audio_record_adpcm.v; rtl/uploaded_song_engine.v','L09,L12')
req('E1.1','复音≥32，或单音加法分量≥32，或多条物理建模','采用32独立声部这一条达标路径；三个分支是“或”，不要求全部重复实现','rtl/poly_synth32_tm.v; rtl/strike_voice_allocator32.v','L03')
req('E1.2','发挥并行优势、提高振荡器吞吐量','相位/包络独立，共享流水运算；32×实测Fs。不能把一个查表声部的谐波重复算声部','rtl/poly_synth32_tm.v; rtl/playable_synth32.v','L02,L03,L12')
req('E2.1','≥3维表情；力度、滑音、颤音等','力度控制幅值/表达，滑杆控制平均音高，EC11编辑颤音深度；分别固定其他两项验证','rtl/pressure_expression32.v; rtl/vibrato_bend.v; rtl/front_panel_product.v','L04')
req('E2.2','≥2种乐器音色自由切换','口琴、二胡；空灵/金属手碟作为额外音色，不用命名替代听音验证','rtl/expressive_texture.v; rtl/handpan_modal32.v; rtl/rock_voice_fx.v','L07')
req('E2.3','FPGA内部混响、延迟、合唱等效果','三条硬件效果通路与平滑混合，比较干声/回声/合唱/混响','rtl/audio_effects_product.v','L07')
req('E3.1','演奏延迟≤5ms','70组强阶跃数字预检；另外测试弱力度。模拟功放、真实传感器部分不计为已过','scripts/preflight_latency_20261101.py','L05,L06','数字预检；≤5ms总输出尚未实测')
req('E3.2','确定性无抖动延迟','固定256时钟/采样，状态按截止时间服务；还须测输入相位造成的界限与max−min，不能宣称异步敲击绝对零抖动','rtl/i2s_stereo_tx.v; rtl/pressure_expression32.v','L02,L05,L11','固定时序设计；严格无抖动尚未实测')
req('E3.3','FPGA逻辑生成LED演奏指引','原有指引下一目标；本轮补无需手机自动进入指引灯与非阻塞时值提示','rtl/guide_rhythm_cue.v; board/pressure_i2s_panel_oled_ble_experiment_top.v','L08','新增节奏提示，候选待上板')
req('E3.4','FPGA逻辑生成李萨如图形','单声道与延迟64个采样的信号作XY投影，在FPGA生成；不冒称独立双通道相位计','rtl/product_audio_analyzer.v; rtl/oled_analysis_columns.v','L08')
req('E3.5','FPGA实时频谱','1024点硬件FFT、32个对数频带，OLED本地绘制；32声部证明另用长窗外部FFT','rtl/product_audio_analyzer.v','L03,L08')
req('E3.6','FPGA实时波形','最终PCM旁路的极值波形；手机FPGA快照与手机麦克风数据明确区分','rtl/product_audio_analyzer.v; app/android/app/src/main/java/cn/soundcore/instrument/ScopeWorkbench.kt','L08,L10')
req('E4.1','脱机LED曲目指引，辅助节奏','两首内置曲目、目标自动切音区、正确敲即前进；节奏灯不锁按键，长音/休止时值用于下一击提示','rtl/song_guide_long.v; rtl/guide_rhythm_cue.v','L08')
req('E4.2','可选蓝牙与手机App联动','JDY优先、最多5设备；控制/状态协议与最新按键状态；不把蓝牙宣称为≤5ms通路','app/android/app/src/main/java/cn/soundcore/instrument/BleController.kt','L10')
req('E4.3','在线曲谱下载','App曲谱书架30首公开来源的旋律编配，搜索/收藏后出现在App内并可离线用；不是只下到Downloads','app/android/app/src/main/java/cn/soundcore/instrument/OnlineScores.kt; app/android/app/src/main/assets/scores','L09')
req('E4.4','演奏键位自定义','同音区1—7排列；全体共同跟随调号、音区；指引目标优先','rtl/product_tools_engine.v; app/android/app/src/main/java/cn/soundcore/instrument/ProductToolsController.kt','L09')
req('E4.5','演奏录音回传','设备最终PCM→抗混叠降采样→8kHz IMA ADPCM，最多8秒，带偏移/CRC回传WAV','rtl/audio_record_adpcm.v; app/android/app/src/main/java/cn/soundcore/instrument/ProductTools.kt','L09')
req('C1','独立单元须有相位累加器、频率、包络控制','phase[0:31]、phase_step每声部32位、envelope/state/gate_last每声部独立；一个查表振荡器按1个计','rtl/poly_synth32_tm.v','L03,L12')
req('C2','活跃可闻独立振荡器数×实际输出采样率；过采样不加分','现场测LRCLK并听见/检出32音；若32与48k均证实，则1,536,000声部采样/秒。音量0即使计数32也不算可闻','rtl/product_tools_engine.v; rtl/poly_synth32_tm.v; rtl/i2s_stereo_tx.v','L02,L03','数字仿真有证据；现场三条件待测')
req('C3','测试多频音、对应数量独立谱峰、RTL证明无预录','同一引擎诊断正弦MIDI60—91；单独关声部32和移动声部1频率；保存实板PCM/FFT/代码追溯','tb/tb_tools_voices_i2s.v; scripts/lab_pcm_check.py','L03,L12')
req('BOARD','限定适配Sipeed Tang系列列明板卡','当前Tang Mega60K属于官方列出的板卡；现场拍铭牌确认具体型号','board/soundcore_melody_top.v','L01')

sections=[]
def sec(title,*text):sections.append(dict(title=title,paragraphs=list(text)))
sec('先看：明天必须带回什么',
 '本手册对照高云2026原厂页面“选题二”，逐项覆盖设计要求、3条基础、4条拓展和3条核心评分规则。它们没有公布可直接引用的百分制权重；不要自拟评分比例。传感方案和合成算法的列举是备选，不要求把每一种传感器/算法都做一遍。',
 '必须带回：①板卡/版本和供电照片；②真实LRCLK/BCLK测量；③4/8/16/32声部PCM与频谱，另有单声部关断/变调视频；④压力电压到功放差分音频的多次原始波形及最坏延迟/抖动；⑤三维表情、ADSR、两音色三效果；⑥断蓝牙脱机指引及FPGA本地三种图形；⑦下载、键位、录音回传验收记录。',
 '目前只能称“软件/数字链路已检查、候选待实物验收”。≤5ms总延迟、确定性无抖动、真实32声部可闻和手机端实际刷新率不能由电脑仿真替代。新App无需改接线。本轮没有烧录，也不自动写Flash。',
 '官方页面当前标注作品提交截止为2026年11月4日18时，决赛11月20—22日。按明天11月4日安排，建议14时前完成关键数据，余下时间整理/上传；如学校或组委会另有通知，以通知为准。')
sec('本轮已跑过的数字检查，不能替代实测',
 'B713候选完整布局布线已完成：Setup/Hold违规均0，最差裕量约27.285ns/0.065ns；Logic48726/59904，CLS28523/29952，BSRAM114/118，DSP82/118，29个引脚沿用原约束。不是仅综合通过，也没有据此声称实板已经合格。',
 '同一冻结源的两音色×五音区×七片共70组强阶跃：到触发事件最坏0.660ms，到首个非零I²S样本1.299ms，到|PCM|≥64为3.362ms。另70组弱阶跃（基线1000→1320码）：到触发1.083ms、首非零2.940ms、到|PCM|≥8为4.436ms。固定64计数的弱敲测试未在5ms内过关，所以不能把3.362ms扩展宣称为任意力度、任意门限的总延迟。',
 '弱音留下的模拟延迟余量较少，明天优先测最轻可用力度与功放端。门限会影响结论，所有判据都要保留。新ADSR与节奏灯单独测试通过；真实RTL解码的32个独立基频、单独关断/重触发/变调通过，每帧最多225/256时钟；这些仍是数字仿真证据。')
sec('L01｜器材、版本与供电（约10分钟）',
 '向老师借：四通道数字示波器（≥50MHz，≥100MSa/s，能存原始CSV和深存储）、四根已补偿的10X探头及短地线；最好再借合适的差分探头。逻辑分析仪需3.3V兼容、≥25MSa/s、至少3数字通道，支持标准I²S解码及导出PCM。另带万用表、正常稳压电源、下载USB、电脑与手机、耳塞/音量控制、U盘、夹具。',
 '先拍唐Mega板卡铭牌，记录板卡版本、固件UserCode、APK版本、供电来源、仪器型号/采样率/探头倍率。新版候选B713，App0.24；若尚未烧录，不可只凭文件名写成板上已经是B713。SRAM验证合格再决定是否写Flash；本次没有替你下载。',
 '断电固定测试夹后再上电。量模块端的3.3V、功放供电、ADC实际VREF及空载/重负载时最低值，所有模块公共GND连续。功放供电不得超其额定范围；不再使用曾输出11.2V的异常面包板电源。保留正常接线，不以测试名义改换未核对的FPGA引脚。',
 '在“数据表/版本与供电.csv”填写实测值。拍一张总体接线、一张模块端供电读数；不要把稳压器空载电压当成模块带载电压。')
sec('L02｜测采样率与固定时序（约5分钟）',
 '黑色地夹只接公共GND；探头尖端接MAX模块的LRC/LRCLK，10X、DC耦合，起始5µs/div、1V/div，观察周期约20.833µs，频率约48kHz。再测BCLK，起始100ns/div，预期约3.072MHz。示波器频率计平均读取，至少记录10个读数、最小/最大周期和截屏。',
 'I²S格式：标准Philips一位延迟，16位有符号音频，每声道32位时隙，左右数据相同。BCLK/LRCLK应为64。内部12.288MHz不是音频采样率，PLL或内部过采样不能叠加吞吐加分。',
 '判断：先确认没有不规则停钟或漏帧，再用实测LRCLK算吞吐。若Fs不是48kHz，应保留实测值并排查，不可手改记录凑标称。按仪器分辨率记录量化误差；有限分辨率下观察不到抖动不等于抖动绝对为0。')
sec('L03｜证明32个“独立、活跃、可闻”声部（约20分钟）',
 '手机连接→设备→演奏工具→声音示波器→展开“独立声部检测”。先停止所有曲目，音量设16，音效关闭；测试会使用同一个32声部引擎的纯音路径。先4，再8、16、32，每档等0.2秒稳定。活动声部数是设备回报，但回报32本身不是可闻证明。诊断最长60秒，长录制前重新启动；按停止、退出页面/断线等会结束检测。',
 '首选逻辑分析仪：GND接公共地，三根信号分别接MAX模块BCLK、LRC、DIN；阈值约1.65V，≥25MSa/s，解码后导出至少0.5秒、推荐1.4秒的稳定单声道PCM/WAV。若只能导出原始位流，大CSV可能占大量内存，优先让仪器先解码导出PCM；不要把屏幕抽取的1000个点当原始数据。',
 '默认32音是MIDI60—91，从C4到G6的连续半音，最接近的两峰约差15.56Hz。推荐FFT≥65536点/1.365秒，Hann窗，分辨率约0.73Hz；0.5秒可做初验。OLED的32个对数频带不能拿来数32个独立声部。手机精细频谱可辅助观察，但包含房间/麦克风影响。',
 '保存未改调的4/8/16/32各一份原始PCM、仪器截图、FFT图和目标峰表，现场适度音量试听。然后选声部32并关闭，等释放完成应从32降31且G6峰消失；再单独将声部1降低半音，C4峰应移动到B3、其他31峰保持。重新点32可恢复默认测试。全过程录像，证明不是一段固定多频录音。',
 '分析命令：python scripts/lab_pcm_check.py "32声部.wav" --voices 32 --measured-rate 48000 --skip-seconds 0.2 --out "实测/32声部"。把48000替换成你量到的LRCLK；WAV应保留足够稳定时长。结果会给32个预期峰的逐项核对，但仍不会自动替代独立控制和听音证明。',
 '如果是原始CSV列Time,BCLK,LRC,DIN，可用：python scripts/lab_audio_inspect.py i2s "32声部.csv" --bclk 1 --lrclk 2 --din 3 --logic-threshold 0.5 --spectrum-only --voices 32 --out "实测/32声部"。仅在导出0/1逻辑值时用0.5；3.3V波形阈值用1.65。CSV列号从0开始，时间若为ms则加--time-scale 0.001。',
 '评分计算：验证到N个独立可闻活跃单元后，吞吐=N×实测Fs。N=32且Fs=48000时为1,536,000声部采样/秒。不要再乘谐波数量、左右声道、流水阶段数或过采样倍数。任何一峰缺失都保留原数据排查，不删掉失败样本。')
sec('L04｜三维独立表情与七片一致性（约15分钟）',
 '依次测试七片。CH1尖端接该片电阻分压中点，即ADC的AI0—AI6信号端，地夹公共GND；不是压力片接3.3V的固定供电端。每片记录空载、轻、中、重三档电压，力度显示最高值和声音RMS；每档3次，尽量用相同压头、固定载荷/砝码，避免仅凭手感宣称一样用力。',
 '满格应以每片实测可达电压、ADC VREF和相应校准映射核对，而不是把重按电压必须等于3.3V当条件。现有统一端点仍是候选，特别关注过去7号与其余六片差异。若有片明显不到满格，保存该片AI原始电压/ADC码，回去改标定，不用盲目提高全部增益掩盖差异。',
 '维度1力度：选固定音高、关闭音效/颤音、滑杆居中，改变压力；幅度应单调，平均音高不应跳。维度2滑音：保持力度、音色、音量、颤音固定，移动滑杆，记录5个位置的基频和cents=1200log2(f/f0)，应连续。',
 '维度3颤音深度：保持压力和滑杆位置，按机身现有方式进入EC11深度编辑（长按旋钮，普通转动仍是音量），独立改变深度；记录频率随时间摆动的范围和周期，不能把幅度起伏称为颤音。另测普通旋钮音量变化不改中心频率。每种至少保存10秒音频和控制画面。')
sec('L05｜数字链路延迟：先准确定位起点（约15分钟）',
 '四通道接法：CH1=压力分压信号AIx；CH2=MAX的BCLK；CH3=LRC/LRCLK；CH4=DIN。所有地夹都接公共GND。关闭自动播放、诊断声部和音效，只留被测琴片。10X/DC耦合；初始1ms/div或2ms/div，预触发20%—30%，单次触发CH1上升，触发电平设空载电压加0.05V作为一个预先声明的参考。',
 '解码I²S原始波形需≥25MSa/s且记录20—40ms；不能只存显示抽点。保存空载至少1ms的安静段。输入同时报告两种起点：首次明显偏离基线（预先定门限），以及越过固件触发门限。当前ON_THRESHOLD=280码，电压增量=280×实测VREF/4096；不是280×VDD/4096。缓慢按压会延迟达到门限，不能事后把起点往右移来凑5ms。',
 '输出同时报告第一个非零PCM、固定|PCM|≥64，以及噪声/相对稳态门限。弱音的稳态幅值可能使64计数变成很高比例，不等于可听起点。先看预触发噪声，建议主判据为噪声RMS的6倍与稳态幅值10%中的较大者，固定后对整组都使用，附带5%/20%敏感性结果；不能只挑最快一个门限。若没有明显越过噪声，应记为弱音信噪比不足。',
 '命令：python scripts/lab_audio_inspect.py i2s "延迟.csv" --input-step 0.05 --output-step 64 --out "实测/延迟01"。第一种门限和换算后的280码门限各分析一次，保留原CSV。该脚本只计算声明的阈值交点，不会证明人的触觉起点、可听阈值或模拟功放总延迟。',
 '测量矩阵：先固定普通音区，中等力度，对口琴和二胡各30次独立敲击，间隔至少0.5秒并确保前音安静；再对七片×两音色各10次（包含最轻可用力度和重按）；补最低音区、音效全开、OLED/蓝牙繁忙各10次。时间不足先完成两音色30次与七片中等力度，再扩展，不把不足次数写满。',
 '记录最小、p50、p95、最大、标准差与max−min。官方基础≤10ms、拓展≤5ms，本项目留余量目标<5ms。报告所有失败/漏音；计算端固定时序和异步ADC采样相位引起的量化变化分开解释，绝不能只拿平均值合格或把测不到叫绝对零抖动。')
sec('L06｜压力到功放差分音频：决定≤5ms是否真正过关（约15分钟）',
 'MAX98357A是BTL桥接Class-D输出，SPK−/OUT−不是GND。普通示波器的地夹绝不能接SPK−，也不拔仪器保护地。优先请老师用额定合适的差分探头：CH1测AIx，差分探头正/负分别接SPK+和SPK−。',
 '没有差分探头但有四通道时：CH1尖端接AIx；CH2尖端接SPK+；CH3尖端接SPK−；这三根地夹全部接系统公共GND。Math=CH2−CH3，两个输出探头衰减/补偿一致并校零。只有普通两通道时，不用把SPK−当地凑测法；先完成数字链路，借到差分探头或三通道以上再测完整模拟输出。',
 '输出含约数百kHz开关载波，必须看低通后的差分音频。不能用PWM第一跳当起音。采原始数据≥2MSa/s、20—40ms、压力单次上升触发；先用8kHz音频低通或离线滤波，再确定噪声与包络阈值。起始CH1 200mV/div（有偏置则调垂直位置），输出端各2V/div或按实测电源，10X/DC。先确认没有削顶/保护重启。',
 'CSV为Time,AIx,SPK+,SPK−时：python scripts/lab_audio_inspect.py speaker "功放.csv" --input-step 0.05 --output-step 0.02 --out "实测/功放01"。0.02V只是示例，须先依据噪声固定阈值。脚本采用因果511点FIR，报告其群延迟且默认不扣除；若老师采用硬件滤波，也记录滤波器延迟和带宽。不明原因地扣时间不算有效测量。',
 '同样保存30次普通中等力度为主数据，再测最低音区、最弱可用力度、七片及全负载。若数字链路<5ms而功放链路超过，当前不能宣布总延迟达标，应定位功放、包络、门限或传感采样；把完整CSV带回来。声学测量可另用参考麦克风，记录距离并说明空气传播约2.9ms/m，不拿远处手机声音替代电气起音。')
sec('L07｜ADSR、音色与三种硬件效果（约10分钟）',
 'ADSR：固定音/力度，录一次长按≥0.5秒再松开，观察短时RMS包络。新版保留口琴约24ms、二胡约5.33ms的柔和Attack；新增从原峰值缓降5%的Decay（约31/29ms），再保持Sustain，松手Release下降到静音。这是音量包络形状，峰值或Attack完成时间不是“起音延迟”。四个阶段应在代码和包络图都能指出，当前不宣称App可任意编辑四参数。',
 '至少口琴和二胡各录同一音符、同一力度/滑杆/音量10秒，保留频谱与试听；空灵、金属手碟额外各录一份。不能只显示两个音色名称就算完成。',
 '同一演奏分别保存干声、只回声、只合唱、只混响，以及三者同时打开各10秒。回声看重复/延迟间隔；合唱看缓慢延迟调制和频谱展宽，单声道仍能听到变化；混响看结束后的衰减尾巴。记录RMS/峰值/是否削顶、是否切换爆音。不要求三效果峰值绝对相同，但不能开效果就巨大突增或保护掉音。')
sec('L08｜真正脱机与FPGA实时视觉（约10分钟）',
 '断开手机蓝牙或关闭手机。机身短按K4进入曲目；长按K4约0.7秒到模式选择，K1选择“我来弹”、K2选择“听示范”，K5确认。K1/K2选曲，K5开始/暂停/继续，K4退出；以OLED当前菜单提示为准。内置《我和我的祖国》《敕勒歌》不需要网络。',
 '新版进入本地指引会自动切到指引灯，退出恢复原灯模式；手机在指引期间主动改为跟随时仍尊重该选择。正确敲后下一灯立即可见：上一歌词时值内较暗、临近下一击闪动、到时亮，长转音/休止计入建议间隔；不锁住按键，不要求额外敲击。保存正确/错误/重复同音、自动换音区、暂停/继续/完成的视频。未使用新版固件时不要把这一新增行为写成已验收。',
 '连接手机后选“FPGA输出”源，依次波形/频谱/XY，观察OLED本地同步图形。声音改变时FPGA图形必须改变，停止后不得一直重复旧动画。FPGA频谱32个带用于直观反馈，波形是32组极值；XY是x(t)与延迟64采样的x(t)，可展示1:1李萨如/延迟投影，不能宣称测量独立双通道相位。',
 '再用手机“麦克风实时”观察同一声响，明确这条是手机自己采集，不是FPGA分析数据。手机图好看不能替代赛题“基于FPGA硬件逻辑生成”的证据；保留OLED与实际声源同框视频。')
sec('L09｜在线曲谱、键位与设备录音回传（约10分钟）',
 '曲谱书架：联网检索并收藏至少一首未收藏曲谱，回到App书架直接出现；关闭网络、重启App，仍可载入试听，再上传设备演奏/指引。书架30首为公开来源旋律编配/重复段，不宣称每首都是原版全曲。至少核对一首的时长和休止未丢。',
 '琴键设置：交换1与7的位置并应用；同音区仍恰好1—7各一次；音区加减和调号对七键共同生效，手机12音键保持精确半音。返回默认排列后再验指引目标优先。截图保存换位前/后和跨音区结果。',
 '设备录音：开始后弹5—8秒→停止→回传→CRC校验→手机回听/导出WAV，记实际录音时长、传输耗时、重试次数。该功能是把设备最终合成声回传，8kHz压缩录音上限8秒；不是录音成曲的180秒入口，也不是录音PCM回放到FPGA。9600串口下8秒回传约40—90秒是带宽限制，不能用它作为5ms指标。',
 '额外创新不代替基础评分：手机断网分别测试一次录音成曲和一次拍谱识别，确认不调用外部API、结果可试听/上传/指引，并保留失败样本与耗时。识别准确率没有在新素材上量过，不能因为功能入口存在就写95%/99%。')
sec('L10｜新版手机示波器与软件延迟（约10分钟）',
 '安装0.24覆盖原App，设备→演奏工具→声音示波器。先选麦克风实时并授权；将手机放音响旁，降低房间干扰/手机削顶。选择波形→自动量程→调节时基与FS/div→设置上升/下降沿及电平；稳定周期应停住，不再自动把每帧高度归一化。“冻结”保留当前帧，“单次”等待一次完整触发，“导出”输出真实采样/频谱CSV和来源。',
 '横屏全屏可看更多周期；旋转不会主动销毁蓝牙/采集控制器。频谱默认4096点；在调节中启用高分辨率16384点，48kHz下Δf约2.93Hz、窗长341ms；可聚焦200—1800Hz看32纯音。分析窗长和蓝牙延迟不是同一个指标，手机系统收音延迟还受机型影响。',
 'XY默认以主峰1/4周期作延迟投影，或手动调τ；显示的是一个单声道信号与自身延迟信号的轨迹，不是双通道测相。纵轴FS、频谱dBFS均为数字满量程相对值，不是电压或声压级；导出数据带采样率、FFT长度、时间戳可靠性和帧号。',
 '软件优化：采集块由32ms减为10ms、FFT与采集分线程、单个待处理任务、最新帧邮箱、缓存FFT窗/旋转因子；旧图不排队。实际蓝牙演奏已使用零额外音符定时器，保留当前手指状态而非历史按键队列；独立声部控制本轮修复目标竞态，并优先于图形读回。9600波特率下9字节裸串口至少9.375ms、16字节至少16.667ms，尚未算BLE；因此不承诺手机蓝牙≤5ms。',
 '测试快速按/松20次、多指、离开页面、断线、旋转、反复开关麦克风。收手后不应继续排出一串旧音，图表停止后再启动应是当前声音。用另一台手机120/240fps同框拍敲击/波形，统计视觉延迟（约8.3/4.17ms分辨率），不能把它冒充硬件电气5ms测量；记录机型、拍摄帧率和判据。')
sec('L11｜重负载稳定性与抖动（至少10分钟）',
 '32声部＋三效果＋FPGA FFT/OLED＋蓝牙状态/图形读取同时运行，至少10分钟；诊断每60秒自动退出，须主动重新启动或分段记录，不能把退出当崩溃。分别记录音频deadline故障标志、LRCLK连续性、电源最小值、是否重启、CRC重试、手机帧是否积压。然后做正常多键演奏与手机图形并行的连续运行。',
 '切换效果、音区、音色、暂停/继续、手机断连/重连和模式复位都要测。出现滋啦/掉音时同时留电源与I²S证据：先分清电源塌陷/接触不良/功放保护与PCM本身突变，不把硬件噪声一概归咎算法。',
 '确定性证据分三层：RTL固定每256时钟产出一帧；实际I²S不漏帧/不超时；异步传感输入到起音的多次延迟统计。ADC扫描约0.2116ms/轮，输入相位会造成有界采样差异；如果实测存在抖动，诚实写数值，不能写“绝对无抖动”。')
sec('L12｜评审证据与交付顺序（约15分钟）',
 '代码讲解只走这一条链：AIx→mcp3208_scan→fsr_strike_detector→strike_voice_allocator32→playable_synth32/phase_step→poly_synth32_tm独立phase/envelope/state→硬件混音/效果→i2s_stereo_tx→MAX。指出32份独立状态和每帧服务截止时间；复用乘法器不等于共享一个振荡器状态。',
 '曲目ROM存的是音高、时值和歌词索引；波形小查表是振荡器的一部分；设备ADPCM缓存是录音回传的旁路。把这些用途与“预录PCM直接发声”区分清楚，保存顶层连线图与关键RTL片段，别只口头说纯硬件。',
 '推荐现场展示顺序：15秒双维/三维压力演奏→30秒4/8/16/32独立谱峰及关断/变调→30秒实测延迟原波形/统计→20秒两音色三效果→20秒脱机节奏灯/OLED硬件波形FFT/XY→最后再展示录音成曲、AI识谱和App书架。核心评分证据先于UI和额外功能。',
 '统一命名：日期_固件_音色_音区_琴片_力度_试次，例如1104_B713_口琴_音区3_AI0_中_001.csv。原CSV/原WAV不覆盖，分析放旁边子目录，另存仪器截图、版本照片、录屏。数据表中写清输入/输出门限、探头倍率、时标单位与原始文件名。',
 '填写“数据表/延迟试次.csv”后运行：python scripts/lab_latency_summary.py "延迟试次.csv" --out "实测/延迟统计"。脚本拒绝空表/非正延迟/缺来源，不会生成不存在的实测值。它只统计已填数据，不能自动证明独立声部或绝对零抖动。',
 '完成后把原始测量文件与填好的CSV保留下来。优先看最坏延迟、缺失谱峰、七片异常和电源问题，再决定是否发布/写Flash；单次成功或只有截图不能替代重复统计。')

def evidence_paths():
 for row in items:
  row['anchors']=[]
  for file in row['source'].split('; '):
   p=R/file
   if not p.exists():raise FileNotFoundError(file)
   row['anchors'].append(dict(path=file,sha256=hashlib.sha256(p.read_bytes()).hexdigest()if p.is_file()else None))
evidence_paths()
(O/'赛题逐项对照.json').write_text(json.dumps(dict(official_url=OFFICIAL,retrieved_date='2026-11-03',firmware='B713 candidate',app='0.24',items=items),ensure_ascii=False,indent=2),encoding='utf8')
with (O/'赛题逐项对照.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=['id','requirement','implementation','source','lab','status']);w.writeheader();w.writerows({k:r[k]for k in w.fieldnames}for r in items)
forms={
 '版本与供电.csv':['date','board_model','board_revision','usercode','apk_version','instrument','probe_ratio','rail','idle_v','load_min_v','adc_vref_v','source_photo','notes'],
 '延迟试次.csv':['test_id','firmware','timbre','bank','pad','force','trial','latency_ms','input_definition','output_definition','source_csv','notes'],
 '声部与采样率.csv':['test_id','firmware','requested_voices','active_report','audible_verified','lrclk_hz','bclk_hz','independent_peaks','gate_test','retune_test','source_pcm','screenshot','notes'],
 '七片与表情.csv':['pad','timbre','bank','force_load','idle_v','pressed_v','adc_vref_v','meter_level','audio_rms','pitch_hz','bend_position','vibrato_depth','source_file','notes'],
 '功能验收.csv':['test_id','requirement_ids','operation','expected','observed','pass_fail','evidence_file','notes']}
for name,fields in forms.items():
 p=O/'数据表'/name
 if not p.exists():
  with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.writer(f);w.writerow(fields)
snap=R/'app/android/app/src/test/snapshots/images'
for source,target in [('cn.soundcore.instrument_ScopeSnapshotsTest_wave.png','波形.png'),('cn.soundcore.instrument_ScopeSnapshotsTest_fft.png','频谱.png'),('cn.soundcore.instrument_ScopeSnapshotsTest_xy.png','XY.png'),('cn.soundcore.instrument_ScopeLandscapeSnapshotsTest_waveLandscape.png','横屏.png')]:
 if(snap/source).exists():shutil.copy2(snap/source,O/'界面预览'/target)

# These are connection diagrams, not an invented photograph or measurement.
diagram='''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="400" viewBox="0 0 1000 400"><style>text{font-family:Microsoft YaHei,sans-serif;fill:#132333;font-size:20px}.box{fill:#edf4f6;stroke:#497780;stroke-width:2}.wire{fill:none;stroke:#087d8b;stroke-width:3}.g{fill:none;stroke:#465268;stroke-width:3}</style><rect x="20" y="45" width="255" height="160" rx="12" class="box"/><text x="40" y="80">压力片分压 → ADC</text><text x="40" y="122">AIx 信号中点 ●</text><text x="40" y="166">GND ●</text><rect x="335" y="45" width="270" height="215" rx="12" class="box"/><text x="355" y="80">MAX98357A / 音响</text><text x="355" y="124">SPK+ / OUT+ ●</text><text x="355" y="171">SPK− / OUT− ●</text><text x="355" y="219">GND ●</text><rect x="690" y="25" width="285" height="250" rx="12" class="box"/><text x="710" y="64">三通道以上示波器</text><text x="710" y="111">CH1：AIx</text><text x="710" y="155">CH2：SPK+</text><text x="710" y="200">CH3：SPK−</text><text x="710" y="246">Math = CH2 − CH3</text><path class="wire" d="M225 118 H300 V10 H680 V105 H700 M565 120 H640 V150 H700 M565 167 H620 V195 H700"/><path class="g" d="M170 163 V310 H830 V278 M470 215 V310"/><text x="85" y="349">所有普通探头地夹 → 系统公共GND；SPK−不是地。</text><text x="85" y="382">输出是Class-D开关波：低通后测声音，不能用PWM边沿当起音。</text></svg>'''
(O/'功放差分测量接线.svg').write_text(diagram,encoding='utf8')
from PIL import Image as PILImage,ImageDraw,ImageFont
im=PILImage.new('RGB',(1200,470),'white');draw=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',23);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21)
for box in [(20,60,320,255),(390,60,710,300),(820,30,1180,320)]:draw.rounded_rectangle(box,radius=12,fill='#edf4f6',outline='#497780',width=2)
for xy,text in [((38,80),'压力分压 / ADC'),((38,142),'AIx 信号中点'),((38,206),'GND'),((408,80),'MAX98357A / 音响'),((408,142),'SPK+ / OUT+'),((408,202),'SPK- / OUT-'),((408,260),'GND'),((838,48),'三通道以上示波器'),((838,110),'CH1 = AIx'),((838,170),'CH2 = SPK+'),((838,230),'CH3 = SPK-'),((838,282),'Math = CH2 - CH3')]:draw.text(xy,text,font=font,fill='#132333')
for path in [[(290,155),(355,155),(355,12),(800,12),(800,123),(823,123)],[(675,155),(760,155),(760,182),(823,182)],[(675,215),(740,215),(740,242),(823,242)]]:draw.line(path,fill='#087d8b',width=3)
draw.line([(180,221),(180,355),(1000,355),(1000,322)],fill='#465268',width=3);draw.line([(540,275),(540,355)],fill='#465268',width=3)
draw.text((50,385),'所有普通探头地夹只接系统公共GND；SPK-不是地。',font=font,fill='#132333')
draw.text((50,425),'输出仍含PWM载波：低通后测音频，不能用开关沿当起音。',font=small,fill='#132333')
im.save(O/'功放差分测量接线.png')

css='''body{margin:0;background:#08151f;color:#dbe8ed;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1100px;margin:auto;padding:36px 22px}h1{font-size:34px;color:#fff;line-height:1.3}h2{font-size:23px;color:#4cdcc5;margin-top:46px}p{max-width:100ch}a{color:#58dfcf}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #35515f;padding:10px;text-align:left;vertical-align:top}th{color:#55e0c9;background:#142d3b}tr:nth-child(even){background:#102430}.tag{color:#f0c37c}.card{background:#122a39;padding:20px;border:1px solid #365466;border-radius:18px;margin:20px 0}.shots{display:flex;gap:14px;overflow-x:auto}.shots img{max-height:480px;border-radius:14px}.wide{width:100%;background:white}code{word-break:break-word}details{margin:12px 0}summary{cursor:pointer;color:#f0c37c}@media(max-width:650px){main{padding:24px 14px}h1{font-size:29px}table{font-size:12px}td,th{padding:7px}.ledger{overflow-x:auto}.ledger table{min-width:800px}}@media print{body{background:white;color:black}h1,h2,a{color:black}.card{background:white}details{display:block}}'''
body=f'<h1>赛题逐项核对与实验室验收</h1><p class="tag">声芯乐动 · 2026年11月3日 · App0.24 / B713待上板候选</p><p>依据：<a href="{OFFICIAL}">高云官方2026赛题·选题二</a>。本页的“待测”不会被自动当成通过。</p>'
body+='<div class="card"><b>优先级：</b>真实32声部与采样率 → 端到端延迟/抖动 → 三维表情/ADSR/效果 → 脱机与FPGA可视化 → App拓展。</div>'
body+='<div class="shots">'+''.join(f'<img src="界面预览/{n}" alt="原生Compose界面测试信号预览">'for n in ['波形.png','频谱.png','XY.png'])+'</div><p>以上是原生Compose渲染的界面测试信号，非实板测量。可横屏放大。</p>'
for section in sections:
 body+=f'<section><h2>{html.escape(section["title"])}</h2>'+''.join(f'<p>{html.escape(p)}</p>'for p in section['paragraphs'])
 if section['title'].startswith('L06'):body+='<img class="wide" src="功放差分测量接线.svg" alt="功放差分测量接线">'
 body+='</section>'
body+='<h2>逐字拆解后的要求对照</h2><p>传感器、动作、合成方法的“等/任意/或”按备选解释；≥32和≤5/10ms保留边界，不替换为&gt;32或平均延迟。</p><div class="ledger"><table><tr><th>编号／要求</th><th>当前对应功能</th><th>证据／实验</th><th>状态</th></tr>'
for r in items:body+=f'<tr><td>{r["id"]}<br>{html.escape(r["requirement"])}</td><td>{html.escape(r["implementation"])}</td><td>{html.escape(r["source"])}<br>{r["lab"]}</td><td>{r["status"]}</td></tr>'
body+='</table></div>'
body+=f'<h2>来源与边界</h2><p><a href="{OFFICIAL}">原厂赛题与时间安排</a> · <a href="{ADI}">MAX98357A数据手册</a> · <a href="{TEK}">Tektronix探头与公共接地</a> · <a href="https://developer.android.com/reference/android/media/AudioRecord">Android采集时间戳</a></p><p>不编造官方评分权重、实测准确率或硬件延迟。“同意/通过”须由实测证据支持；新增候选未经上板，原Flash没有被改写。</p>'
(O/'明日实验室详细指导.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声芯乐动·实验室验收</title><style>'+css+'</style><main>'+body+'</main></html>',encoding='utf8')

# Printable handbook, with selectable Chinese text and repeating table headers.
pdfmetrics.registerFont(TTFont('Song','C:/Windows/Fonts/simsun.ttc',subfontIndex=0))
styles=getSampleStyleSheet();styles.add(ParagraphStyle('CN',fontName='Song',fontSize=9.5,leading=16,wordWrap='CJK',spaceAfter=8))
styles.add(ParagraphStyle('HeadCN',parent=styles['CN'],fontSize=15,leading=22,spaceBefore=12,spaceAfter=10,keepWithNext=True))
styles.add(ParagraphStyle('CellCN',parent=styles['CN'],fontSize=8,leading=12,spaceAfter=0))
P=lambda t,style='CN':Paragraph(html.escape(t.replace('−','-')).replace('\n','<br/>'),styles[style])
story=[P('声芯乐动｜赛题核对与明日实验室验收','HeadCN'),P('2026年11月3日整理；App0.24；B713候选；未烧录、实物待测。')]
for section in sections:
 story.append(P(section['title'],'HeadCN'))
 if section['title'].startswith('L06'):story.append(Image(str(O/'功放差分测量接线.png'),width=499,height=195))
 story.extend(P(p)for p in section['paragraphs'])
story.append(P('离开实验室前，先把关键数值写在这里','HeadCN'))
notes=[['项目','实测填写（不要抄仿真值）'],['板卡／UserCode／APK','____________________________'],['ADC VREF／功放带载最低电压','____________________________'],['LRCLK／BCLK','____________________________'],['同时独立可闻声部数／吞吐','____________________________'],['口琴最坏总延迟／判据','____________________________'],['二胡最坏总延迟／判据','____________________________'],['延迟max−min／试次数','____________________________'],['异常样本／原始数据目录','____________________________']]
note_table=Table([[P(c,'CellCN')for c in row]for row in notes],colWidths=[225,274])
note_table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.append(note_table)
story.extend([PageBreak(),P('附录：全部要求的功能与证据对照','HeadCN')])
table=[[P(x,'CellCN')for x in ['编号／要求','对应功能','实验证据／当前状态']]]
for r in items:table.append([P(r['id']+'\n'+r['requirement'],'CellCN'),P(r['implementation'],'CellCN'),P(r['lab']+'\n'+r['status']+'\n'+r['source'],'CellCN')])
t=Table(table,colWidths=[112,193,194],repeatRows=1,hAlign='LEFT')
t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#aaaaaa')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(t)
story.extend([Spacer(1,8),Paragraph(f'来源：<link href="{OFFICIAL}">高云2026官方赛题</link>；<link href="{ADI}">MAX98357A原厂数据手册</link>；<link href="{TEK}">Tektronix探头接地说明</link>。',styles['CN'])])
def footer(canvas,doc):
 canvas.setFont('Song',8);canvas.drawString(42,24,'声芯乐动 · 仿真与实测分开记录');canvas.drawRightString(A4[0]-42,24,str(doc.page))
SimpleDocTemplate(str(O/'明日实验室详细指导.pdf'),pagesize=A4,rightMargin=43,leftMargin=43,topMargin=36,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)

quick=[P('明天到实验室，按这个顺序做','HeadCN'),P('完整操作、阈值和命令在详细手册；此页只作现场顺序卡。')]
for title,text in [
 ('1｜先确认版本与供电（10分钟）','拍Mega60K铭牌/固件UserCode/APK版本；量模块端3.3V、MAX供电与ADC VREF。新版B713尚未自动烧录，不改接线。'),
 ('2｜最重要：32声部证据（20分钟）','测LRCLK≈48k、BCLK≈3.072MHz；测试4/8/16/32。导出≥0.5秒稳定PCM，推荐1.4秒；数32预期基频。独立关闭声部32、改声部1音高，录像并重新抓谱。32×实测Fs才是吞吐量。'),
 ('3｜最重要：端到端延迟（30分钟）','CH1尖端接压力分压AIx。功放用差分探头，或CH2接SPK+、CH3接SPK−并Math相减；所有普通地夹接公共GND。SPK−不是地！低通PWM后测起音。两音色各30次，保存CSV、最坏/p95/max−min和门限。≤5ms还未实测，不能只报平均值。'),
 ('4｜三维、包络、两音色三效果（15分钟）','压力/滑音/颤音深度分别改变，其他维度固定；七片轻中重电压/RMS/满格高度。保存ADSR长按松手，以及干声、回声、合唱、混响WAV。'),
 ('5｜脱机与硬件视觉（10分钟）','关闭手机蓝牙，用机身指引两首歌，验证节奏灯、自动换音区、正确/错误/暂停。再连接选FPGA输出，看OLED波形/FFT/XY；手机麦克风图只算辅助。'),
 ('6｜下载、换位、录音与稳定性（20分钟）','在线收藏后出现在App书架并能离线；七音同区换位随音区共同移动；设备录音CRC回传WAV。全负载至少10分钟，诊断每60秒需重启，记录电源/掉音/超时。'),
 ('7｜不要忘记带回的文件','版本/接线/仪器照片；LRCLK/BCLK截图；4/8/16/32原PCM与FFT；独立控制录像；延迟原CSV和填写CSV；三维/音色/效果录音；脱机/可视化/App功能录像。建议14时前测完，官网当前截止11月4日18时。')]:
 quick.extend([P(title,'HeadCN'),P(text)])
SimpleDocTemplate(str(O/'实验室随身检查卡.pdf'),pagesize=A4,rightMargin=43,leftMargin=43,topMargin=34,bottomMargin=38).build(quick,onFirstPage=footer,onLaterPages=footer)
print(json.dumps(dict(output=str(O),requirements=len(items),sections=len(sections)),ensure_ascii=False))
