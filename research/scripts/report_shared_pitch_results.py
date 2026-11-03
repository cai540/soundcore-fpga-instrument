"""Write factual results and a separate revised contest document."""
from pathlib import Path
import json,shutil,re
from PIL import Image,ImageDraw
import fill_contest_technical_document_20261028 as b

ROOT=b.ROOT;DATA=json.loads((ROOT/'build/shared_pitch_20261028/release.json').read_text(encoding='utf-8'))
OUT=ROOT/'output/shared_pitch_20261028';OUT.mkdir(parents=True,exist_ok=True)
REPORT=OUT/'report';REPORT.mkdir(exist_ok=True);ASSETS=REPORT/'assets';ASSETS.mkdir(exist_ok=True)
old=ROOT/'output/engineering_upgrade_20261028/report'
for p in (old/'assets').glob('*.png'):shutil.copy2(p,ASSETS/p.name)
b.OUT=REPORT;b.ASSETS=ASSETS;b.DOCX=REPORT/'声芯_竞赛技术文档_共享流水线实证版.docx'
b.CONTENT=json.loads((old/'正文内容.json').read_text(encoding='utf-8'));b.LIMITED.clear()
def replace(prefix,text):
    for x in b.CONTENT:
        if x['kind']=='p' and x['text'].startswith(prefix):x['text']=text;return
    raise KeyError(prefix)
replace('技术文档 ·','技术文档 · 共享音高流水线实证稿 · 2026年10月28日')
replace('声芯是一款',
 '声芯是一款将七片压力敲击面、滑音控制、中文显示与手机操作结合的电子乐器原型。作品以高云GW5AT-60B FPGA为计算核心，通过MCP3208采集七路压力及一路滑杆信号，硬件完成触发识别、力度映射、声部分配、包络与逐样本音色合成。系统设置五个音区、共35个可选音高，保留32个独立声部上下文，并提供口琴、二胡两类算法音色和三种音效。手机经BLE/UART操作设备，声音由FPGA产生。内置《我和我的祖国》《敕勒歌》，支持自动演奏、敲对推进、自动换音区和逐字歌词。\n针对32路音高变调运算的重复开销，本版实现帧界参数锁存、单表查音与共享乘法流水线，在193/256拍预算内完成全部声部计算。完整耳机工程DSP由107.5/118降至45.5/118，Logic由30280降至26990，BSRAM保持45；11项数字检查通过，包括16384种音高/变调组合及1200帧PCM对照。原耳机版曾完成SRAM下载，本版候选位流0xC2B3仅完成构建，尚未烧录。新电源已购，整机复测、实板听感、32路频谱及端到端延迟仍待验收。',)
replace('采用分时复用流水线',
 '采用帧界一致性锁存与共享音高流水线，将32份音高查表及宽乘法合并为一个运算入口。音高准备64拍，原声源服务128拍，连同启动共193拍，在12.288 MHz时钟的256拍音频帧内完成。每声部保留独立相位、包络、音色及表情状态。静态音高组合穷举，动态输入与使用同帧快照的原结构比较；声源算法及截位规则保持不变。实体/手机输入统一到设备状态，曲目播放、正确音推进、OLED歌词和LED共享事件索引。标准I²S外放及PT8211耳机具有独立输出适配。')
replace('现阶段的32声部、手机联动',
 '针对多声部变调的重复开销，实现帧界一致性锁存与共享音高流水线，保留32份独立声部状态，在193/256拍内完成计算。完整耳机工程DSP用量降低57.7%、Logic降低10.9%；16384种音高组合及1200帧数字对照通过。该结果体现本项目的架构改进，不将分时复用本身宣称为原创。早期力度及和弦保护仍为后续研究。')
replace('外放工程将标准I²S',
 '外放工程将标准I²S送入MAX98357A，再驱动扬声器。供电事故后建立了PT8211板载耳机恢复工程，串行格式不同。本次资源对比均采用完整耳机上层、同一器件和管脚约束，只重构共享音高入口；标准I²S外放在供电整改后仍须单独复测。')
