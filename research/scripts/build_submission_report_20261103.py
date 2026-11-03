"""Build editable anonymous contest report from the supplied OOXML template."""
from pathlib import Path
import copy, hashlib, importlib.util, json, math, shutil
from xml.sax.saxutils import escape
from PIL import Image, ImageDraw, ImageFont
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/submission_20261103'
AS=OUT/'报告可编辑源/figures'
AS.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('template_helper',ROOT/'scripts/fill_contest_technical_document_20261028.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
h.OUT=OUT;h.ASSETS=AS;h.DOCX=OUT/'02_声芯乐动_技术报告_可编辑.docx'

class Figure:
    def __init__(self,w,height):
        self.w=w;self.h=height;self.im=Image.new('RGB',(w,height),'white');self.d=ImageDraw.Draw(self.im)
        self.s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" viewBox="0 0 {w} {height}"><rect width="100%" height="100%" fill="white"/>']
    def line(self,points,width=3,color='#222222'):
        self.d.line(points,fill=color,width=width)
        self.s.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    def rect(self,b,text='',size=27,fill='white'):
        self.d.rectangle(b,fill=fill,outline='#222222',width=2)
        x,y,x2,y2=b;self.s.append(f'<rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" fill="{fill}" stroke="#222222" stroke-width="2"/>')
        if text:self.text((x+x2)/2,(y+y2)/2,text,size)
    def text(self,x,y,text,size=26,anchor='mm',bold=False):
        f=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',size)
        lines=text.split('\n');total=len(lines)*(size+10)
        for i,t in enumerate(lines):
            yy=y-total/2+(i+.5)*(size+10)
            self.d.text((x,yy),t,font=f,fill='#161616',anchor=anchor)
            ta='start' if anchor.startswith('l') else 'end' if anchor.startswith('r') else 'middle'
            self.s.append(f'<text x="{x}" y="{yy}" text-anchor="{ta}" dominant-baseline="central" font-family="Microsoft YaHei, sans-serif" font-size="{size}" font-weight="{"bold" if bold else "normal"}">{escape(t)}</text>')
    def arrow(self,a,b):
        self.line([a,b]);v=math.atan2(b[1]-a[1],b[0]-a[0]);q=[b,(b[0]-13*math.cos(v-.5),b[1]-13*math.sin(v-.5)),(b[0]-13*math.cos(v+.5),b[1]-13*math.sin(v+.5))]
        self.d.polygon(q,fill='#222');self.s.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in q)}" fill="#222"/>')
    def dot(self,x,y):
        self.d.ellipse((x-5,y-5,x+5,y+5),fill='#222');self.s.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#222"/>')
    def resistor(self,x,y,name):
        self.line([(x,y),(x+30,y)]);self.rect((x+30,y-14,x+130,y+14));self.line([(x+130,y),(x+160,y)]);self.text(x+80,y-42,name,24)
    def ground(self,x,y):
        self.line([(x,y),(x,y+18)]);self.line([(x-22,y+18),(x+22,y+18)]);self.line([(x-14,y+27),(x+14,y+27)]);self.line([(x-6,y+36),(x+6,y+36)])
    def save(self,name):
        self.im.save(AS/(name+'.png'));(AS/(name+'.svg')).write_text(''.join(self.s)+'</svg>',encoding='utf-8');return name+'.png'

