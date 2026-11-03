"""Revise the contest draft and write a separate evidence-based design proposal.

This authoring tool does not change RTL, APK, bitstreams or the original template.
"""
from pathlib import Path
import json,re,shutil,hashlib,copy
from zipfile import ZipFile
from PIL import Image,ImageDraw
from lxml import etree as E
import fill_contest_technical_document_20261028 as b

ROOT=b.ROOT;OUT=ROOT/'output/engineering_upgrade_20261028'
REPORT=OUT/'report';REPORT.mkdir(parents=True,exist_ok=True)
ASSETS=REPORT/'assets';ASSETS.mkdir(exist_ok=True)
b.OUT=REPORT;b.ASSETS=ASSETS
b.DOCX=REPORT/'声芯_竞赛技术文档_工程图修订版.docx'
b.CONTENT.clear();b.LIMITED.clear();b.figures();b.compose()

def replace(prefix,new):
    for x in b.CONTENT:
        if x.get('kind')=='p' and x.get('text','').startswith(prefix):
            old=x['text'];x['text']=new
            for k,(text,limit) in list(b.LIMITED.items()):
                if text==old:b.LIMITED[k]=(new,limit)
            return
    raise KeyError(prefix)

replace('技术文档 ·','技术文档 · 工程图修订稿 · 2026年10月28日')
replace('声芯是一款',b.LIMITED['摘要'][0].replace('供电故障后的整机复测及外壳总装尚未完成','新电源已购，整改后的整机复测及外壳总装尚未完成'))
replace('（1）以32份独立声部',
 '现阶段的32声部、手机联动与曲目指引属于工程实现，尚不足以单独证明算法原创。拟重点研究七片敲击的早期力度估计与保留真实和弦的串扰判别，并设计固定帧时限的共享音高流水线；以前后对照的误触发、漏触发、力度误差、延迟及DSP占用评价。新增方案尚未实现和验证，不作为已完成创新成果申报。')
replace('采用矩形双层机身方案',
 '采用矩形双层机身，上层沿用已经制作的七片敲击面，右侧设置OLED、滑杆、旋钮及五颗功能键。现已建立参数化三维装配规划，包含顶板开孔、侧壁、支柱及内部模块包络；输出STEP、STL与GLB文件。图2来自实际三维几何渲染，不是照片重建或成品实拍。')
replace('图2  矩形双层', '图2  参数化CAD装配规划与内部包络（设计占位尺寸，非加工定稿）')
replace('不透明顶板在各片旁侧',
 '规划外包络暂取420 mm×240 mm×80 mm、板厚3 mm，均为设计假设。七片、屏窗、五键和各模块的实际尺寸尚待测量；板卡包络不含推测的内部元器件及原板孔位。顶板旁侧透光点对应普通LED，内部预留线束和检修空间；STEP几何有效性已检查，但尚未进行实物配合与装配干涉验收。分解视图、三维文件及尺寸参数随附工程图包[10]。')
replace('图3  压力分压', '图3  压力分压、LED限流和常开按钮电路（完整五张A3模块原理图另附）')
replace('近期出现反接、5 V口',
 '新电源硬件已经购买，当前应完成更换、分支供电及上电验收。推荐一个12 V总入口经保护后分成两路：一路接FPGA原有DC5521入口，另一路经额定能力足够的降压模块形成外设5 V。该底板原有12 V输入及内部电源管理见厂家原理图[2]；不从面包板3.3 V或5 V电源轨向FPGA电源输出端反灌。适配器和降压模块的电流能力、温升及故障模块状态尚待实测确认。完整原理图将现有模块连接、新供电候选及可选灯环分别标明，按模块边界绘制，尚未建立芯片级PCB及ERC工程。MAX的供电及桥接输出遵循器件资料[4]。')