replace('（2）32声部合成。',
 '（2）32声部合成。playable_synth32在音频帧开始时锁存gate、note、velocity、timbre和bend，以同一查表及32×17位乘法逐个准备音高；64拍后启动poly_synth32_tm。后者保留32份phase、envelope、gate、note_age及表情状态，单声部四拍、整轮128拍。新入口总完成时间为193拍，全部结果在下一个256拍帧界之前准备好。名义声部更新吞吐量仍为1.536 M声部样本/秒；实际32路可闻频谱证据待补。')
replace('作品已形成七片压力输入',
 '作品已形成压力输入、实时合成、手机控制、中文OLED和LED反馈的原型，并经历多轮试听和界面修订。新电源已经购买，供电更换与总装后的整机复测待完成。已上板基线为0x9D67；本次共享音高候选位流为0xC2B3，完成数字验证和完整构建，尚未烧录。布局布线成功与实际听感、供电可靠性分别验收。')
replace('资源余量需要按类型判断',
 '本次只重构音高准备入口。相同完整耳机工程中，DSP由107.5/118（91.1%）降至45.5/118（38.6%），减少62个报告单位，相对下降57.7%；Logic由30280降至26990，相对下降10.9%。BSRAM保持45/118。寄存器由9614增至11111，增加1497，用于帧界锁存和步进缓存；这是以计算时间及寄存器换取宽乘法与查表面积。')
replace('候选时序为32×2拍',
 '音高准备使用64拍，启动占1拍，原声源仍使用128拍；数字测试测得每帧193拍完成，相比200拍设计上限余7拍，距256拍下一帧余63拍。完成时刻比原结构晚65拍，但两者均在下一输出帧前交付，没有新增整帧音频缓存。帧内输入变化按新定义留到下一帧；1200帧对照使用同样的帧界快照语义，不能据此宣称任意时刻读参的旧语义也完全一致。')
replace('新电源已购，先完成单入口',
 '新电源已购，先完成单入口分支供电与整机验收。共享音高优化已使DSP占用降到38.6%，为继续研究早期力度、真和弦保护、声源和音效预留空间。后续评估自动演奏与实体演奏共用声源时，须明确总声部数；继续比较DSP、寄存器、时限、误差与听感。曲目上传及事件录制在核心指标实测验收后推进。')
for x in b.CONTENT:
 if x['kind']=='table':
    if x['headers'][0]=='成果':
        x['rows'][0]=['FPGA共享音高候选','0xC2B3；完整耳机功能＋共享入口','构建完成，未烧录；基线0x9D67曾下载']
    if x['headers'][0]=='项目' and any('资源'==r[0] for r in x['rows']):
        for row in x['rows']:
            if row[0]=='声部运算':row[1]='32份独立状态；共享准备后193拍/帧';row[2]='16384种组合；1200帧及逐声部状态对照'
            elif row[0]=='完整耳机时序':row[1]='Setup/Hold违规0；余量＋27.791/＋0.104 ns'
            elif row[0]=='资源':row[1]='Logic26990；BSRAM45；DSP45.5';row[2]='分别约45.1%、38.1%、38.6%'
            elif row[0]=='耳机/音频回归':row[1]='11项共享与音频集成检查通过';row[2]='数字检查；本版实板听感待验'

# Figure 8: actual before/after utilization on one consistent axis.
im=Image.new('RGB',(1600,690),'white');d=ImageDraw.Draw(im)
b.label(d,(800,34),'完整耳机工程：共享音高重构前后',32,True)
for i,(key,name) in enumerate([('Logic','Logic'),('Register','寄存器'),('BSRAM','BSRAM'),('DSP','DSP')]):
    before=DATA['comparison'][key]['before'];after=DATA['resources'][key]['used'];total=DATA['resources'][key]['total'];y=100+i*130
    b.label(d,(125,y+30),name,27,True)
    for used,offset,color in [(before,0,'#b7b7b7'),(after,35,'black')]:
        d.rectangle((260,y+offset,1200,y+offset+25),outline='black',width=1)
        d.rectangle((260,y+offset,260+940*used/total,y+offset+25),fill=color)
    b.label(d,(1380,y+12),f'{before:g} / {total}',24)
    b.label(d,(1380,y+47),f'{after:g} / {total}',24)
