"""Fill an anonymous contest template while preserving its package and header.

The original file is never written. Figures are engineering schematics and
explicitly labelled simulations/designs, not manufactured evidence photographs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\YOUR_USER\xwechat_files\wxid_nc4c6jcrry7e22_2653\msg\file\2026-10\技术文档模板.docx")
OUT = ROOT / "output/technical_document_20261028"
ASSETS = OUT / "assets"
OUT.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(exist_ok=True)
DOCX = OUT / "声芯_竞赛技术文档_试填版_2026-10-28.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS = {"w": W, "r": R}
WIDTH = 8306  # User template: A4, 1800 twips left/right margins.
CONTENT: list[dict] = []
LIMITED: dict[str, tuple[str, int]] = {}


def font(size, bold=False):
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / ("msyhbd.ttc" if bold else "msyh.ttc")), size)


def label(draw, xy, text, size=30, bold=False, anchor="mm", fill="black"):
    draw.multiline_text(xy, text, font=font(size, bold), fill=fill, anchor=anchor,
                        align="center", spacing=9, stroke_width=0)


def box(draw, bounds, text, size=29, bold=False):
    draw.rounded_rectangle(bounds, radius=10, fill="white", outline="black", width=3)
    x0, y0, x1, y1 = bounds
    label(draw, ((x0+x1)/2, (y0+y1)/2), text, size, bold)


def arrow(draw, p1, p2, width=3):
    draw.line([p1, p2], fill="black", width=width)
    angle = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
    tip = [p2, (p2[0]-16*math.cos(angle-.45), p2[1]-16*math.sin(angle-.45)),
           (p2[0]-16*math.cos(angle+.45), p2[1]-16*math.sin(angle+.45))]
    draw.polygon(tip, fill="black")


def save(im, name):
    p = ASSETS / name
    im.save(p)
    return p


def figures():
    im=Image.new("RGB", (1600, 940), "white");d=ImageDraw.Draw(im)
    box(d,(20,100,320,265),"7路压力片 + 滑杆\nMCP3208 / 8通道ADC",27)
    box(d,(20,330,320,470),"五颗功能键 / EC11\n音区、音色、表情",28)
    box(d,(20,555,320,710),"手机App ↔ JDY-23\nBLE / UART控制",28)
    d.rounded_rectangle((410,35,1165,840),radius=12,outline="black",width=4)
    label(d,(787,78),"FPGA：实时运算与统一状态",35,True)
    box(d,(460,130,1115,250),"采样识别 → 输入仲裁 → 32声部分配",30)
    box(d,(460,310,1115,450),"独立相位 / ADSR / 力度音色\n128拍完成32声部逐样本运算",30)
    box(d,(460,510,1115,625),"回声 / 合唱 / 混响 → 总音量",31)
    box(d,(460,685,1115,795),"脱机曲目 / 严格指引 / 逐字词时",29)
    arrow(d,(320,182),(460,182));arrow(d,(320,400),(410,400))
    arrow(d,(320,632),(410,632));arrow(d,(788,250),(788,310));arrow(d,(788,450),(788,510))
    box(d,(1260,140,1580,295),"标准I²S → MAX功放\n扬声器（参赛路径）",27)
    box(d,(1260,370,1580,510),"中文OLED / 七灯\n配置、力度、歌词",29)
    box(d,(1260,600,1580,745),"PT8211 → 耳机\n独立串行器（恢复版）",27)
    d.line([(1115,565),(1205,565),(1205,218)],fill="black",width=3);arrow(d,(1205,218),(1260,218))
    arrow(d,(1165,440),(1260,440))
    d.line([(1205,565),(1205,672)],fill="black",width=3);arrow(d,(1205,672),(1260,672))
    label(d,(800,905),"谱面 / MIDI / 人声仅用于电脑端整理音符；设备不存储、回放歌曲录音",26)
    save(im,"system.png")

    im=Image.new("RGB",(1600,900),"white");d=ImageDraw.Draw(im)
    d.rectangle((55,70,1545,570),outline="black",width=4)
    label(d,(145,30),"顶视图",30,True)
    for i in range(7):
        x=145+i*142;y=200-85*math.sin(i*math.pi/6)
        d.rounded_rectangle((x-47,y-43,x+47,y+43),12,outline="black",width=3)
        label(d,(x,y),str(i+1),28,True)
        d.ellipse((x-10,y+58,x+10,y+78),outline="black",width=3)
    label(d,(580,335),"沿用已完成的七片敲击面\n单色LED在旁侧透光点显示",30)
    box(d,(1150,115,1490,235),"OLED观察窗",28)
    d.rectangle((1180,285,1230,430),outline="black",width=3)
    label(d,(1330,365),"滑杆 / EC11",27)
    d.ellipse((1300,285,1380,365),outline="black",width=3)
    for i,t in enumerate(["−","+","音色","曲目","开始"]):
        x=1110+i*83;d.ellipse((x,470,x+62,532),outline="black",width=2);label(d,(x+31,501),t,21)
    label(d,(185,620),"侧视剖面",30,True)
    d.rectangle((55,665,1545,735),outline="black",width=3)
    d.rectangle((55,815,1545,840),outline="black",width=3)
    for x in [110,1490]:d.rectangle((x,735,x+12,815),outline="black",width=3)
    for rect,text in [((185,750,570,800),"FPGA / 可拆支柱"),((620,750,970,800),"ADC / 接口固定"),((1020,750,1400,800),"电源 / 音频分区")]:box(d,rect,text,25)
    label(d,(800,880),"结构设计示意；最终开孔、尺寸与模块高度须按实物复核",25)
    save(im,"mechanical.png")

    im=Image.new("RGB",(1600,880),"white");d=ImageDraw.Draw(im)
    label(d,(385,35),"单路压力分压",32,True)
    x=390
    label(d,(x,100),"ADC模块3V3输出",28)
    d.line((x,130,x,170),fill="black",width=3)
    d.rectangle((x-35,170,x+35,245),outline="black",width=3);label(d,(600,207),"4.7 kΩ固定电阻",26)
    d.line((x,245,x,285),fill="black",width=3)
    d.rectangle((x-45,285,x+45,370),outline="black",width=3);label(d,(600,325),"FSR压力片",26)
    d.line((x,370,x,480),fill="black",width=3);d.ellipse((x-7,405,x+7,419),fill="black")
    arrow(d,(x,412),(720,412));label(d,(640,375),"AI0～AI6之一",26)
    d.rectangle((x-35,480,x+35,555),outline="black",width=3);label(d,(600,517),"10 kΩ下拉电阻",26)
    d.line((x,555,x,600),fill="black",width=3)
    for n in range(3):d.line((x-40+n*10,600+n*10,x+40-n*10,600+n*10),fill="black",width=3)
    label(d,(x,668),"ADC GND",28)
    label(d,(x,755),"AI7滑杆：REF → 电阻轨 → GND\n中间滑动端接AI7",26)
    label(d,(1170,35),"LED与功能按键",32,True)
    label(d,(1170,125),"每颗LED均需独立限流",27)
    arrow(d,(900,215),(1000,215));label(d,(920,175),"GPIO",25)
    d.rectangle((1000,190,1100,240),outline="black",width=3);label(d,(1050,280),"1 kΩ",26)
    d.line((1100,215,1160,215),fill="black",width=3)
    d.polygon([(1160,185),(1160,245),(1220,215)],outline="black",width=3)
    d.line((1220,183,1220,247),fill="black",width=3);d.line((1220,215,1450,215),fill="black",width=3)
    arrow(d,(1187,178),(1227,135),2);arrow(d,(1210,185),(1250,142),2)
    label(d,(1400,270),"GND",26)
    label(d,(1190,390),"按键GPIO（内部上拉至3.3V）",26)
    d.line((930,470,1090,470),fill="black",width=3);d.ellipse((1090,462,1106,478),outline="black",width=3)
    d.line((1105,468,1195,425),fill="black",width=3);d.ellipse((1200,462,1216,478),outline="black",width=3)
    d.line((1216,470,1450,470),fill="black",width=3);label(d,(1400,520),"GND",26)
    label(d,(1180,595),"常开、自复位；按下读0\n同步后消抖，再识别短按/长按",27)
    label(d,(1170,755),"各模块共地；不同稳压输出不可直接并联\n扬声器OUT−不接公共地",25)
    save(im,"circuits.png")

    im=Image.new("RGB",(1600,900),"white");d=ImageDraw.Draw(im)
    cols=[(40,750),(850,1560)]
    headings=["实体输入到声音","手机快照到声音"]
    steps=[
        ["SPI扫描：channel / value / valid","校准与阈值：strike / velocity","输入仲裁：实体优先、手机持音隔离","32槽分配：note / gate / velocity","逐样本合成 → 音效 → 音频输出"],
        ["按下/松开：held / attacks / velocity","覆盖未发送旧状态；最短16 ms发送","BLE透传 → 9600 UART → CRC校验","实时快照旁路；过期起音不补播","FPGA执行；STATE / 遥测回传"]]
    for j,(left,right) in enumerate(cols):
        label(d,((left+right)/2,45),headings[j],33,True)
        for i,t in enumerate(steps[j]):
            y=100+i*140;box(d,(left,y,right,y+100),t,27)
            if i<4:arrow(d,((left+right)/2,y+100),((left+right)/2,y+140))
    label(d,(800,855),"两条链路共用声源和设备状态；手机通信延迟须与本地演奏分别统计",27)
    save(im,"control_flow.png")

    im=Image.new("RGB",(1600,840),"white");d=ImageDraw.Draw(im)
    label(d,(800,40),"一份曲目事件，驱动两种模式",34,True)
    box(d,(440,100,1160,210),"事件ROM：音高 / 时值 / 休止 / 连音标志",28)
    arrow(d,(620,210),(380,295));arrow(d,(980,210),(1220,295))
    box(d,(70,295,690,415),"整曲播放：按毫秒时钟取下一事件",28)
    box(d,(910,295,1530,415),"脱机指引：自动设置目标音区",28)
    arrow(d,(380,415),(380,485));arrow(d,(1220,415),(1220,485))
    box(d,(70,485,690,605),"实时声源发声；暂停冻结时钟",28)
    box(d,(910,485,1530,605),"只敲对目标片才推进\n休止/同字连音自动处理",27)
    arrow(d,(380,605),(620,680));arrow(d,(1220,605),(980,680))
    box(d,(360,680,1240,795),"同一事件位置 → 双行歌词 / LED目标 / App进度\n停止后恢复演奏配置显示",28)
    save(im,"song_flow.png")

    # Faithful navigation map, deliberately not presented as a screenshot.
    im=Image.new("RGB",(1600,720),"white");d=ImageDraw.Draw(im)
    panels=[("演奏",["七个触控键 / 实时力度","颤音开关与深度","临时滑音 / 音量","播放中的歌词与状态"]),
            ("曲目",["我和我的祖国 / 敕勒歌","整曲播放 / 暂停 / 停止","脱机指引 / 当前目标","自动切换音区"]),
            ("音色",["口琴 / 二胡","五音区 / 演奏场景","回声 / 合唱 / 混响","LED模式 / OLED亮度"]),
            ("设备",["JDY优先的设备列表","BLE连接与FPGA应答","重连 / 断连处理","实际状态与通信提示"])]
    for i,(name,items) in enumerate(panels):
        left=20+i*400;right=left+360
        d.rounded_rectangle((left,35,right,630),radius=30,outline="black",width=3)
        label(d,((left+right)/2,100),name,34,True)
        d.line((left+22,145,right-22,145),fill="black",width=2)
        for j,t in enumerate(items):label(d,((left+right)/2,225+j*95),t,22)
    label(d,(800,685),"依据当前App代码整理的页面结构图；非手机实拍截图",26)
    save(im,"app_map.png")

    # Draw the latest actual report numbers, not a performance measurement.
    im=Image.new("RGB",(1600,500),"white");d=ImageDraw.Draw(im)
    label(d,(800,35),"完整耳机恢复工程：布局布线资源",32,True)
    vals=[("Logic",30280,59904),("BSRAM",45,118),("DSP",107.5,118)]
    for i,(name,u,total) in enumerate(vals):
        y=120+i*110;label(d,(140,y+25),name,29,True)
        d.rectangle((270,y,1190,y+50),outline="black",width=2)
        d.rectangle((270,y,270+920*u/total,y+50),fill="black")
        label(d,(1390,y+25),f"{u:g}/{total}  {100*u/total:.1f}%",27)
    label(d,(800,472),"DSP余量较小；Setup/Hold违例为0，不能据此推算整机演奏延迟",25)
    save(im,"resources.png")
    # Reuse three exact RTL-rendered lyric regions at readable report size.
    # This is a montage of existing digital evidence, never a device photo.
    src=Image.open(ROOT/'build/chilege_oled_review.png').convert('RGB')
    im=Image.new('RGB',(1600,240),'white');d=ImageDraw.Draw(im)
    crops=[((12,60,524,188),'祖国：起始'),((528,60,1040,188),'祖国：逐字高亮'),((12,420,524,548),'敕勒歌：当前句')]
    for i,(bounds,name) in enumerate(crops):
        crop=src.crop(bounds);im.paste(crop,(i*534,10));label(d,(i*534+256,192),name,28)
    save(im,'oled_frames.png')


def add(kind, **kwargs): CONTENT.append({"kind":kind,**kwargs})
def p(text, style="SCBody"): add("p",text=text,style=style)
def h(text, level=2, page=False): add("p",text=text,style=f"SC{level}",page=page)
def fig(name,caption,width=WIDTH): add("image",name=name,width=width);p(caption,"SCCaption")
def table(headers, rows, widths=None, caption=None):
    add("table",headers=headers,rows=rows,widths=widths)
    if caption:p(caption,"SCCaption")
def limited(name,text,limit):
    LIMITED[name]=(text,limit);p(text)


def compose():
    p("声芯：基于FPGA实时合成的七音交互电子乐器","SCTitle")
    p("技术文档 · 试填稿 · 2026年10月28日","SCMeta")
    h("摘要",1)
    limited("摘要",
        "声芯是一款将七片压力敲击面、滑音控制、中文显示与手机操作结合的电子乐器原型。作品以高云GW5AT-60B FPGA为计算核心，通过MCP3208采集七路压力及一路滑杆信号，利用硬件逻辑完成触发识别、力度映射、声部分配、包络与逐样本音色合成。系统设置五个音区，共35个可选音高，具有32个独立声部上下文，并提供口琴风格与二胡风格两种算法音色，以及回声、合唱、混响效果。手机经BLE/UART发送演奏与设置指令，声音始终由FPGA产生。\n系统内置《我和我的祖国》《敕勒歌》的音符事件，既能自动演奏，也能以LED提示当前目标，只有敲对才进入下一音；指引自动换音区。OLED与App展示同一演奏状态，曲目模式显示逐字歌词及七路力度。完整耳机恢复工程已完成构建与SRAM下载，布局布线检查无建立/保持时间违例。32声部规模和接口行为已有数字验证，实际多频谱峰与端到端延迟仍需仪器验收；供电故障后的整机复测及外壳总装尚未完成。本稿据此区分已实现功能、构建结果与待补实测，不将设计值写成实测值。",800)
    h("第一部分  作品概述",1)
    h("1.1 功能与特性")
    limited("功能与特性","通过七片压力片实现选音与力度控制，滑杆控制连续滑音，EC11及手机调整颤音。五音区对应35个半音阶音高；32声部保留各自的相位、包络与力度。可切换口琴、二胡两类算法音色，并独立开关回声、合唱、混响。手机七键可让设备发声，也能选择场景、曲目、音区、灯效和显示亮度。两首内置曲支持整曲播放及严格指引；指引自动换音区。中文OLED、七灯及App联动显示配置、目标、歌词与力度。断开手机后，内置曲目与实体演奏逻辑仍由FPGA独立运行。",400)
    h("1.2 应用领域")
    limited("应用领域","适用于小型电子乐器演奏、个人音乐体验、教学演示及FPGA实时音频实验。七片弧形敲击面降低单手选音的操作负担，手机提供更直观的参数入口。系统还可作为多维传感、硬件音频流水线、嵌入式可视化与无线控制的综合实验平台。当前定位为竞赛原型，可靠性、音色拟真及整机性能仍需持续完善。",400)
    h("1.3 主要技术特点")
    limited("主要技术特点","采用分时复用流水线，在12.288 MHz时钟下以四拍服务一个声部，32声部共128拍，音频帧预算为256拍。每个声部具有独立相位、频率、包络及力度状态，以谐波整形和弱纹理生成两类持续音色。音频效果在FPGA内以延迟存储和反馈支路实现，并对干湿比例平滑过渡。实体与手机输入分开管理，快速演奏采用当前按键快照覆盖旧请求，减少历史音符积压。曲谱、词时和显示共享事件索引，播放与指引共用曲库。标准I²S外放与PT8211耳机串行输出使用不同适配器。",400)
    h("1.4 主要性能指标")
    rows=[["输入","7路压力＋1路滑杆；12位ADC"],["音高/声部","35音高；32声部（数字验证）"],["音频","名义48 kHz，16位单声道复制输出"],["音色/效果","2类算法音色；3种音效"],["整机延迟","≤10 ms基础、≤5 ms争取；尚未实测"]]
    LIMITED["主要性能指标"]=("".join("".join(r) for r in rows)+"项目指标",200)
    table(["项目","当前指标与口径"],rows,[1900,6406],"表1  主要性能指标（设计/数字验证与实测口径分列）")
    h("1.5 主要创新点")
    limited("主要创新点","（1）以32份独立声部状态结合共享运算流水线，在有限资源下兼顾复音规模与多维表情。（2）将实体敲击、手机演奏和参数控制统一到FPGA状态，配合当前快照抑制历史起音补播。（3）把自动换音区、正确音推进、LED目标与双行逐字歌词结合，使同一曲库兼顾独立欣赏和互动演奏。以上为本作品的组合设计特点，不主张相关基础算法为原创。",200)
    h("1.6 设计流程")
    limited("设计流程","需求拆解与接口核对→压力/滑杆单路采集→多声部与音色合成→音效和外置音频→LED/OLED联动→BLE协议与App→曲谱/词时整理→数字回归与布局布线→实板试听修订→供电整改、整机复测及提交材料。本阶段后两项仍在完善。",200)

    h("第二部分  系统组成及功能说明",1,True)
    h("2.1 整体介绍")
    p("系统分为动作采集、实时音频、交互控制和声光输出四层。动作采集产生音符事件与连续表情参数；FPGA进行声部分配和逐样本合成；App通过蓝牙操作同一设备；OLED及LED反映FPGA当前状态。电脑端只负责开发、曲谱整理与测试，演奏时不参与音频计算[1]。")
    fig("system.png","图1  系统整体框图（两种音频输出对应独立工程）")
    p("外放工程将标准I²S送入MAX98357A，再驱动扬声器。近期供电事故后，另行建立PT8211板载耳机恢复工程；它保留上层功能，但串行格式不同，不能将耳机恢复成功当作标准I²S链路验收。本文资源参数采用完整耳机恢复工程，外放路径须在电源修复后复测。")
    h("2.2 硬件系统介绍")
    h("2.2.1 硬件整体介绍",3)
    table(["模块","作用及关键连接","当前证据"],[
        ["Tang Mega 60K","GW5AT-60B；主时钟、GPIO及音频流水线","已识别、构建、下载"],
        ["压力片×7","经固定电阻分压接AI0～AI6","此前已有实体演奏反馈"],
        ["MCP3208模块","8通道12位；SPI连接FPGA","原型使用，事故后待复查"],
        ["滑杆 / EC11","AI7连续滑音；旋转和按压调表情","代码接入，需整机复测"],
        ["OLED / LED×7","I²C中文显示；GPIO单色灯反馈","此前有显示/灯效反馈"],
        ["JDY-23 / Android","BLE透传UART；控制与状态双向通信","已安装APK并有联动反馈"],
        ["五颗面板键","音区−/＋、音色、曲目/返回、开始/暂停","已购；安装接线未确认"],
        ["音频与供电","MAX外放或板载PT8211耳机；独立稳定电源","当前隔离外设，耳机版SRAM"]
    ],[1750,3900,2656],"表2  硬件模块与当前证据状态")
    p("MCP3208的12位分辨率是器件能力，不等于已经标定的压力精度[3]；本作品当前将其用于相对力度控制。模块板载稳压与参考电压须以实物为准，不把芯片资料中的最高采样率写成当前整机采样性能。")
    h("2.2.2 机械设计介绍",3)
    p("采用矩形双层机身方案，上层布置现有七片弧形敲击面，右侧安排OLED、滑杆、旋钮与五颗功能键。敲击面已制作，后续重点为安装固定和旁侧透光点，不重做敲击结构。下层将FPGA、ADC、通信、功放和电源分区，保留检修及耳机/供电接口。")
    fig("mechanical.png","图2  矩形双层机身与内部布置设计示意（非成品实拍）")
    p("不透明顶板在各片旁侧设置小透光孔或导光件，对应普通两脚LED。线路沿顶板背面布置并固定，穿板处留绝缘与应力释放；各板卡使用支柱固定，电源与音频线远离压力高阻节点。最终尺寸、开孔、螺柱位置及模块最高点均按实物复核。当前尚无完成总装的正面和45°照片，不以概念图代替成果照片。")
    h("2.2.3 电路各模块介绍",3)
    p("七路压力输入采用同样的分压结构：ADC模块3V3输出依次经过4.7 kΩ电阻和压力片到采样节点，再由10 kΩ电阻接ADC地；采样节点接对应AI通道。压力片电阻减小时，采样电压上升。每通道独立布线和校准；任何情况下均应确认采样节点不超过实际ADC参考范围。")
    fig("circuits.png","图3  压力分压、单颗LED限流与常开按钮原理示意")
    p("AI7滑杆的电阻轨两端接ADC的REF和GND，滑动端接AI7，避免将滑杆满行程直接接到高于参考的电源。七颗LED每颗串独立1 kΩ电阻；五键使用常开、自复位触点，GPIO上拉，按下接地。EC11的逻辑电平保持3.3 V，外部按钮不接到开发板原有1.5 V按键网络。")
    table(["接口","关键输入/输出","设计约束"],[
        ["ADC ↔ FPGA","CS、SCLK、MOSI、MISO","3.3 V逻辑；电源正常后接信号"],
        ["OLED ↔ FPGA","VCC、GND、SCL、SDA","3.3 V供电/上拉，开漏I²C"],
        ["JDY ↔ FPGA","TXD→RX、RXD←TX、GND","载板VCC按实物规格；UART为3.3 V"],
        ["MAX ↔ FPGA","BCLK、LRCLK、DIN、SD","稳定5 V功放电源；SD经10 kΩ上拉"],
        ["MAX ↔ 扬声器","OUT＋、OUT−","桥接输出；OUT−不接公共地"],
        ["PT8211 ↔ FPGA","HP_BCK、HP_WS、HP_DIN、PA_EN","板载内部连接，独立右对齐串行器"]
    ],[1800,3000,3506],"表3  主要接口及电平约束")
    p("近期出现反接、5 V口测得11.2 V、3.3 V带载降至约1.2 V及明显发热。现已隔离故障外设，具体受损器件尚未定位。电源整改需逐块隔离检查，增加反接与过流保护，并用稳定供电重新验收；不能用程序切换解决供电问题。MAX98357A是I²S数字输入D类功放，其供电和桥接输出按厂家资料执行[4]。")
    h("2.3 软件系统介绍")
    h("2.3.1 软件整体介绍",3)
    p("FPGA部分以Verilog编写，包含采样、识别、分配、声源、音效、曲目和显示等模块；Gowin EDA完成综合、布局布线和位流生成。Android端使用Kotlin与Jetpack Compose，承担蓝牙发现、设备设置、手机演奏与状态呈现。电脑端Python脚本处理曲谱、词时、ROM和试听文件；设备不依赖云服务器或网址完成上述功能。")
    fig("app_map.png","图4  当前App四页功能结构（依据代码整理，非真机截图）")
    p("演奏页集中放置七键、力度、颤音与临时滑音，减少跨页调节；曲目页区分整曲播放与正确音推进的指引；音色页配置音色、音区、场景与音效；设备页区分蓝牙连接成功与FPGA有效状态回复。页面不以本机播放假音代替设备响应。当前Android最低版本为8.0，已生成可直接安装的APK；最终提交还需补拍当前版本真机界面[7]。")
    h("2.3.2 软件各模块介绍",3)
    p("（1）采样与动作识别。mcp3208_scan输出sample_channel、sample_value与sample_valid；fsr_strike_detector执行基线校准、双阈值和重触发判断，输出strike_channel及velocity。连续压力用于保持/力度，滑杆形成bend，EC11及手机形成vibrato参数。声部分配模块按bank×7＋pad得到音高索引，保存各次有效起音的拥有者，避免松开一个输入误释放其他声音。")
    fig("control_flow.png","图5  实体采样与手机实时快照的处理流程")
    p("（2）32声部合成。poly_synth32_tm保存32份phase、envelope、gate、note_age及音色状态，运算单元按slot轮转。单声部四拍、整轮128拍；在256拍音频帧内交付混合样本。相位步进由35项音高表确定，bend与颤音改变步进，ADSR控制幅度。以32×48 000计算的名义声部更新吞吐量为1.536 M声部样本/秒；它是结构设计值，仍需32个同时活跃可闻音和实际采样时钟证明。")
    p("口琴风格声源采用圆滑谐波、力度亮度变化与微弱气流纹理，二胡风格增加箱体频谱整形、弓擦纹理和渐入揉弦；当前均属算法近似，尚不能宣称达到真实乐器拟真标准。两类声源共用平滑起音和释放控制；后续调参应同时观察音头响应、长音和噪声，避免以增加底噪代替乐器质感。")
    p("（3）硬件音效。audio_effects_product实现约300 ms回声、约16 ms且随低频振荡变化的分数延迟合唱，以及四条不同长度、带阻尼反馈的混响支路。各效果干湿权重平滑变化，总权重受约束，避免简单相加造成突增音量。已有试听反馈能区分三种效果，仍需采集同音量A/B录音与峰值/RMS数据作为正式证据。")
    p("（4）BLE与App状态。帧包含帧头、版本、类型、序号、长度、载荷及CRC-8；Protocol负责组包/拆包，CommandQueue调度可靠设置，RealtimeNotes保存当前按住与起音位图。FPGA经CRC校验后执行，并返回STATE或七路力度遥测。实时快照可越过等待状态回复的队列，未发送的过期起音被取消，减少快速点按后补播旧音。")
    p("连接后无需机身K4/K5授权：当前有效帧建立活动会话，持续通信保持操作可用。JDY的STAT脚尚未接入，FPGA依靠活动超时判断链路，不能声称断开瞬间即可硬件识别。UART目前为9600 baud、8N1，九字节快照串行传输约9.375 ms，App最短合并间隔16 ms；手机链路应单独评价，不能套用本地演奏≤5 ms目标。")
    p("（5）曲目与指引。ROM保存音高、时值、休止和同字连音标志；song_event_player按时间运行，song_guide_long只有在当前目标出现一次正确的新敲击后才推进。指引将目标音区自动交给发声映射，演奏者只需选择正确压力片；同字的后续连音和休止自动处理，避免一个字被要求连点多次。曲目开始、暂停、停止分别有明确状态，不复用含糊的开关命令。")
    fig("song_flow.png","图6  整曲播放、脱机指引与歌词的统一事件流程")
    p("（6）OLED与LED。自由演奏时显示音区、音量、颤音开关、音色与蓝牙活动状态；下面保留七根力度柱及数字。曲目播放或指引时，上面两行改为左右错列歌词，已唱字反显、当前字逐列推进，长句滚动。字模使用统一基线，使“一”等笔画较少的字位于行中；整帧锁存一致状态，减少半屏新旧数据混杂。七灯显示跟随、指引、流光或呼吸模式；均为单色亮度变化。")
    add("image",name="oled_frames.png",width=WIDTH)
    p("图7  从RTL数字显示数据得到的歌词及字模预览（不代表实物刷新率）","SCCaption")

    h("第三部分  完成情况及性能参数",1,True)
    h("3.1 整体介绍")
    p("作品已形成七片压力输入、音频合成、手机控制、中文OLED和LED反馈的原型系统，研发过程中已进行多轮实物试听及界面反馈。近期电源反接造成硬件异常，目前外接供电和模块与FPGA隔离；完整耳机恢复程序已重新下载到SRAM并读回版本码0x9D67。下载成功只证明配置与器件通信，不能证明受损外设和整机已恢复。")
    p("本稿未取得可用的当前整机正面、45°全局照片及最新App真机截图，故不使用概念渲染冒充实物。正式提交前应在完成供电整改及总装后补拍上述照片，并将当前安装APK、运行位流和演示视频版本保持一致。")
    h("3.2 工程成果")
    h("3.2.1 机械成果",3)
    p("七片敲击面已制作；矩形机身、LED透光点和内部模块分区方案已设计。五颗功能键已到手，外壳固定、接插件安装、线束整理及总装照片尚未确认完成。机械成果当前以图2的结构方案说明，正式稿应替换或补充带实物标注的照片。")
    h("3.2.2 电路成果",3)
    p("已有七路压力分压、ADC接口、滑杆、旋钮、七灯、OLED、蓝牙及音频的接线资料和独立约束。外放链路此前实际有声；故障后受损器件待定位，最终接线与供电应重新逐项验收。现阶段不得把面包板连通或指示灯亮作为电气可靠性证明。")
    h("3.2.3 软件成果",3)
    table(["成果","当前版本/范围","完成与待补"],[
        ["FPGA完整耳机工程","0x9D67；完整功能上层＋PT8211输出","构建及SRAM读回完成，实听待验"],
        ["Android App","当前配套APK；四页功能、实时快照","25项JVM测试通过；最新真机复测待补"],
        ["曲目事件库","祖国246事件/194字；敕勒歌224事件/184字","两曲数据与歌词已生成；后者149 s"],
        ["显示与指引","中文配置、力度、双行歌词、自动音区","有数字帧/行为检查及历史实物反馈"],
        ["资料与构建","RTL、CST、工程脚本、验证日志、哈希","可追溯；提交前冻结配套版本"]
    ],[1700,3300,3306],"表4  工程成果及证据边界")
    h("3.3 特性成果与量化参数")
    p("以下数值分别来自当前源码配置、数字回归记录与Gowin布局布线报告；不将芯片标称参数或历史版本结果替代本版实测。主工程采用完整耳机恢复版，不与外放版或早期32分量实验混列资源成绩。")
    table(["项目","数据/结果","证据口径"],[
        ["音频帧","12.288 MHz / 256＝名义48 kHz","RTL/时钟配置；实测频率待补"],
        ["声部运算","32份独立状态；4拍/份，128拍/帧","当前RTL和声部隔离/期限回归"],
        ["音高范围","35个半音阶音高，MIDI60～94","查表非零与映射数字检查"],
        ["声部吞吐","名义1.536 M声部样本/秒","32×48 kHz；可闻并发待实证"],
        ["完整耳机时序","Setup/Hold违规均0；余量＋22.260/＋0.085 ns","布局布线结果，非演奏延迟"],
        ["资源","Logic30280；BSRAM45；DSP107.5","分别约50.5%、38.1%、91.1%"],
        ["耳机/音频回归","4项耳机定向检查＋10项音频回归通过","已保存发布记录；非听感评分"],
        ["App回归","5组共25项，失败/错误均0","JVM单测；非Android真机端到端"],
        ["祖国曲目","148.010 s；246事件、194歌词字","事件时长与目录核对"],
        ["敕勒歌曲目","149.000 s；224事件、184歌词字","按演示终点裁剪的事件数据"],
        ["整机延迟/稳定性","暂缺有效实测值","待电源修复后仪器测量"]
    ],[1800,3400,3106],"表5  当前可引用的量化结果")
    fig("resources.png","图8  完整耳机工程资源占用（来自实际布局布线报告）")
    p("35是可选择音高数，32是并发声部容量，两个指标不可互换。六条谐波用于每声部音色整形，不能据此宣称“单音32分量”。官方对独立振荡器及多频谱峰有单独验证口径[1]；现场应展示32个独立频率的同时输出、单路关闭/变调及RTL状态，而非只展示音区菜单。")
    p("本版声源含平滑起音，听感自然与响应速度需按同一门限评价。旧版本的数字链路阶跃结果不适用于直接证明本版≤5 ms，更不能替代机械传感到模拟输出的总延迟。Bluetooth控制与实体演奏须分开统计。")
    table(["待补测试","建议记录方式","判定目标"],[
        ["端到端延迟","同步记录压力原始信号与安全音频采样；两音色×七片×多次重复","基础≤10 ms；争取≤5 ms，报告最大值与抖动"],
        ["32路频谱","固定32个独立音；保留FFT、逐路关音/变调录像","谱峰数量、独立性及实际采样率可追溯"],
        ["七片力度/串扰","每片轻中重重复采样；同时记录邻片误触发","标定后响应一致，无明显漏音/误音"],
        ["音效与噪声","等增益旁路/开启对照，记录峰值、RMS和静音底噪","不异常增音量，效果可辨，残响符合设置"],
        ["整机稳定性","连续演奏、快点收手、重连、暂停恢复、断电重启","无卡音/历史补播；配置和声光一致"]
    ],[1700,3550,3056],"表6  正式提交前的测试方法（待执行，非已得结果）")
    p("延迟测量应提前约定起点和起音门限，分别记录静音首次起音、持音重触发与效果开启情形。扬声器桥接输出不能直接以普通接地探头夹到OUT−，应使用适当的差分或隔离采样方式；耳机路径可用于恢复诊断，但参赛标准I²S仍须单独取证[4-6]。")

    h("第四部分  总结",1)
    h("4.1 可扩展之处")
    limited("可扩展之处","优先完善稳定电源、反接/过流保护、可靠连接和可拆检修结构，再补齐32路频谱、端到端延迟、七片校准及长时间稳定性证据。在此基础上，可加入断电保存的演奏场景、可校验曲目上传、有限容量的音符事件录制/回放、更多按键映射和诊断自检。音色可继续优化高音区抗混叠与力度相关谐波，音效增加可调参数。扩展前应先降低当前DSP占用并保留时序余量；保持音频由FPGA实时合成，不以无线PCM推流替代核心。",300)
    h("4.2 心得体会")
    limited("心得体会","本项目的主要收获，是把“能够发声”逐步推进到“能够稳定演奏和解释”。早期仅比较音量或波形，难以体现口琴和二胡的特点；经过起音、谐波、揉弦和纹理调整，我们认识到乐器感来自多个环节的共同作用。增加气声或擦弦噪声也可能变成明显底噪，必须以同增益试听和原始样本对照，避免仅靠更响获得“更有效”的错觉。\n手机快速演奏曾出现松手后仍补播旧音的问题，说明可靠发送队列并不适合无限保存实时动作。将演奏改成当前状态快照、设置保留确认机制后，控制逻辑更符合乐器需要。曲目整理也不能直接相信自动转录：人声提取可能带来碎音、错误音高和不自然停顿，需要结合简谱、原唱时序及逐句试听修订；指引和自动播放则应共享事件数据，减少两个版本逐渐不一致。\n近期电源反接和带载掉压进一步说明，供电、接插件和绝缘固定属于作品核心。软件仿真通过、位流下载成功与实物可稳定使用是三件不同的事。后续将先排除硬件故障，完成整机复测和证据采集，再冻结演示版本。我们也会把35音高、32声部、数字计算时间和端到端延迟分别说明，使技术特点与可验证结果对应。",1000)

    h("第五部分  参考文献",1)
    refs=[
        "[1] 广东高云半导体科技股份有限公司. 全国大学生嵌入式芯片与系统设计竞赛2026：选题二及评分规则[EB/OL]. [2026-10-28]. https://www.gowinsemi.com.cn/university/match2026.",
        "[2] SIPEED. Tang Mega 60K Dock：硬件资料及底板原理图[EB/OL]. [2026-10-28]. https://wiki.sipeed.com/hardware/en/tang/tang-mega-60k/mega-60k.html.",
        "[3] MICROCHIP TECHNOLOGY. MCP3208：12-Bit, 100kSPS, 8-Channel ADC[EB/OL]. [2026-10-28]. https://www.microchip.com/en-us/product/mcp3208.",
        "[4] ANALOG DEVICES. MAX98357A/MAX98357B：PCM Input Class D Amplifier[EB/OL]. [2026-10-28]. https://www.analog.com/en/products/max98357a.html.",
        "[5] NXP SEMICONDUCTORS. I²S bus specification：UM11732[EB/OL]. [2026-10-28]. https://www.nxp.com/docs/en/user-manual/UM11732.pdf.",
        "[6] PRINCETON TECHNOLOGY. PT8211：16 Bit Digital to Analog Converter[EB/OL]. [2026-10-28]. https://www.pjrc.com/store/pt8211.pdf.",
        "[7] ANDROID DEVELOPERS. Bluetooth Low Energy[EB/OL]. [2026-10-28]. https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview.",
        "[8] 声芯项目组. 实时音频RTL、Android源码、曲目事件和构建验证记录[CP]. 2026. 随作品工程提交；版本基线见本文表4、表5."
    ]
    for ref in refs:p(ref,"SCRef")


def el(tag, **attrs):
    n=E.Element(f"{{{W}}}{tag}")
    for k,v in attrs.items():n.set(f"{{{W}}}{k}",str(v))
    return n


def sub(parent,tag,**attrs):
    n=el(tag,**attrs);parent.append(n);return n


def add_styles(styles):
    configs={
      "SCBody":("正文",21,False,330,0,100,"left",420),
      "SCTitle":("作品标题",36,True,400,0,180,"center",0),
      "SCMeta":("版本信息",20,False,300,0,160,"center",0),
      "SC1":("一级标题",28,True,360,180,130,"left",0),
      "SC2":("二级标题",24,True,330,150,90,"left",0),
      "SC3":("三级标题",22,True,315,120,70,"left",0),
      "SCCaption":("图表题注",18,False,270,65,110,"center",0),
      "SCSmall":("说明",19,False,285,0,80,"left",0),
      "SCRef":("参考文献",20,False,300,0,120,"left",0),
      "SCTable":("表格正文",18,False,265,0,0,"center",0),
    }
    for sid,(name,size,bold,line,bef,aft,align,indent) in configs.items():
        s=el("style",type="paragraph",styleId=sid);sub(s,"name",val=name);sub(s,"basedOn",val="1")
        pp=sub(s,"pPr");sub(pp,"spacing",before=bef,after=aft,line=line,lineRule="auto")
        sub(pp,"jc",val=align);sub(pp,"ind",firstLine=indent);sub(pp,"widowControl",val="1")
        sub(pp,"snapToGrid",val="0")
        if sid in ["SC1","SC2","SC3"]:sub(pp,"keepNext");sub(pp,"outlineLvl",val={"SC1":0,"SC2":1,"SC3":2}[sid])
        rp=sub(s,"rPr");sub(rp,"rFonts",ascii="Times New Roman",hAnsi="Times New Roman",eastAsia="宋体",cs="Times New Roman")
        sub(rp,"sz",val=size);sub(rp,"szCs",val=size);sub(rp,"color",val="000000")
        if bold:sub(rp,"b")
        styles.append(s)


def para(text,style="SCBody",page=False,keep=False,bold=False):
    q=el("p");pp=sub(q,"pPr");sub(pp,"pStyle",val=style)
    if page:sub(pp,"pageBreakBefore")
    if keep:sub(pp,"keepNext")
    rr=sub(q,"r")
    if bold:sub(sub(rr,"rPr"),"b")
    t=sub(rr,"t");t.set("{http://www.w3.org/XML/1998/namespace}space","preserve");t.text=text
    return q


def make_table(item):
    tb=el("tbl");pr=sub(tb,"tblPr");sub(pr,"tblW",w=WIDTH,type="dxa");sub(pr,"jc",val="center")
    borders=sub(pr,"tblBorders")
    for k in ["top","left","bottom","right","insideH","insideV"]:sub(borders,k,val="single",sz="5",color="000000")
    sub(pr,"tblLayout",type="fixed")
    margins=sub(pr,"tblCellMar")
    for k,w in [("top",65),("left",90),("bottom",65),("right",90)]:sub(margins,k,w=w,type="dxa")
    widths=item["widths"] or [WIDTH//len(item["headers"])]*len(item["headers"])
    widths[-1]+=WIDTH-sum(widths)
    grid=sub(tb,"tblGrid")
    for w in widths:sub(grid,"gridCol",w=w)
    rows=[item["headers"]]+item["rows"]
    for j,row in enumerate(rows):
        tr=sub(tb,"tr");trpr=sub(tr,"trPr");sub(trpr,"cantSplit")
        if j==0:sub(trpr,"tblHeader")
        for w,text in zip(widths,row):
            tc=sub(tr,"tc");tcpr=sub(tc,"tcPr");sub(tcpr,"tcW",w=w,type="dxa");sub(tcpr,"vAlign",val="center")
            tc.append(para(text,"SCTable",bold=j==0))
    return tb


def make_image(path,rid,width,index):
    with Image.open(path) as im:w,h=im.size
    cx=round(width/1440*914400);cy=round(cx*h/w)
    q=el("p");pp=sub(q,"pPr");sub(pp,"jc",val="center");sub(pp,"keepNext")
    sub(pp,"spacing",before="80",after="0",line="240",lineRule="auto")
    rr=sub(q,"r");drawing=sub(rr,"drawing")
    inline=E.SubElement(drawing,f"{{{WP}}}inline",distT="0",distB="0",distL="0",distR="0")
    E.SubElement(inline,f"{{{WP}}}extent",cx=str(cx),cy=str(cy))
    E.SubElement(inline,f"{{{WP}}}docPr",id=str(index+100),name=f"技术文档图{index}",descr="工程设计或数字预览，见题注")
    props=E.SubElement(inline,f"{{{WP}}}cNvGraphicFramePr")
    E.SubElement(props,f"{{{A}}}graphicFrameLocks",noChangeAspect="1")
    graphic=E.SubElement(inline,f"{{{A}}}graphic")
    gd=E.SubElement(graphic,f"{{{A}}}graphicData",uri=PIC)
    pic=E.SubElement(gd,f"{{{PIC}}}pic")
    nv=E.SubElement(pic,f"{{{PIC}}}nvPicPr");E.SubElement(nv,f"{{{PIC}}}cNvPr",id="0",name=path.name);E.SubElement(nv,f"{{{PIC}}}cNvPicPr")
    fill=E.SubElement(pic,f"{{{PIC}}}blipFill");blip=E.SubElement(fill,f"{{{A}}}blip");blip.set(f"{{{R}}}embed",rid)
    stretch=E.SubElement(fill,f"{{{A}}}stretch");E.SubElement(stretch,f"{{{A}}}fillRect")
    sp=E.SubElement(pic,f"{{{PIC}}}spPr");xf=E.SubElement(sp,f"{{{A}}}xfrm")
    E.SubElement(xf,f"{{{A}}}off",x="0",y="0");E.SubElement(xf,f"{{{A}}}ext",cx=str(cx),cy=str(cy))
    pg=E.SubElement(sp,f"{{{A}}}prstGeom",prst="rect");E.SubElement(pg,f"{{{A}}}avLst")
    return q


def write_docx():
    with ZipFile(SOURCE) as z:files={n:z.read(n) for n in z.namelist() if not n.endswith("/")}
    root=E.fromstring(files["word/document.xml"]);body=root.find("w:body",NS)
    sect=copy.deepcopy(body.find("w:sectPr",NS));body.clear()
    # Existing page sizes, margins, competition logo and header/footer relationships stay intact.
    styles=E.fromstring(files["word/styles.xml"]);add_styles(styles)
    rels=E.fromstring(files["word/_rels/document.xml.rels"])
    relns="http://schemas.openxmlformats.org/package/2006/relationships"
    existing_ids={x.get("Id") for x in rels};counter=100
    images=0
    for item in CONTENT:
        kind=item["kind"]
        if kind=="p":
            # Independent Word paragraphs preserve normal line wrapping and editing.
            for j,line in enumerate(item["text"].split("\n")):
                body.append(para(line,item["style"],item.get("page",False) and j==0))
        elif kind=="table":body.append(make_table(item))
        elif kind=="image":
            path=Path(item["name"])
            if not path.is_absolute():path=ASSETS/path
            while f"rId{counter}" in existing_ids:counter+=1
            rid=f"rId{counter}";counter+=1;images+=1
            name=f"sc_report_{images}.png";files[f"word/media/{name}"]=path.read_bytes()
            E.SubElement(rels,f"{{{relns}}}Relationship",Id=rid,Type=R+"/image",Target=f"media/{name}")
            body.append(make_image(path,rid,item["width"],images))
    body.append(sect)
    # OOXML paragraph properties have a strict order, even when Word accepts
    # permissively-ordered files. Keep the generated package schema-valid.
    order='pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange'.split()
    rank={name:i for i,name in enumerate(order)}
    for pp in root.findall('.//w:pPr',NS)+[p for s in styles if s.get(f'{{{W}}}styleId','').startswith('SC') for p in s.findall('w:pPr',NS)]:
        children=list(pp)
        for child in children:pp.remove(child)
        pp.extend(sorted(children,key=lambda e:rank.get(E.QName(e).localname,1000)))
    def xml(n):return E.tostring(n,xml_declaration=True,encoding="UTF-8",standalone=True)
    files.update({"word/document.xml":xml(root),"word/styles.xml":xml(styles),"word/_rels/document.xml.rels":xml(rels)})
    core=E.fromstring(files["docProps/core.xml"])
    core_ns={"dc":"http://purl.org/dc/elements/1.1/","cp":"http://schemas.openxmlformats.org/package/2006/metadata/core-properties"}
    for tag in ["dc:creator","cp:lastModifiedBy"]:
        node=core.find(tag,core_ns)
        if node is not None:node.text="声芯项目组"
    for tag in ["dc:title","dc:subject","cp:keywords","dc:description"]:
        node=core.find(tag,core_ns)
        if node is not None:node.text="声芯竞赛技术文档试填版"
    files["docProps/core.xml"]=xml(core)
    app=E.fromstring(files["docProps/app.xml"])
    for n in app.iter():
        if E.QName(n).localname in ["Company","Manager"]:n.text=""
    files["docProps/app.xml"]=xml(app)
    with ZipFile(DOCX,"w",ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return images


def verify(images):
    result={"template":str(SOURCE),"template_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),"docx":str(DOCX),"docx_sha256":hashlib.sha256(DOCX.read_bytes()).hexdigest(),"figures":images,"limited_sections":{}}
    for name,(text,limit) in LIMITED.items():
        chars=len(re.sub(r"\s+","",text));assert chars<=limit,(name,chars,limit)
        result["limited_sections"][name]={"nonspace_characters":chars,"limit":limit,"passed":True}
    with ZipFile(DOCX) as z:
        root=E.fromstring(z.read("word/document.xml"));text="\n".join(root.xpath('//w:t/text()',namespaces=NS))
        assert len(root.findall('.//w:tbl',NS))==6
        assert all(x in text for x in ["第一部分","第二部分","第三部分","第四部分","第五部分"])
        for term in ["浙江大学","Lwc01","wxid_","兰亭序","牵丝戏","PCM5102A"]:assert term not in text,term
        for term in ["800字内","400字内","1000字内","不要出现任何"]:assert term not in text,term
        assert len(root.xpath('//w:drawing',namespaces=NS))==images
        result["body_characters"]=len(text)
        result["tables"]=len(root.findall('.//w:tbl',NS))
        result["anonymity_text_check"]=True
    (OUT/"document_validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def improvement_note():
    text="""# 声芯技术文档试填：提升与待补清单