replace('作品已形成七片压力输入',
 '作品已形成七片压力输入、音频合成、手机控制、中文OLED和LED反馈的原型系统，并经历多轮实物试听及界面修订。新电源已经购买，供电更换与总装后的整机复测待完成；当前完整耳机恢复程序已下载到SRAM并读回0x9D67。已完成的软件及数字验证，与供电整改后待恢复的外放和外设联调分别记录。')
replace('七片敲击面已制作；矩形机身',
 '七片敲击面已制作，五颗功能键已到手；本次补充50个有效实体组成的参数化装配规划，并通过STEP重新导入检查。图2与随附分解视图说明外观和内部净空关系；尺寸仍需实测，外壳固定、接插件安装、线束整理和总装照片尚未确认完成。')
replace('已有七路压力分压、ADC接口',
 '已有压力分压、ADC、滑杆、旋钮、七灯、五键、OLED、蓝牙和音频接线资料。本次补充五张A3模块级原理图、SVG源图及连接清单，覆盖当前接线资料中的27个FPGA信号；其中单电源分支和可选灯环为候选设计。外放链路此前有声，供电整改后仍须逐块复测。')
replace('优先完善稳定电源',
 '新电源已购，先完成单入口分支供电与整机验收。资源扩展优先共享当前复制32次的音高查表和变调乘法，保留32份独立声部状态；后续评估自动演奏与实体演奏共用声源，但须明确总声部数。以真实敲击数据研究早期力度及串扰判别，确保和弦召回率不因抑制误音而下降。扩展必须同步比较DSP、时限、误差与听感；曲目上传和事件录制放在核心指标验收后。')

for x in b.CONTENT:
    if x['kind']=='table' and x['headers'][0]=='模块':
        for row in x['rows']:
            if row[0]=='音频与供电':row[2]='新电源已购；整改后复测，耳机版SRAM'

at=next(i for i,x in enumerate(b.CONTENT) if x.get('text','').startswith('35是可选择音高数'))
b.CONTENT[at:at]=[
 {'kind':'p','style':'SCBody','text':'资源余量需要按类型判断。当前DSP使用率91.1%，是音频扩展的主要算术瓶颈；Logic约50.5%、BSRAM约38.1%，并非全部资源耗尽。源码中的声源计算已经分时，但音高入口仍实例化32份查表和32路32×17位变调乘法。拟将入口改为逐声部共享流水线，先锁存本帧输入再计算，保留全部独立相位和包络；尚无优化后的综合成绩。'},
 {'kind':'p','style':'SCBody','text':'候选时序为32×2拍音高预处理＋32×4拍声源计算，共192拍，再为提交与控制预留8拍，目标不超过每帧200/256拍。该值是待验证排程预算，不是当前已运行结果。物理DSP占用不能从源码乘法数量直接相减；重构后需重新综合、布局布线和逐样本对照。当前报告PRIMARY/LW路由均为8/8，还应检查被提升的高扇出控制网，不能据此认定有八个独立时钟域。'},
]
at=next(i for i,x in enumerate(b.CONTENT) if x.get('text')=='4.2 心得体会')
b.CONTENT[at:at]=[
 {'kind':'p','style':'SCBody','text':'更具研究价值的后续方向，是在确定起音时限内联合判断“何时触发、力度估计到什么程度、邻片是否真的被敲击”。已有FSR低延迟和多点识别研究[9]，因此不能把采用FSR、阈值或共享乘法本身称为首创。拟以实际七片装配为对象，与固定阈值、逐片校准及完整峰值等待方法进行比较，证明在误音、真和弦保留、力度误差和延迟之间获得实测改进。若实测串扰并不明显，则取消这一分支，聚焦早期力度与起音自然度，不制造没有证据的问题。'}]