b.label(d,(800,645),'灰：0x9D67基线；黑：0xC2B3候选；均为实际布局布线结果',26)
im.save(ASSETS/'resources.png')
replace('图8  完整耳机工程资源占用','图8  完整耳机工程重构前后资源（寄存器增加，DSP与Logic下降）')

limits=[('摘要','摘要',800),('功能与特性','1.1 功能与特性',400),('应用领域','1.2 应用领域',400),
        ('主要技术特点','1.3 主要技术特点',400),('主要创新点','1.5 主要创新点',200),
        ('设计流程','1.6 设计流程',200),('可扩展之处','4.1 可扩展之处',300),('心得体会','4.2 心得体会',1000)]
for name,heading,limit in limits:
    i=next(i for i,x in enumerate(b.CONTENT) if x.get('text')==heading)
    b.LIMITED[name]=(b.CONTENT[i+1]['text'],limit)
t=next(x for x in b.CONTENT if x['kind']=='table' and x['headers'][0]=='项目' and x['rows'][0][0]=='输入')
b.LIMITED['主要性能指标']=(''.join(''.join(row) for row in t['rows']),200)
n=b.write_docx();b.verify(n)
(REPORT/'正文内容.json').write_text(json.dumps(b.CONTENT,ensure_ascii=False,indent=2),encoding='utf-8')

# A short readable results document complements the full contest report.
BRIEF=OUT/'results';BRIEF.mkdir(exist_ok=True);b.OUT=BRIEF;b.ASSETS=BRIEF/'assets';b.ASSETS.mkdir(exist_ok=True)
b.DOCX=BRIEF/'共享音高流水线_优化结果.docx';b.CONTENT.clear();b.LIMITED.clear()
p,h,t,fig=b.p,b.h,b.table,b.fig
p('共享音高流水线：优化结果','SCTitle');p('声芯 · 0x9D67 → 0xC2B3 · 2026年10月28日','SCMeta')
h('1  已完成的改变与资源结果',1)
p('原结构为空间复制的32份音高表和32组变调宽乘法。本次在音频帧开始时锁存32份输入，用一个查表入口和共享乘法逐个准备步进，再启动原32声部声源。相位、包络、纹理和独立归属保持原结构；音色、曲库、App及管脚约束未修改。')
t(['指标','原完整耳机版','共享候选版','变化'],[
 ['DSP','107.5 / 118（91.1%）','45.5 / 118（38.6%）','减少62；用量下降57.7%'],
 ['Logic','30280 / 59904','26990 / 59904','减少3290，下降10.9%'],
 ['寄存器','9614 / 60780','11111 / 60780','增加1497，约15.6%'],
 ['BSRAM','45 / 118','45 / 118','不变'],
 ['声部 / 采样率','32 / 名义48 kHz','32 / 名义48 kHz','保持'],
 ['计算完成','128 / 256拍','193 / 256拍','增加65拍，仍在期限内']
],[1500,2300,2300,2206],'表1  相同完整耳机顶层与约束下的实际结果')
p('主要收益是把原先的重复宽乘法换成有限帧内时间。新增寄存器用于参数一致性锁存和结果缓存；没有靠减少声部、关闭效果或删掉曲库取得节省。当前结果来自Gowin布局布线，不能用源码乘法数量替代这一结果。')
p('一个音频帧有256拍，音高准备64拍、启动1拍、声源128拍，共193拍；距下一帧还有63拍。193拍约15.7微秒是内部运算时间，不能拿它证明传感器到实际声音已低于5毫秒。')