本清单是研发建议，不属于已经实现的成果。主报告保持原模板五部分，未把本清单塞进参赛正文。

## P0：完整性与可信度，提交前优先

1. 电源和线路：先查清反接后受损模块，停止使用输出异常的稳压板；使用稳定5V/3.3V并增加反接、过流保护。线束用有锁扣接插件/端子和应力释放固定，不靠捏紧杜邦头保证整机可靠性。整改后拍电源轨及接口检查记录。
2. 固定标准I²S外放路径并取证。当前PT8211耳机恢复版只能诊断/试听，其格式不等于标准I²S；MAX98357A路径应在恢复后测时钟、帧和实际发声，保留器件资料及原理图。无需仅因文档填写就另买PCM5102A。
3. 完成正面、45°、内部走线和四页App实拍；所有素材不带学校名、校徽、桌面账户等识别信息。现有设计图/数字预览保留明确题注，不能改称成品照片。
4. 冻结一套FPGA/曲库/APK及构建说明，完成断电启动、长时间演奏、手机重连/松手、模式切换、暂停恢复回归。当前耳机程序仍只在SRAM，不能写成掉电已持久化。

## P1：性能指标，让评委能测得出来

- 端到端延迟：借示波器或合适采集设备，同步采集传感原始触发与安全音频输出，两音色/七片重复。预先定义起点和起音门限；报告最小、中位、95分位、最大与抖动。先证明≤10ms，再争取≤5ms。当前平滑起音可能影响门限，需要自然音头与触发响应分别优化，不能直接删除柔化逻辑换数字。
- 32复音：设计独立入口的32频率测试模式，采集同时可闻谱峰、逐路关闭和变调；现场再切回七片演奏。35个音高菜单不能替代32并发验证。
- 力度：每片轻中重各至少20次，记录漏触发、误触发、串扰与响应范围，用逐片参数校准。柱子满格只代表显示映射，不代表传感器更准。
- 音质与效果：相同输入/音量做两音色及三效果A/B，测峰值、RMS、静音底噪，检查高音区混叠、叠音饱和和模式切换突变；不将乐器厂家THD/SNR直接填为本机指标。
- 蓝牙单独计时：9600 UART、9字节快照仅传输就9.375ms，当前App16ms合并。保留无历史补播目标；若升级波特率须先确认JDY支持、双端同步并验证丢包，不能承诺手机≤5ms。