def figures():
    f=Figure(1500,760);f.text(750,38,'硬件实时合成与手机创作分工',35,bold=True)
    boxes=[((30,130,330,255),'7路压力片 / AI7滑杆\nMCP3208 · SPI'),((30,340,330,455),'五键 / EC11\n音区 · 音色 · 曲目'),((440,125,1020,475),'FPGA · GW5AT-60B\n触发 / 表情 / 32声部合成\nADSR → 三种效果 → I²S\n曲谱指引 / 分析 / 录音'),((1130,125,1470,250),'MAX98357A\n扬声器'),((1130,340,1470,455),'OLED / 7颗LED\n歌词 · 力度 · 指引'),((440,590,1020,710),'Android App · 蓝牙串口\n本地录音识别 / 简谱识别 / 曲谱书架')]
    for b,t in boxes:f.rect(b,t,28)
    for a,b in [((330,195),(440,195)),((330,395),(440,395)),((1020,195),(1130,195)),((1020,395),(1130,395)),((730,475),(730,590))]:f.arrow(a,b)
    f.text(1180,620,'音频逐样本计算在FPGA完成\n识别模型在手机运行\n不依赖外部API',24)
    f.save('01_system')
    f=Figure(1500,790);f.text(750,38,'压力采样、滑杆与人机输入电路',34,bold=True)
    f.text(80,140,'ADC 3V3',26,anchor='lm');f.line([(230,140),(290,140)]);f.resistor(290,140,'R1 4.7 kΩ');f.line([(450,140),(500,140)]);f.rect((500,118,700,162),'FSR_i',25);f.line([(700,140),(830,140)]);f.dot(790,140);f.resistor(830,140,'R2 10 kΩ');f.line([(990,140),(1110,140)]);f.ground(1110,140);f.line([(790,140),(790,240),(1080,240)]);f.text(1200,240,'AI0…AI6',28)
    f.text(750,305,'七路独立分压：V_AI = 3.3 × 10k / (4.7k + R_FSR + 10k)',25)
    f.text(90,415,'3V3',26,anchor='lm');f.line([(200,415),(290,415)]);f.rect((290,400,570,430));f.text(430,365,'滑杆电位器',26);f.line([(570,415),(650,415)]);f.ground(650,415);f.arrow((430,520),(430,435));f.line([(430,520),(900,520)]);f.text(1040,520,'AI7 / PITCH',27)
    f.text(100,650,'3V3',26,anchor='lm');f.resistor(210,650,'上拉');f.line([(370,650),(500,650)]);f.dot(450,650);f.line([(450,650),(450,730),(650,730)]);f.text(830,730,'K1…K5 / EC11输入',25);f.line([(500,650),(580,605)]);f.line([(600,650),(680,650)]);f.ground(680,650);f.text(1110,635,'常开触点：按下接地\n松开高，按下低\n可使用已配置的内部上拉',25)
    f.save('02_input_circuit')
    f=Figure(1500,830);f.text(750,38,'音频、显示与灯光电路',34,bold=True)
    f.rect((45,120,490,490),'FPGA · LVCMOS33\ndac_bclk\ndac_lrclk\ndac_din\noled_scl / oled_sda\npad_led_o[0…6]',29)
    f.rect((890,110,1440,285),'MAX98357A\nBCLK / LRC / DIN\nVIN=稳定5V；GND=公共地',26)
    for yy in [175,215,255]:f.arrow((490,yy),(890,yy))
    f.text(690,125,'I²S：3.3V逻辑',24);f.rect((930,340,1420,475),'OLED · I²C · 128×64\nVCC=3.3V；SCL/SDA上拉至3.3V\nGND=公共地',25);f.arrow((490,390),(930,390))
    f.text(180,590,'pad_led_o[i]',25);f.line([(330,590),(400,590)]);f.resistor(400,590,'R_LED 1 kΩ');f.line([(560,590),(665,590)]);f.line([(665,570),(665,610),(705,590),(665,570)]);f.line([(708,570),(708,610)]);f.line([(708,590),(840,590)]);f.ground(840,590);f.arrow((690,558),(713,533));f.arrow((710,560),(733,535));f.text(1120,580,'七颗LED各一只串联电阻\nK5灯环另一路受控输出\n灯环限流与额定电流需实测',25)
    f.text(750,735,'MAX的SPK+ / SPK−只接喇叭两端；SPK−不是公共地。SD用10 kΩ上拉。\n普通示波器地夹只接公共GND，差分输出按实验室指导使用两通道相减或差分探头。',25)
    f.save('03_output_circuit')
    f=Figure(1500,750);f.text(750,40,'32声部共享调度与独立状态',34,bold=True)
    f.rect((45,125,400,300),'32份独立状态\nphase / frequency\nADSR / velocity / note',28);f.arrow((400,210),(520,210));f.rect((520,125,970,300),'帧界锁存控制量\n4路共享音高/表情计算\n32上下文 / 8时钟更新',28);f.arrow((970,210),(1090,210));f.rect((1090,125,1460,300),'逐声部取样累加\n限幅 / 效果 / I²S\n每帧按时完成',28)
    f.text(750,375,'名义采样帧：12.288 MHz / 48 kHz = 256时钟',29)
    f.rect((70,430,1430,520),fill='#eeeeee');f.rect((70,430,1265,520),'最坏225时钟：真实32声部调度与输出',28);f.text(1340,475,'余量\n31时钟',23)
    f.text(750,625,'共享的是运算单元，32声部的相位、音高与包络状态各自保留。\n硬件逐样本合成；曲谱ROM只存音符事件，不存歌曲PCM波形。',29)
    f.save('04_voice_pipeline')
    f=Figure(1500,780);f.text(750,40,'本地录音成曲与简谱识别流程',34,bold=True)
    for x,t in [(30,'录音 / 导入音频\n解码、重采样'),(535,'声学证据融合\n周期性 + CREPE Tiny'),(1040,'事件解码与校核\n音高 / 八度 / 停顿')]:f.rect((x,130,x+430,270),t,27)
    f.arrow((460,200),(535,200));f.arrow((965,200),(1040,200));f.arrow((1255,270),(1255,380))
    for x,t in [(30,'曲谱照片\n裁切 / 分行 / 符号候选'),(535,'本地OCR + 数字符号MLP\n音符点线 / 节拍解析'),(1040,'统一音符事件\nMIDI / 时值 / 休止')]:f.rect((x,380,x+430,520),t,27)
    f.arrow((460,450),(535,450));f.arrow((965,450),(1040,450));f.arrow((1255,520),(1255,610));f.rect((430,610,1470,735),'手机试听与核对 → 分段打包 / CRC → 蓝牙 → FPGA合成或灯光指引\nFPGA识谱模式：仅数字分类推理下沉，其余图像/节奏解析仍由手机完成',26)
    f.save('05_recognition')
    f=Figure(1500,680);f.text(750,40,'模块资源对照：压力表情计算',34,bold=True)
    for i,(label,old,new,total) in enumerate([('LUT',7346,1816,8000),('ALU',1426,274,8000),('寄存器',1172,917,8000)]):
        y=140+i*145;f.text(150,y+38,label,29);f.rect((280,y,280+old/8000*1020,y+35),fill='#777777');f.rect((280,y+48,280+new/8000*1020,y+83),fill='#dddddd');f.text(1310,y+15,str(old),27);f.text(1310,y+65,str(new),27)
    f.text(750,610,'深色：优化前；浅色：优化后。仅此模块，非整片FPGA。\n65,536组合、30,000周期对照通过；包含声部服务时限检查。',26)
    f.save('06_resources')
    f=Figure(1500,500);f.text(750,40,'完成度与实测补录位置',34,bold=True)
    f.rect((40,105,710,410),'整机正面实拍替换区\n当前未获得可读取的最终整机照片\n请将原图放入报告可编辑源/photos\n后续替换Word内本图',27,fill='#f5f5f5');f.rect((790,105,1460,410),'整机45°实拍替换区\n此处不是实物照片\n不使用概念渲染图代替实拍\n第6项独立照片材料按要求未另行制作',27,fill='#f5f5f5')
    f.save('07_photo_slots')
    src=ROOT/'app/android/app/src/test/snapshots/images'
    candidates=['ProductSnapshotsTest_connectedPerformance','ProductSnapshotsTest_library','ProductSnapshotsTest_creation','HandpanSnapshotsTest_sound']
    canvas=Image.new('RGB',(1500,990),'white');d=ImageDraw.Draw(canvas)
    for i,(term,title) in enumerate(zip(candidates,['演奏','曲谱书架','创作','音色'])):
        p=next(src.glob('*'+term+'.png'));im=Image.open(p).convert('RGB');im.thumbnail((335,880));x=35+i*375;canvas.paste(im,(x+(335-im.width)//2,80));d.text((x+165,35),title,font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',30),fill='black',anchor='mm')
    canvas.save(AS/'08_app.png')
    scope=ROOT/'output/contest_lab_20261103/界面预览/横屏.png'
    if scope.exists():shutil.copy2(scope,AS/'09_scope.png')
    cad=ROOT/'output/engineering_upgrade_20261028/声芯_技术方案与工程图包_2026-10-28/cad/assembly.png'
    if cad.exists():shutil.copy2(cad,AS/'10_cad_concept.png')

C=[];LIMIT={}
def p(t,style='SCBody'):C.append(dict(kind='p',text=t,style=style))
def hd(t,level=1,page=False):C.append(dict(kind='p',text=t,style=f'SC{level}',page=page))
def para(t,limit=None,label=''):
    p(t)
    if limit:LIMIT[label]={'limit':limit,'count':len(''.join(t.split())),'text':t}
def fig(name,caption):C.append(dict(kind='image',name=name,width=h.WIDTH));p(caption,'SCCaption')
def table(headers,rows,widths=None):C.append(dict(kind='table',headers=headers,rows=rows,widths=widths))

def content():
    p('声芯乐动：基于FPGA的多维交互实时合成乐器','SCTitle')
    p('技术报告｜B713固件 · Android 0.24｜2026年11月3日','SCMeta')
    hd('摘要')
    para('本作品围绕可敲击、可引导、可创作的电子乐器，设计七路压力触感输入、滑杆变调、旋钮表情控制、五键操作及手机联动系统。音频核心采用纯HDL固定点实现，在FPGA内逐样本完成32份独立声部的音高、相位、ADSR包络与混音计算，经I²S驱动功放；口琴、二胡和两种手碟音色均为算法合成。回声、合唱、混响与OLED/灯光反馈构成完整演奏链路。为缓解资源紧张，采用帧界快照和共享流水线，在保留独立声部状态的同时减少重复运算，并以周期对照检查输出及服务时限。压力处理将快速起音、峰值力度和持续表情分离，兼顾响应与稳定。手机端内置录音旋律识别、简谱符号识别及曲谱管理，通过统一音符事件协议连接自动演奏和脱机指引，不依赖外部识别API。B713已完成布局布线、相关RTL回归及SRAM下载读回，App完成自动化测试。32声部、资源与延迟结果在本文中分别注明数字验证条件；真实端到端延迟、抖动、声学效果和最终整机照片仍需实验室补证。',800,'摘要')
    hd('第一部分 作品概述',page=True)
    hd('1.1 功能与特性',2)
    para('七片压力传感片提供选音、触发及力度输入，默认同一音区七个自然音，可调整键位顺序并切换音区。滑杆实现连续变调，EC11调节音量及颤音深度，五颗按钮完成音区、音色、曲目及播放操作。支持32声部实时合成、四种算法音色、三种空间效果、两首内置曲目、自动演奏与脱机灯光指引；指引自动切换音区。OLED显示配置、力度或歌词，蓝牙App提供虚拟琴键、曲谱书架、录音成曲、本地简谱识别、波形/频谱/XY分析及设备录音回传。',400,'1.1')
    hd('1.2 应用范围',2)
    para('面向电子乐器原型、音乐交互展示、创作体验与FPGA教学验证。实体敲击适合现场体验，手机用于曲谱准备、参数设置和可视化，脱机模式不要求手机持续在线。录音成曲优先处理单旋律人声或单乐器，复杂伴奏及和声不在可靠保证范围内。曲谱识别面向清晰简谱，识别结果需经过试听与拍号检查后下发。仪器化验证入口用于展示独立声部、采样率、运算吞吐量及输入到输出的响应。',400,'1.2')
    hd('1.3 主要技术特点',2)
    para('采用32上下文状态与共享定点算术分离的架构，音频时钟12.288MHz、名义采样率48kHz，每帧256时钟。帧界锁存表情参数并以4路运算流水线处理32声部，避免参数更新穿透和重复乘法。压力检测由快速可信起音、窗口峰值和持续压力三条作用路径组成，音色谐波与音量分开调节。手机将声学或图像识别结果转换为同一种带音高、时值、休止的事件格式，FPGA执行合成、自动音区和灯光目标推进。FFT、波形与延迟XY分析直接观察合成输出；控制与大块数据使用有边界的串口传输。',400,'1.3')
    hd('1.4 主要性能指标',2)
    para('下表区分设计规格、已完成数字验证和待测实物指标；未将仿真时间当作实测延迟。',200,'1.4')
    table(['项目','当前结果及条件','证据状态'],[
        ['合成能力','32声部独立相位、音高、包络；48kHz名义采样','RTL/I²S数字验证'],['运算时限','最坏225/256音频时钟，保留31时钟','32声部数字验证'],['采样数据','16bit；单声道复制至I²S左右槽','代码及RTL'],['输入响应','强阶跃非零PCM≤1.300ms；弱阶跃≤2.940ms','各70次仿真；非实测'],['时序收敛','Setup/Hold违例0；最小裕量27.285/0.065ns','B713布局布线'],['实物≤5ms与抖动','统一阈值、仪器时基下测量，待补','尚不可宣称通过']],[1500,4750,2056])
    hd('1.5 主要创新点',2)
    para('①状态独立、算术共享的帧一致表情流水线：保留32声部，在本模块LUT由7346降至1816。②将可信起音、峰值力度和持续压力分离，减少等待峰值与误触发的矛盾。③建立识别结果到实体七键的统一事件桥，结合自动音区、休止及指引节奏反馈。创新定位为具体架构、判据与系统实现，既有DDS、ADSR和开源识别模型不作为本项目首创。',200,'1.5')
    hd('1.6 设计过程',2)
    para('先建立压力采样与单音链路，再扩展多声部、I²S与音效；随后统一实体面板、OLED、蓝牙和App状态。根据资源瓶颈引入共享流水线，按独立参考与真实服务时限回归；根据听感反馈迭代起音与曲谱事件。最终冻结B713及0.24源文件、配置、验证日志和哈希，实物数据以同一版本补录。',200,'1.6')
    hd('第二部分 系统组成及功能说明',page=True)
    hd('2.1 整体介绍',2);para('系统由触感与面板输入、FPGA合成与交互、I²S功放输出、OLED/灯光反馈、蓝牙及Android App组成。FPGA是演奏状态与音频时序的执行中心，手机负责创作、曲谱准备和交互显示。设备内置曲目及灯光指引可脱机运行。')
    fig('01_system.png','图1 系统总体关系与实时/非实时任务分工')
    hd('2.2 硬件系统介绍',2);hd('2.2.1 硬件总体及接口',3)
    para('主控为Tang Mega 60K与NEO Dock，使用GW5AT-60B器件；MCP3208提供七路压力和一路滑杆采样。MAX98357A接收标准I²S驱动扬声器，OLED为128×64 I²C模块，蓝牙串口模块负责手机链路。信号逻辑按已核对约束使用3.3V；电源输入与稳压不允许通过GPIO互相供电。正式接线以冻结CST、接线表与实板方向三者一致为准。')
    table(['模块','输入/输出','设计作用'],[['MCP3208','AI0…AI6压力，AI7滑杆；SPI','选音、力度、连续变调'],['EC11与五键','S1/S2/KEY；K1…K5低有效','音量、颤音、音区、音色及曲目'],['MAX98357A','dac_bclk/lrclk/din；SPK+/−','I²S电声输出'],['OLED与LED','oled_scl/sda；pad_led_o[0…6]','中文配置、歌词、力度、节奏指引'],['蓝牙串口','ble_uart_tx/rx；共地','设置、琴键事件、曲谱与分析传输']],[1750,3550,3006])
    hd('2.2.2 机械设计与装配',3)
    para('外观采用七触感区、右侧操作区及可维护底层电路的分层思路，四个普通按钮加一个带灯按钮，滑杆与旋钮保留独立操作空间。下图为已有参数化装配规划模型，并非根据最终实物完成的逆向模型；孔径、受力支撑、线束弯曲半径和固定柱位置应在实际装配后复核。最终整机外观照片见3.1替换区。')
    if (AS/'10_cad_concept.png').exists():fig('10_cad_concept.png','图2 参数化装配规划（概念CAD；不是最终加工或实拍证据）')
    hd('2.2.3 电路原理与信号说明',3)
    para('每路压力片与4.7kΩ、10kΩ形成独立分压：3.3V→4.7kΩ→压力片→AI节点→10kΩ→GND。压力片电阻减小时AI电压升高，七个AI节点不能并联。滑杆两端接ADC参考供电和公共地，滑动端接AI7。五键使用常开触点，信号由上拉保持高电平，按下接地；开关回路与带灯按钮灯环是两组独立线路。')
    fig('02_input_circuit.png','图3 七路压力分压、滑杆与低有效触点原理图（每片单独复用一套）')
    para('七颗普通LED各串联1kΩ后接对应GPIO与公共地。OLED与蓝牙必须和FPGA共地；串口TX/RX交叉。OLED的SCL/SDA上拉只到3.3V。MAX的SD通过10kΩ上拉，SPK+/SPK−只接扬声器两端，不把负输出当作公共地。最终灯环限流需依据实际模块电流，不用减小电阻代替驱动能力核算。')
    fig('03_output_circuit.png','图4 I²S功放、I²C显示与LED接口原理图；电源分轨与公共地条件')
    table(['J13位置（沿用已确认A/B方向）','冻结信号名','用途'],[['A8、B8、A9、B9、B11、A12、B12','pad_led_o[0]…[6]','七颗演奏LED，顺序与CST核对'],['A10 / A11','oled_scl / oled_sda','OLED时钟 / 数据'],['A13 / B13 / A14 / B14 / A16','panel_bank_down/up/timbre/song/play','K1 / K2 / K3 / K4 / K5'],['B10','guide_button_led_o','K5播放灯环，须独立限流'],['B6','GND','公共地；上电前导通核对']],[3400,3000,1906])
    para('表内排位只沿用本项目既定朝向，不重新从空闲针开始计数。PMOD的ADC/I²S/EC11接线以及29个FPGA封装管脚均随代码包保存；任何改针须同步修改CST和接线表。',None)
    hd('2.3 软件与HDL系统介绍',2);hd('2.3.1 总体软件及主要界面',3)
    para('Android原生App按演奏、曲谱、创作、音色和设备五个主区组织。演奏区含七键/十二音琴键、力度、颤音和临时滑音；曲谱区提供内置与下载书架、搜索及播放/指引；创作区处理录音成曲和本地简谱识别；音色区管理四种算法音色、音效和场景；设备区负责连接、工具与配置。蓝牙连接后可直接控制，不要求通过机身K4/K5额外授权。')
    fig('08_app.png','图5 当前原生App界面渲染（自动化快照，不作为真实手机现场照片）')
    if (AS/'09_scope.png').exists():fig('09_scope.png','图6 横屏分析工具渲染：波形/频谱/XY、时基、增益与触发操作')
    para('录音、相机与本地文件权限只在对应操作时使用。识别模型及OCR资源内置，不要求配置API密钥。初次安装后核心识别可离线运行；曲谱目录的在线更新属于独立可选路径。目录含30首60～120秒公版旋律编配，下载结果进入App书架。')
    hd('2.3.2 核心功能分解与输入输出',3)
    table(['模块','关键输入 → 输出','设计要点'],[['压力事件','ADC样本→起音/峰值/持续压力','自动基线；早起音与峰值回退；滞回防抖'],['声部分配与合成','note/velocity→32状态→PCM','独立相位/音高/ADSR；共享计算'],['音效与输出','PCM+效果参数→I²S','延迟线、混合比例、平滑与限幅'],['曲谱与面板','事件流+K1…K5→播放/指引/歌词','休止与进度一致；自动音区；退出恢复'],['分析与录音','最终PCM→FFT/波形/XY/ADPCM','不阻塞音频时限；分块传输与CRC'],['手机创作','音频/谱图→统一事件→设备','本地模型推理；可试听核对后下发']],[1700,3300,3306])
    fig('04_voice_pipeline.png','图7 32声部独立状态与共享算术的帧级组织')
    para('共享流水线优化的是运算资源，不把32声部折算成32个固定音高。每份声部都有独立相位累加器、频率参数、包络阶段及力度；可同时发声、释放、重触发和变调。32声部运算在同一音频帧内完成，I²S按固定节拍输出。音区/自然音映射属于交互层，和可并发声部数是不同概念。')
    para('压力路径不等待完整峰值后才开始发声：可信早样本满足条件时先起音，窗口峰值随后更新力度；置信度不足时回退到稳定峰值路径。持续压力调节表情，避免一次敲击的峰值被噪声反复改写。七路目前使用统一曲线；达到满格的阈值需结合实物最大电压再确认，不能仅靠画满柱子说明实际力度一致。')
    para('ADSR由真实的Attack、Decay、Sustain、Release阶段组成，当前音色使用固定预设；口琴保留较柔和起音，二胡包含渐入颤音及谐波纹理。两种手碟使用不同模态与失真/阻尼配置。合成音色为工程近似，真实乐器相似度及主观听感仍需听测，不能由谐波图替代。')
    fig('05_recognition.png','图8 手机内置识别到实体演奏/指引的统一事件桥')
    para('录音成曲融合周期性与神经基频证据，进行八度候选校核、主音稳定区间选择、碎音抑制和句间停顿整理；保留起始时间及持续时长而非仅输出音名。长录音按约28秒带重叠窗口处理，当前输入上限180秒，控制内存峰值。CREPE Tiny/ONNX等基础模型为开源基础，不声称从零训练；自研部分在信号预处理、证据融合、事件解码、七键映射与系统协议。没有经独立标注测试集证明99%音准。')
    para('简谱识别使用手机本地OCR与数字MLP，识别数字、八度点、时值线、休止及版面顺序，再进行拍号与小节检查。手机模式完成全流程；FPGA协同模式仅将候选数字分类下沉为定点MLP运算，分行、时值与结构解析仍在手机。遇到遮挡、复杂反复记号或不确定时值，应显示可检查结果，不用无声失败掩盖识别错误。')
    para('设备录音保存最终合成PCM，经127阶FIR抽取到8kHz并编码为IMA ADPCM，最长8秒，分块附CRC16回传为手机WAV。在线演奏采用最新事件优先与字节预算，避免旧按键积压；9600波特蓝牙不属于5ms音频实时路径。')
    hd('第三部分 完成情况及性能参数',page=True)
    hd('3.1 整体完成情况',2)
    para('已形成完整FPGA工程、Android工程、曲谱数据、模型资源、验证脚本及技术资料。B713于2026年11月3日完成SRAM下载与UserCode读回匹配；记录显示未写Flash，真实音频验收仍待补。当前交付以冻结源和日志为准，不能把历史其他版本的听感确认外推为B713全部通过。')
    fig('07_photo_slots.png','图9 最终整机实拍保留位置（待补；本图明确不作为实物证据）')
    hd('3.2 分项完成情况',2)
    table(['子项','已完成工作','仍需补证'],[['硬件与面板','采样、输出、OLED、蓝牙、七灯、五键及旋钮链路已有工程与调试历史','最终供电、线束、七路满力度与整机照片'],['32声部与时序','独立释放/重触发/变调、实际I²S数字谱峰检查、PNR收敛','实机Fs、32个谱峰与持续运行'],['App与识别','331项测试：323通过、8跳过、0失败/错误；本地资源已打包','目标手机长录音、图片集、实际蓝牙联调'],['指引与显示','节奏提示、休止、自动音区、歌词位置及灯模式恢复回归','整首脱机指引与OLED现场视频'],['效果与分析','回声/合唱/混响及波形/FFT/延迟XY实现','声学与示波器同步测量']],[1700,3600,3006])
    hd('3.3 主要功能、性能及证据',2)
    hd('3.3.1 资源与可复现优化',3)
    table(['B713资源','使用 / 总量','占用'],[['Logic','48726 / 59904','82%'],['CLS','28523 / 29952','96%'],['寄存器','18388 / 60780','31%'],['BSRAM','114 / 118','97%'],['DSP','82 / 118','70%']],[2500,3500,2306])
    para('布局布线采用place=4、route=0，Setup/Hold均无违例；时序裕量不代表器件温升、电源扰动及全工况下已经测试。CLS与BSRAM剩余空间较少，后续优先进行状态/表存储复用、数据宽度审计和模块时分复用，而非无约束增加功能。')
    fig('06_resources.png','图10 压力表情模块优化前后资源对照（LUT下降75.3%）')
    para('资源对照来自同一功能模块优化前后的独立综合；另以65,536组输入组合和30,000周期时序对照验证帧输出及每个声部服务时限。它支持“减少重复计算”的结论，不等于全片资源下降75.3%，也不等于主观音质不变已由听测证明。')
    hd('3.3.2 延迟与音频吞吐量',3)
    table(['仿真刺激/观测','70次强阶跃1000→2200','70次弱阶跃1000→1320'],[['起音触发最坏','0.6602ms','1.0834ms'],['第一非零PCM最坏','1.2994ms','2.9396ms'],['规定振幅门限最坏','|PCM|≥64：3.3619ms','|PCM|≥8：4.4356ms'],['限制','数字激励不含机械/模拟链路','固定|PCM|≥64未通过5ms']],[2900,2700,2706])
    para('弱信号在固定绝对门限64下未满足5ms，必须保留这一限制，不能通过改变门限宣称所有力度均通过。实验室应同时记录相对稳态门限、固定绝对门限和首个有效数字样本，标明起点为压力片分压节点、终点为I²S/功放差分输出或声学输出；多次采样报告最小、均值、最大、P95和峰峰抖动。App蓝牙延迟单独说明，不纳入FPGA硬件链路的5ms结论。')
    para('32声部吞吐验证按“实际同时可听见的独立声部数×实测采样率”计算。若实机确认32声部和48,000Hz，结果为1,536,000声部样本/秒；目前48kHz为名义规格。数字验证中32个不同频率的I²S输出可区分，且独立释放、重触发与重新调音均通过。左右复制输出、谐波数或内部时钟频率不重复计为声部吞吐。')
    hd('3.3.3 可视化及应用验证',3)
    para('FPGA分析链含1024点FFT及32个频带、波形最小/最大值摘要和延迟64样本构造的XY图。XY来自同一单声道的延迟配对，不能宣称为两路独立模拟输入的相位测量仪。App工具提供音频输入、硬件摘要和诊断等不同来源，必须显示来源、实际采样率与单位。手机音频分析采用独立工作线程及最新帧邮箱，避免积压；显示刷新率及真实延迟仍需在目标手机测量。')
    para('已有七类受影响RTL回归通过：节奏提示、ADSR、真实顶层指引灯路由、工具协议、分块传输、手碟控制、手碟音频核。Android 331项测试中8项为需显式启用的外部/人工条件项而跳过，不写成331项全通过。报告与源代码包保存对应日志、源哈希和版本号，测试环境及跳过项应在复现时核对。')
    table(['实验室补录项','推荐数据与证据','填写位'],[['电气完整性','各供电轨空载/负载电压，七路AI峰值，共地与接线图','待实测'],['端到端时延','七路、弱/中/强至少各30次，示波器CSV和截图','待实测'],['独立32声部','Fs/BCLK/LRCLK，32谱峰，独立释放前后录音/CSV','待实测'],['表情与音效','三维度独立变化；干声/湿声同电平对照','待实测'],['产品全流程','冷启动、五键、OLED、蓝牙、下载/识别/指引、退出恢复','待实测']],[2000,5100,1206])
    hd('第四部分 总结')
    hd('4.1 作品可扩展性',2)
    para('体系按输入事件、独立声部、音频效果、曲谱事件和显示通信解耦，便于替换传感器、扩展音色或增加曲谱。当前主要瓶颈是CLS和BSRAM；优先压缩字库/曲谱表、复用延迟存储、降低非关键状态位宽，并以相同激励复核时限及误差。识别端可更换基频观察器或数字分类模型，统一事件格式和FPGA演奏核心无需随模型重写。后续训练必须使用具有明确许可和独立测试划分的数据，并公开训练设置、量化误差与失败样例；不以更换名称主张开源基础为原创。',300,'4.1')
    hd('4.2 总结与反思',2)
    para('本项目的主要收获在于把“能发声”推进到可检查的实时系统：独立声部状态、固定音频时限和完整输入输出链路必须同时成立。共享算术的价值应由资源对照及服务时限证明，识别模块的价值应由未参与调参的样本和实际可演奏事件证明，界面与外观不能替代这些证据。\n在实现中，音色自然度、力度一致性、句间停顿和蓝牙事件积压往往无法用单个测试覆盖，需要数字参考、自动回归和实物听测相互补充。保留失败结果比只保留成功截图更有助于解释系统边界，例如弱阶跃固定门限下尚未满足5ms。\n当前版本已具备提交材料的结构与源码基础，仍需把最终整机照片和实验室测量补入第三部分，特别是时延分布、峰峰抖动、32声部频谱与实际Fs。在这些数据得到前，本文坚持使用“数字验证通过、实物待测”的表达。后续应先冻结可稳定演示的功能，再以相同版本完成测量和修改回归，避免材料与现场工程不一致。',1000,'4.2')
    hd('第五部分 参考文献',page=True)
    refs=[
      '[1] 高云半导体. 2026年FPGA创新设计竞赛：赛题二[EB/OL]. https://www.gowinsemi.com.cn/university/match2026, 访问日期2026-11-03.',
      '[2] 竞赛组委会. 2026FPGA创新设计赛道作品上传要求[Z]. 2026.（随本次任务提供的提交说明）',
      '[3] 竞赛组委会. 技术文档模板[Z]. 2026.（随本次任务提供的Word模板）',
      '[4] Sipeed. Tang Mega 60K / NEO Dock硬件资料与原理图[EB/OL]. https://wiki.sipeed.com/hardware/zh/tang/tang-mega-60k/mega-60k.html, 访问日期2026-11-03.',
      '[5] Microchip. MCP3204/3208: 12-Bit A/D Converters with SPI Serial Interface[EB/OL]. https://www.microchip.com/en-us/product/mcp3208, 访问日期2026-11-03.',
      '[6] Analog Devices. MAX98357A/MAX98357B: PCM Input Class D Audio Power Amplifiers[EB/OL]. https://www.analog.com/en/products/max98357a.html, 访问日期2026-11-03.',
      '[7] KIM J W, SALAMON J, LI P, et al. CREPE: A Convolutional Representation for Pitch Estimation[C]. ICASSP, 2018: 161-165. https://arxiv.org/abs/1802.06182.',
      '[8] MORRISON M. torchcrepe[CP/OL]. https://github.com/maxrmorrison/torchcrepe. 基频观察器开源基础，许可见源码包第三方声明.',
      '[9] Tesseract.js contributors. Tesseract.js[CP/OL]. https://github.com/naptha/tesseract.js. 本地OCR基础与随包许可.',
      '[10] Microsoft. ONNX Runtime[CP/OL]. https://github.com/microsoft/onnxruntime. 手机端模型推理运行时.',
      '[11] 本项目. B713冻结源、布局布线报告、RTL/Android测试记录及SRAM下载读回记录[DS]. 2026-11-03. 随代码包evidence目录保存.'
    ]
    for r in refs:p(r,'SCRef')

def styles(root):
    h.add_styles_original(root)
    for s in root:
        sid=s.get('{'+h.W+'}styleId','')
        if not sid.startswith('SC'):continue
        pp=s.find('w:pPr',h.NS);rp=s.find('w:rPr',h.NS)
        size={'SCBody':24,'SCTitle':36,'SCMeta':20,'SC1':28,'SC2':24,'SC3':24,'SCCaption':20,'SCSmall':21,'SCRef':22,'SCTable':21}.get(sid,24)
        for k in ['sz','szCs']:rp.find('w:'+k,h.NS).set('{'+h.W+'}val',str(size))
        if sid=='SCBody':
            pp.find('w:spacing',h.NS).set('{'+h.W+'}line','360')
            pp.find('w:ind',h.NS).set('{'+h.W+'}firstLine','480')
        if sid=='SC1':pp.find('w:spacing',h.NS).set('{'+h.W+'}before','160')

def main():
    figures();content()
    assert all(x['count']<=x['limit'] for x in LIMIT.values()),LIMIT
    (OUT/'报告可编辑源/正文内容.json').write_text(json.dumps(C,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'报告可编辑源/字数核对.json').write_text(json.dumps(LIMIT,ensure_ascii=False,indent=2),encoding='utf-8')
    h.CONTENT=C;h.add_styles_original=h.add_styles;h.add_styles=styles
    count=h.write_docx()
    # Correct helper's inherited draft metadata and use explicit anonymous project identity.
    from zipfile import ZipFile,ZIP_DEFLATED
    with ZipFile(h.DOCX) as z:parts={n:z.read(n) for n in z.namelist()}
    core=E.fromstring(parts['docProps/core.xml'])
    for n in core:
        if E.QName(n).localname in ['title','subject','description','keywords']:n.text='声芯乐动FPGA多维交互实时合成乐器技术报告'
    parts['docProps/core.xml']=E.tostring(core,xml_declaration=True,encoding='UTF-8',standalone=True)
    with ZipFile(h.DOCX,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    shutil.copy2(__file__,OUT/'报告可编辑源'/Path(__file__).name)
    shutil.copy2(ROOT/'scripts/fill_contest_technical_document_20261028.py',OUT/'报告可编辑源/template_ooxml_helper.py')
    (OUT/'报告可编辑源/photos').mkdir(exist_ok=True)
    (OUT/'报告可编辑源/修改说明.md').write_text('直接修改上一级DOCX后用Word导出PDF即可。正文内容.json和figures/*.svg可单独编辑；重新运行构建会覆盖自动生成的DOCX，因此手工修改请另存为修订版。最终整机照片放在photos目录并替换图9。第三部分的待实测表格须填写仪器实测结果。原始模板未修改。',encoding='utf-8')
    print(json.dumps({'docx':str(h.DOCX),'images':count,'bounded_sections':{k:v['count'] for k,v in LIMIT.items()}},ensure_ascii=False))

if __name__=='__main__':main()