h('2  验证了什么，尚未验证什么',1,True)
t(['检查','结果及范围'],[
 ['音高组合','64种编码×256个bend＝16384组；包括35个有效音及非法编码'],
 ['逐样本对照','1200帧PCM逐位一致，逐声部相位、包络、门控及随机状态一致'],
 ['变化与恢复','两音色、成熟揉弦、帧内输入变化、独立释放和运算中复位'],
 ['集成检查','11项全部通过：含七片ADC、32音测试、手机/实体归属及耳机串行路径'],
 ['完整工程时序','Setup/Hold违例0；余量＋27.791 / ＋0.104 ns'],
 ['保持范围','37份保护文件哈希不变；原发布位流及全部实际管脚映射保留'],
 ['仍待实测','本版实板听感、32路模拟频谱、传感到模拟音频延迟、整改后的整机稳定性']
],[1800,6506],'表2  验证证据及实际边界')
p('对照的动态语义必须说清楚：两边在sample_tick锁存同一组参数，再分别计算。新结构故意取消了旧结构帧内即时读参的行为。因此“1200帧一致”表示相同帧快照输入下的结果，不能扩展为任意输入时刻都与旧语义一致。新的原子更新可避免同一混音样本中前后声部使用不同参数。')
p('回归中还修正了两个旧测试的时间假设：早期音头受平滑包络量化为零，不能只等12帧就判断无声；32音测试应等第32声部真正进入包络，不能把切换前留下的混合样本计作新模式已经发声。修改后的测试对原版及新版都通过，没有放宽实际声部数或音高条件。')
p('候选位流0xC2B3已生成，尚未扫描、烧录SRAM或写Flash；当前板上已知版本仍是此前的0x9D67。完整源码、日志、资源报告与哈希清单已冻结，便于之后进行同条件上板A/B验收。')

h('3  作为创新点应怎样表述',1,True)
p('建议表述：针对多声部变调计算的重复开销，设计帧界一致性锁存与共享音高流水线，保留32份独立声部状态，在193/256拍内交付结果。完整耳机工程DSP用量降低57.7%、Logic降低10.9%，并以16384种音高组合及1200帧数字对照验证。')
p('它现在可以作为有数据支撑的本项目硬件架构改进。分时复用、乘法器共享和参数锁存本身都是已有方法；不能仅凭此次应用声称基础算法首创、全球首次，或直接等同于高水平学术原创。更强的创新论证仍需要与合理替代架构比较，并说明为什么这一排程、状态组织和一致性策略适合本项目。')
p('下一阶段可做的比较是：在相同32声部和48 kHz条件下，比较不同共享程度的资源—期限曲线；或者把节省的资源用于有真实数据支撑的早期力度与真和弦保护。新的力度算法尚未实现，不加入本次已完成结果。')
h('证据索引',2)
p('当前发布记录：build/shared_pitch_20261028/release.json；实际布局布线：resource_report.txt与timing_report.html；数字回归：all_tests.json及各项日志。基线来源：build/headphone_20261027/release.json；基线源码快照保留在本次构建目录baseline中。','SCSmall')
p('本次修改的产品RTL只有playable_synth32.v。没有改变poly_synth32_tm与instrument_texture算法、供电或接线，也没有修改APK和两首曲目的事件数据。','SCSmall')
b.write_docx()
(BRIEF/'内容.json').write_text(json.dumps(b.CONTENT,ensure_ascii=False,indent=2),encoding='utf-8')

lines=['# 共享音高流水线优化结果','',f"候选：{DATA['user_code']}，未烧录。",'']
for x in b.CONTENT:
    if x['kind']=='p':lines.extend([x['text'],''])
    elif x['kind']=='table':
        lines+=['| '+' | '.join(x['headers'])+' |','| '+' | '.join(['---']*len(x['headers']))+' |']
        lines+=['| '+' | '.join(row)+' |' for row in x['rows']];lines.append('')
(ROOT/'docs/shared_pitch_optimization_2026-10-28.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'report':str(REPORT),'brief':str(BRIEF),'figures':n},ensure_ascii=False))