## P2：创新性，把已有系统的不同讲清楚

- 当前可以成立的亮点：32独立状态与共享流水线；实体/手机统一FPGA状态及过期事件淘汰；自动音区、严格推进、歌词和灯反馈的一体曲目演奏。
- 可以再做的差异：敲击片逐片自校准档案；一键进入有声有光的自检/复音演示；带稳定版本标识和错误原因的通信诊断。这些功能可以直接改善真实使用和答辩，不依赖云端。
- 不宜夸大的说法：全球首创、AI自动精准扒谱、完整二胡物理建模、35种音色、蓝牙零延迟、整机已达到5ms、仅靠听感证明32独立振荡器。

## P3：技术特点与扩展，优先小而完整

1. DSP优化：完整耳机工程DSP107.5/118≈91.1%，先评估共享变调乘法、定点范围及常系数运算，重新验证时序和频谱，腾出余量后再加新模型。
2. 场景完善：已有本地场景，可增加明确的保存/调用/恢复默认及设备回执；如需FPGA断电保存，另行设计存储和写入寿命管理。
3. 音符事件录制：记录音高、力度、起止时刻与表情，回放时仍由FPGA实时合成。先录事件，避免在现有BLE上回传PCM音频。
4. 曲目上传：先定义版本、长度、范围、CRC及一次性提交/失败回退，再做App导入；不把“可在线下载”写成已经实现。
5. 音色优化：高音抗混叠、随力度变化的谐波与渐入揉弦，同增益盲听后决定是否改；不要继续用大量噪声制造拟真。

建议执行顺序：电源/线束 → 音频恢复 → 整机回归 → 延迟/32谱峰 → 成品图和演示 → 自检/校准等小扩展。现在不建议同时增加很多外设。
"""
    (OUT/"提升与待补清单.md").write_text(text,encoding="utf-8")


if __name__=="__main__":
    figures();compose();n=write_docx();res=verify(n);improvement_note()
    (OUT/"正文内容.json").write_text(json.dumps(CONTENT,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"docx":str(DOCX),"figures":n,"tables":res["tables"],"characters":res["body_characters"],"word_limits":res["limited_sections"]},ensure_ascii=False,indent=2))