refs=[
 '[9] BOSI M, JORDÀ S. Towards fast multi-point force and hit detection in tabletops using mechanically intercoupled Force Sensing Resistors[C]. NIME, 2012. https://www.nime.org/proceedings/2012/nime2012_257.pdf.',
 '[10] CADQUERY PROJECT. CadQuery Documentation：参数化实体建模与STEP导出[EB/OL]. [2026-10-28]. https://cadquery.readthedocs.io/en/latest/.'
]
for ref in refs:b.p(ref,'SCRef')
next(x for x in b.CONTENT if x.get('text')=='第五部分  参考文献')['page']=True
next(x for x in b.CONTENT if x.get('text')=='2.2 硬件系统介绍')['page']=True

# Replace the old block schematic and flat mechanical diagram with actual assets.
shutil.copy2(OUT/'schematics/detail_sensors_led.png',ASSETS/'circuits.png')
im=Image.new('RGB',(1800,660),'white')
for k,n in enumerate(['assembly.png','inside.png']):
    src=Image.open(OUT/'cad'/n).convert('RGB')
    # Remove duplicated in-image titles and footers; keep the report caption.
    src=src.crop((90,150,1710,1000));src.thumbnail((885,550))
    im.paste(src,(k*900+(900-src.width)//2,30))
    ImageDraw.Draw(im).text((450+k*900,560),'(a) 装配规划' if k==0 else '(b) 内部模块包络',font=b.font(29),anchor='mt',fill='black')
im=im.crop((0,0,1800,620));im.save(ASSETS/'mechanical.png')
images=b.write_docx();validation=b.verify(images)
(REPORT/'正文内容.json').write_text(json.dumps(b.CONTENT,ensure_ascii=False,indent=2),encoding='utf-8')

# A separate proposal contains comparisons, planned algorithms and acceptance
# criteria. Its future work is not inserted into the report as achieved results.
proposal_dir=OUT/'proposal';proposal_dir.mkdir(exist_ok=True)
b.OUT=proposal_dir;b.ASSETS=proposal_dir/'assets';b.ASSETS.mkdir(exist_ok=True)
b.DOCX=proposal_dir/'声芯_技术创新与资源优化方案.docx'
b.CONTENT.clear();b.LIMITED.clear()
p,h,t,fig=b.p,b.h,b.table,b.fig
p('声芯：技术创新与资源优化方案','SCTitle')
p('研究与实施设计稿 · 2026年10月28日','SCMeta')
p('本方案回答“还应做出什么自己的技术贡献”。当前资源来自已构建的完整耳机版本，新增算法、节省量和目标指标均未作为既成成果。电源硬件已经购买，下一步是完成装配和验证。')
h('1  把创新落到可验证的问题',1)
p('产品外观、App和OLED能够提高完成度，但不足以单独证明技术原创。32复音、DDS、ADSR、分时复用、BLE和数字音效都是已有方法。更有分量的贡献，应明确一个现有方案处理不好的问题，提出本项目自己的算法或调度结构，并在相同输入、相同硬件和相同评价口径下证明改进。不能保证某个方案必获一等奖，也不能在没有新结果时把“拟研究”改写为“已突破”。')
t(['路线','具体研究问题','判断与取舍'],[
 ['A 早期力度与真和弦保护','在有限起音等待内估计相对峰值；区分邻片耦合与真实双音','作为主要实验贡献候选；先采数据，确认问题存在'],
 ['B 固定帧时限的共享计算','保留32份独立状态，减少重复宽乘法和查表，并使参数同帧一致','作为资源基础与体系结构贡献；已找到具体代码热点'],
 ['C 弓弦/簧片物理模型','非线性激励、共振和发音手势之间的动态关系','研究深度高，但辨识、定点稳定性及资源风险最大；暂不优先']
],[1800,3400,3106],'表1  三条路线比较')
p('推荐先完成B，再研究A，把“低资源、固定计算时限”与“更早且更可靠地识别演奏动作”连接成一项完整贡献。C可保留为后续方向，不在现阶段同时扩张。A必须以实测为前提：若七片装配没有显著串扰，就不做无用的串扰模型，改为研究逐片一致性、早期力度误差和自然起音。')
p('可能成立的成果名称：面向七片压力演奏面的时限约束力度估计与共享音频流水线。名称并不等于创新证明；最终应由对照实验决定哪些内容值得保留。')

h('2  当前资源究竟卡在哪里',1,True)
t(['资源','当前使用 / 总量','判断'],[
 ['DSP','107.5 / 118，91.1%','主要算术瓶颈；还剩10.5个报告单位'],
 ['Logic','30280 / 59904，50.5%','仍有空间，但分配器及复用选择逻辑也要留余量'],
 ['BSRAM','45 / 118，38.1%','并非当前总瓶颈；音效延迟线占用较多'],
 ['时序','Setup +22.260 ns；Hold +0.085 ns；违例0','仅说明本次约束下通过，不代表端到端5 ms'],
 ['时钟路由','PRIMARY 8/8；LW 8/8','含被提升的高扇出控制网；需要检查其用途']
],[1450,3500,3356],'表2  当前完整耳机工程的实际布局布线结果')
p('基线位流版本0x9D67；本次重新核对发布清单，全部源码输入哈希匹配。这里没有把早期小工程的低占用写成当前完整版成绩。综合报告中的“DSP运算实例”和布局布线的“物理DSP报告单位”不是同一口径，不能直接相减估算优化效果。')
t(['优先级与位置','已查到的结构','应怎样改'],[
 ['P1 playable_synth32','generate复制32份音高表，及32路32×17位变调乘法','锁存同帧参数；一个查表入口及共享流水乘法逐声部计算'],
 ['P2 自动演奏声源','独立synth_voice与纹理计算，和32声部路径重复','评估统一声源；明确总数为32时的分配政策'],
 ['P3 位宽与常系数','宽乘、常系数滤波及限幅分支较多','先证范围，再选定点位宽或移位加法；保留误差报告'],
 ['P4 存储/选择网络','声部分配器较多LUT；效果延迟线30个BSRAM','先量访问冲突和带宽；不盲目删曲库或降采样']
],[1800,3200,3306],'表3  直接对应当前代码的优化顺序')
p('P1是最值得先做的一处：主声源已经轮流处理32声部，但它前面的音高准备仍空间复制。共享入口有望降低乘法与查表重复；需要付出多路选择、结果缓存和控制逻辑。它不是“删掉31个声部”，独立相位、包络、音色及归属状态必须全部保留。音高表每份综合显示110 LUT，只能作为重复结构证据，不能把32×110直接当作最终净节省。')

h('3  路线B：可执行的共享流水设计',1,True)
p('每个48 kHz音频帧在12.288 MHz时钟下有256拍。拟采用两阶段排程：先在帧边界锁存32份gate、note、velocity及公共表情，再逐个准备音高步进；随后运行现有四拍声源服务。若输入在运算期间变化，留到下一帧采用，避免同一混音样本中前后声部用了不同的音区或变调。')
t(['阶段','候选预算','设计要求'],[
 ['输入快照及提交','与控制共计预留8拍','同步/握手完成后锁存；不跨域直接读活动总线'],
 ['音高准备','32声部×2拍＝64拍','共享35项查表与变调流水；保存有效音标志和结果'],
 ['声源服务','32声部×4拍＝128拍','各自phase/envelope/age；单一混音提交点'],
 ['总预算','目标≤200/256拍，余量≥56拍','192拍运算＋8拍控制为候选；综合后确认延迟']
],[1800,2700,3806],'表4  候选帧内排程（不是已实现结果）')
p('先保留现有32×17位乘积及截位规则，静态输入下以逐样本结果完全一致为首个验收条件。35音高×256个bend组合可穷举；再覆盖非法音号、重触发、释放、32路同时更新及帧边界变化。对于动态参数，先定义“帧边界锁存”为新参考语义，再比较参考模型与RTL，不能宣称与旧版任意时刻读参都逐位等价。')
p('自动演奏统一声源属于第二阶段。若预留1个声部用于曲目，则必须公开说明为31路实时＋1路自动演奏、总数32；若要保持32路实时再叠加曲目，就需要33份状态及新的排程验证。不能靠暗中减少并发得到漂亮的节省数字。原有自动播放时配置切换、歌词、力度与停止恢复也必须回归。')
p('目标：保持32声部及48 kHz、帧运算≤200拍、Setup/Hold无违例；争取DSP≤80%以恢复扩展余量。80%只是设计目标，当前没有优化后成绩。最终同时报告LUT、BSRAM、寄存器和关键路径，防止把DSP节省转移成不可接受的选择网络或时序问题。')

h('4  路线A：早期力度与真和弦保护',1,True)
p('当前检测器具有独立基线、双阈值及4次同通道采样的峰值等待；已经记录rise，但力度函数明确不使用rise。可以研究：先以较短观测估计峰值起音，再在峰值到来时平滑修正，使轻重敲击稳定，同时不为等峰值延长所有音的起音。估计对象为相对ADC峰值，不在没有力学标定时称为绝对力值。')
p('第一步采七路原始序列并带通道时间戳。轮询采样不是七路同一时刻采样，跨通道判断必须校正采样偏移。空闲噪声估计和逐片增益只由校准样本确定；按压期间冻结基线，防止把慢按当作漂移吸收。')
p('候选估计器输入包括去基线幅值、首段上升率、连续两次差分和当前通道参数。先用短分段线性表估计峰值，置信度足够时提前触发；置信度不足时，在明确的最长观察窗口内等待后续样本，不无限等峰。后续只在现有声部内修正力度，不补播新的起音；修正使用有界斜率，避免突然变响、爆音或音色抖动。')
p('只有在实测显示机械耦合时，才加入稀疏邻域模型：标定单片敲击时邻片幅值比和滞后范围。真实双音可能恰好同时出现，不能简单保留最大者，也不能触发后屏蔽全部邻片。候选残差需结合各片上升证据、时间差和持续性；模糊情况偏向保留真实演奏，并把增加的误音量纳入代价。')
t(['比较方法','必须保留的对照','要回答的问题'],[
 ['原版','固定阈值＋4样本峰值窗口','当前误差和延迟到底多大'],
 ['逐片校准','仅校准阈值/增益，不用联合判别','改进是否只是校准带来的'],
 ['早期估计','加置信度与限时，不加串扰模型','缩短等待后力度误差是否可接受'],
 ['完整候选','仅在有实际串扰时加邻域判别','误音减少时是否误删真实和弦']
],[1600,3350,3356],'表5  消融对照，避免把多个因素混在一起')
p('FSR多点、耦合与低延迟识别已有研究[1-2]。本作品有机会形成自己的贡献，是针对这套七片装配提出并量化一个更合适的时限、置信度及和弦保护机制，而不是宣称首次使用这些基本概念。若对照结果没有优势，应如实放弃“创新有效”的说法。')

h('5  用什么实验决定它是否值得写进申报',1,True)
t(['试验','最小可操作设计','记录及判定'],[
 ['单片与力度','7片×轻中重×30次；按完整采集场次划分校准/测试','误触发、漏触发；归一化峰值MAE/P95；逐片一致性'],
 ['双音与滚奏','相邻/非相邻组合，近同时和先后敲击各多次','真实和弦召回率；实际时间差随原始序列记录'],
 ['迟延','每片/两音色/不同力度重复，记录原始触发与模拟音频','统一门限，报告中位/P95/最大；本地目标<5 ms'],
 ['结构优化','同一约束、工具、音色、采样率及32路输入','资源前后表、期限断言、静态逐样本一致及动态模型误差'],
 ['听感与稳定','等响度A/B；起音、长音、快点、收手及模式切换','无异常补播/卡音/突增；不要只听更响的一版']
],[1500,3400,3406],'表6  所有项目均为待执行试验')
p('先分场次再拟合参数，测试数据不参与门限挑选。简易敲击夹具或固定下落物可提高重复性；如只用手敲，必须保留动作差异，不能把预测误差直接解释成传感器的绝对力误差。先导试验可先每片每档10次，验证采集和标注流程，再补足正式数据。')
p('本地<5 ms必须约定起点、音频起音门限、采样带宽及音效状态。当前口琴/二胡包络达到完整攻击幅度分别需256/512音频帧，约5.3/10.7 ms；这不是声响首次出现的延迟。不能只报告128拍计算时间就宣布达标，也不能为了数字好看删除自然起音。')
p('手机链路另算：当前9600 baud，9字节8N1仅UART串行时间已约9.375 ms，尚有BLE调度与App合并。App可继续消除旧请求积压，但不应承诺手机全链路<5 ms。若升级波特率，需要确认到手JDY参数、双端同步和丢包回归；不能把本地指标套到无线链路。')
p('验收顺序：冻结当前基线→P1共享音高的数字等价及布局布线→恢复供电与原始采集→评估A的收益→整机时延与听感→把真正有证据的改进写进创新点。可以先做软件结构优化，不必等电源总装完才开始。')

h('6  一个电源接口与专业工程图',1,True)
p('可以实现单一总电源入口。推荐总12 V在面包板之前分支，一路去FPGA原有DC5521入口，一路经降压形成外设5 V；逻辑地共地，功放大电流回路避免经过压力采样回流。厂家底板电源树支持12 V原入口[3]。不建议让小型面包板稳压模块先承担整机电流，再从其3.3 V/5 V轨给FPGA“倒着供电”。')
p('新电源已经购买，不再列为采购缺口。仍需核对其输入范围、持续/峰值电流、接头极性、保护和温升；单入口适配器按整机峰值功率及余量选择。新的3.3 V输出不能与开发板或ADC的3.3 V输出直接并联。图纸第1页是候选分配设计，尚未证明已购件满足其额定条件。')
p('本次已补五张A3电路图：供电、七路压力与滑杆、七灯与五键、OLED/BLE、音频/旋钮。图中有元件编号、阻值、网名、连接与可选支路，覆盖27个现有FPGA信号。按购买模块边界绘制，未知内部电路没有猜画。SVG为可编辑矢量图，另有连接清单；当前不是KiCad原生工程，也未运行其ERC。后续若做接口PCB，应在EDA中建立真实连接器引脚和封装后再作ERC/DRC与制板。')
p('三维部分已生成50个实体的装配规划，STEP重新导入后几何有效；另附STL、GLB和参数。420×240×80 mm机身及模块包络是设计假设，按钮到手尺寸、实际板卡长宽高、孔距和接口插拔空间要实测后更新。它能帮助讨论摆放与检修，尚不是可直接下单加工的模型。')
p('参数化实体建模使用CadQuery，可导出STEP[4]；KiCad提供电气规则检查及原理图/PCB导出路径[5]。专业感应来自正确网表、实测尺寸、公差和版本对应，而不是仅增加装饰渲染。')

h('7  照片辅助建模：哪些方法实际可用',1,True)
t(['方法','适用范围','本项目注意点'],[
 ['测量＋参数化CAD','安装孔、板厚、外壳和模块净空；可编辑尺寸','优先采用；保留STEP与参数，这是本次已完成的路线'],
 ['COLMAP多视图','从多角度重叠照片恢复可见表面','黑色/反光/细线较难；需比例尺和测量，不能猜隐藏孔'],
 ['TripoSR单图网格','快速展示形状、辅助视觉讨论','官方默认约6 GB显存；本机8 GB可尝试但未实跑'],
 ['TRELLIS.2 / SAM 3D','较复杂的AI形状重建','默认分别要求至少24/32 GB显存；不适合当前8 GB配置直接照默认运行']
],[1800,3200,3306],'表7  开源路线及当前适用性')
p('单张照片生成的是推测表面网格，不能保证螺孔位置、接头尺寸、内部空间和绝对尺度。多视图应绕物体移动拍摄，保持焦距与重叠，减少反光，提供尺子和正交方向照片；COLMAP官方建议同一特征在多个视图出现[6]。生成后仍要和尺寸表比较，不能把贴图逼真的网格直接称为加工CAD。')
p('旧聊天中的临时照片路径目前不可读取，因此本次没有进行照片重建。若补充当前实物的正面、背面、侧面、接口近照及带尺照片，现有参数化模型可以逐项校准；没有照片和尺寸也不妨碍先完成现在这套可编辑规划。')
h('参考资料',2)
for s in [
 '[1] Bosi M, Jordà S. Towards fast multi-point force and hit detection in tabletops using mechanically intercoupled Force Sensing Resistors. NIME 2012. https://www.nime.org/proceedings/2012/nime2012_257.pdf',
 '[2] Tindale A R, et al. A Comparison of Sensor Strategies for Capturing Percussive Gestures. NIME 2005. https://www.mistic.ece.uvic.ca/publications/2005_nime_drum.pdf',
 '[3] SIPEED. Tang Mega 60K硬件资料及Dock rev1.4原理图，第2、4页. https://en.wiki.sipeed.com/hardware/en/tang/tang-mega-60k/mega-60k',
 '[4] CadQuery Documentation. https://cadquery.readthedocs.io/en/latest/',
 '[5] KiCad 9 CLI Documentation. https://docs.kicad.org/9.0/en/cli/cli.html',
 '[6] COLMAP Tutorial. https://colmap.github.io/tutorial.html',
 '[7] TripoSR官方项目及硬件要求. https://github.com/VAST-AI-Research/TripoSR',
 '[8] TRELLIS.2官方项目. https://github.com/microsoft/TRELLIS.2',
 '[9] SAM 3D Objects官方安装要求. https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md',
 '[10] 声芯当前RTL、布局布线及发布清单. 0x9D67完整耳机版本；2026-10-28重新核对源码哈希；资源审计文件随附。'
]:p(s,'SCRef')

proposal_images=b.write_docx()
# Keep the compact reference list together on its existing final content page.
with ZipFile(b.DOCX) as z:files={n:z.read(n) for n in z.namelist()}
styles=E.fromstring(files['word/styles.xml'])
refstyle=styles.xpath("//w:style[@w:styleId='SCRef']",namespaces=b.NS)[0]
spacing=refstyle.find('w:pPr/w:spacing',b.NS)
spacing.set('{'+b.W+'}after','35');spacing.set('{'+b.W+'}line','270')
files['word/styles.xml']=E.tostring(styles,encoding='UTF-8',xml_declaration=True,standalone=True)
from zipfile import ZIP_DEFLATED
with ZipFile(b.DOCX,'w',ZIP_DEFLATED) as z:
    for name,data in files.items():z.writestr(name,data)
(proposal_dir/'内容.json').write_text(json.dumps(b.CONTENT,ensure_ascii=False,indent=2),encoding='utf-8')
# Save the full readable proposal as the project's design record too.
lines=['# 声芯技术创新与资源优化设计（待实现）','']
for item in b.CONTENT:
    if item['kind']=='p':lines.extend([item['text'],''])
    elif item['kind']=='table':
        lines.extend(['| '+' | '.join(item['headers'])+' |','| '+' | '.join(['---']*len(item['headers']))+' |'])
        lines.extend('| '+' | '.join(row)+' |' for row in item['rows']);lines.append('')
plan=ROOT/'docs/plans/2026-10-28-technical-innovation-design.md';plan.parent.mkdir(exist_ok=True)
plan.write_text('\n'.join(lines),encoding='utf-8')

print(json.dumps({'report':str(REPORT),'report_figures':images,'report_tables':validation['tables'],
 'proposal':str(b.DOCX),'proposal_figures':proposal_images,'proposal_tables':sum(x['kind']=='table' for x in b.CONTENT)},ensure_ascii=False,indent=2))
