"""Vector module-level electrical schematics from current verified net names.

Not a fabricated drawing of purchased module internals. The single-input power
distribution is a proposed revision, with ratings awaiting the purchased part.
"""
import json,math,re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle,Polygon
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/engineering_upgrade_20261028/schematics';OUT.mkdir(parents=True,exist_ok=True)
F=FontProperties(fname=r'C:\Windows\Fonts\msyh.ttc')
nets=[];bom=[]

def text(ax,x,y,s,size=8,ha='left',va='center',bold=False):
    ax.text(x,y,s,fontproperties=F,fontsize=size,ha=ha,va=va,
            weight='bold' if bold else 'normal',color='black',linespacing=1.4)
def line(ax,*pts,lw=1):
    ax.plot([p[0] for p in pts],[p[1] for p in pts],color='black',lw=lw,solid_capstyle='round')
def dot(ax,x,y):ax.add_patch(Circle((x,y),.65,color='black'))
def gnd(ax,x,y):
    line(ax,(x,y),(x,y+3))
    for i in range(3):line(ax,(x-3+i,y+3+i),(x+3-i,y+3+i))
def label(ax,x,y,s,side='left'):
    # Net labels with an explicit connection point at (x,y).
    text(ax,x-1 if side=='left' else x+1,y-1,s,7.2,'right' if side=='left' else 'left',va='bottom')
def resistor(ax,x,y,ref,val,vertical=True,variable=False):
    if vertical:
        line(ax,(x,y),(x,y+3));ax.add_patch(Rectangle((x-2,y+3),4,10,fill=False,lw=1));line(ax,(x,y+13),(x,y+16))
        text(ax,x+4,y+5,ref,7);text(ax,x+4,y+11,val,7)
        if variable:ax.annotate('',xy=(x+4,y+2),xytext=(x-4,y+14),arrowprops={'arrowstyle':'->','lw':.9})
        return (x,y),(x,y+16)
    line(ax,(x,y),(x+3,y));ax.add_patch(Rectangle((x+3,y-2),10,4,fill=False,lw=1));line(ax,(x+13,y),(x+16,y))
    text(ax,x+8,y-7,ref,7,'center');text(ax,x+8,y+7,val,7,'center')
    return (x,y),(x+16,y)
def module(ax,x,y,w,h,ref,title,left=(),right=()):
    ax.add_patch(Rectangle((x,y),w,h,fill=False,lw=1.2));text(ax,x+w/2,y+6,ref,10,'center',bold=True)
    text(ax,x+w/2,y+13,title,8,'center')
    pins={}
    for side,items in [('left',left),('right',right)]:
        start=y+24
        step=min(10,(h-30)/max(len(items)-1,1))
        for i,name in enumerate(items):
            py=start+i*step;px=x if side=='left' else x+w
            end=px-8 if side=='left' else px+8
            line(ax,(px,py),(end,py));text(ax,px+2 if side=='left' else px-2,py,name,7,'left' if side=='left' else 'right')
            pins[name]=(end,py)
    return pins
def entry(ref,value,pins,kind='existing'):
    bom.append({'reference':ref,'value':value,'status':kind})
    for pin,net in pins.items():nets.append({'reference':ref,'pin':str(pin),'net':net,'status':kind})
def sheet(title,n,subtitle='按原型模块连线绘制；非模块内部芯片原理图'):
    fig,ax=plt.subplots(figsize=(16.54,11.69),dpi=145)
    ax.set_xlim(0,420);ax.set_ylim(297,0);ax.set_aspect('equal');ax.axis('off');fig.subplots_adjust(0,0,1,1)
    ax.add_patch(Rectangle((8,8),404,281,fill=False,lw=1))
    for x in range(20,410,20):line(ax,(x,8),(x,10),lw=.4)
    for y in range(20,280,20):line(ax,(8,y),(10,y),lw=.4)
    text(ax,16,18,title,13,bold=True);text(ax,16,28,subtitle,8)
    line(ax,(8,264),(412,264))
    text(ax,16,272,'声芯 / SOUNDCORE    模块级电路原理图    工程复核稿 Rev A',9,bold=True)
    text(ax,16,281,'网名相同表示电气相连；元件值按当前接线，新增保护/分配参数须核对实际电源。',7.5)
    text(ax,402,272,f'{n}/5',10,'right');text(ax,402,281,'2026-10-28  ·  A3',8,'right')
    return fig,ax
def export(fig,name,pdf):
    fig.savefig(OUT/(name+'.svg'));fig.savefig(OUT/(name+'.png'),dpi=145,facecolor='white');pdf.savefig(fig);plt.close(fig)

def build():
 with PdfPages(OUT/'声芯_模块级电路原理图_RevA.pdf') as pdf:
    fig,ax=sheet('01  单电源入口与分支供电（拟采用）',1,'12V单入口方案；已购电源模块的型号、额定电流和温升尚待核对，不能据此直接接线')
    pin=module(ax,20,60,58,55,'J_IN','单一12V DC入口',right=['+12V_IN','GND'])
    p=pin['+12V_IN'];line(ax,p,(100,p[1]));resistor(ax,100,p[1],'F1','保险/过流保护',False)
    line(ax,(116,p[1]),(132,p[1]));rp=module(ax,145,58,70,58,'U_PROTECT','反接保护 / 总开关',left=['VIN'],right=['VOUT'])
    # Port VIN sits at y=82, the input line is y=84: intentional routed join.
    line(ax,(137,82),(132,82),(132,p[1]));line(ax,(223,82),(242,82),(242,135));dot(ax,242,82)
    line(ax,pin['GND'],(88,pin['GND'][1]),(88,125));gnd(ax,88,125);text(ax,98,124,'GND（星形公共地）',8)
    fp=module(ax,282,52,104,70,'U_FPGA','开发板原有DC5521入口',left=['DC_12V','GND'],right=['3V3_OUT'])
    line(ax,(242,82),(260,82),(260,76),fp['DC_12V']);line(ax,fp['GND'],(260,fp['GND'][1]),(260,120));gnd(ax,260,120)
    label(ax,*fp['3V3_OUT'],'3V3_FPGA',side='right')
    buck=module(ax,282,146,104,72,'U_BUCK','已购降压模块：12V → 5V',left=['VIN+','VIN-'],right=['VOUT+','VOUT-'])
    line(ax,(242,135),(242,170),buck['VIN+']);line(ax,buck['VIN-'],(256,buck['VIN-'][1]),(256,233));gnd(ax,256,233)
    label(ax,*buck['VOUT+'],'5V_EXT',side='right');label(ax,*buck['VOUT-'],'GND',side='right')
    text(ax,20,161,'电源分配原则',10,bold=True)
    text(ax,20,178,'• 12V在面包板之前分支，FPGA不从3.3V/5V轨倒灌供电。\n• 5V_EXT：ADC模块、JDY载板、MAX功放。\n• 3V3_FPGA：OLED及3.3V逻辑控件。\n• 3V3_ADC：只给压力分压；不与3V3_FPGA并联。\n• USB下载保留；外接电源接原有入口，沿用板上电源管理。',8,va='top')
    text(ax,20,241,'适配器/降压额定功率 ≥ 实测整机峰值功率并留余量；原板12V入口依据Dock rev1.4电源树及厂家说明。',7.5)
    entry('J_IN','12V input',{'1':'12V_IN','2':'GND'},'proposed')
    entry('F1','rating TBD',{'1':'12V_IN','2':'12V_FUSED'},'proposed')
    entry('U_PROTECT','series protection and switch TBD',{'IN':'12V_FUSED','OUT':'12V_SYS'},'proposed')
    entry('U_BUCK','purchased 12V-to-5V, verify rating',{'VIN+':'12V_SYS','VIN-':'GND','VOUT+':'5V_EXT','VOUT-':'GND'},'proposed')
    entry('U_FPGA_PWR','Tang Mega NEO Dock',{'DC_IN':'12V_SYS','GND':'GND','3V3_OUT':'3V3_FPGA'})
    export(fig,'01_power',pdf)

    fig,ax=sheet('02  七路压力片分压与滑杆采样',2)
    for i in range(7):
        x=24+i*42;text(ax,x,43,f'CH{i}',9,bold=True);label(ax,x,56,'3V3_ADC',side='right')
        line(ax,(x,56),(x,66));resistor(ax,x,66,f'R{i+1}','4.7kΩ')
        line(ax,(x,82),(x,91));resistor(ax,x,91,f'FSR{i+1}','压力片',variable=True)
        line(ax,(x,107),(x,120));dot(ax,x,120);line(ax,(x,120),(x+15,120));label(ax,x+15,120,f'AI{i}',side='right')
        line(ax,(x,120),(x,137));resistor(ax,x,137,f'R{i+8}','10kΩ');line(ax,(x,153),(x,166));gnd(ax,x,166)
        entry(f'R{i+1}','4.7k',{'1':'3V3_ADC','2':f'FSR_TOP_{i}'})
        entry(f'FSR{i+1}','pressure sensor',{'1':f'FSR_TOP_{i}','2':f'AI{i}'})
        entry(f'R{i+8}','10k',{'1':f'AI{i}','2':'GND'})
    adc=module(ax,325,45,58,144,'U_ADC','MCP3208模块',left=[f'AI{i}' for i in range(8)],right=['CLK','DIN','OUT','CS','REF','3V3','GND','VIN'])
    for i in range(8):label(ax,*adc[f'AI{i}'],f'AI{i}')
    mp={'CLK':'adc_sclk','DIN':'adc_mosi','OUT':'adc_miso','CS':'adc_cs_n','REF':'ADC_REF','3V3':'3V3_ADC','GND':'GND','VIN':'5V_EXT'}
    for pin,net in mp.items():label(ax,*adc[pin],net,side='right')
    entry('U_ADC','8AI-V1.06 MCP3208 module',{**{f'AI{i}':f'AI{i}' for i in range(8)},**mp})
    text(ax,25,197,'RV1  滑杆（10k电阻轨，需核对实物端子）',9,bold=True)
    label(ax,40,215,'ADC_REF',side='left');line(ax,(40,215),(50,215));resistor(ax,50,215,'RV1','10kΩ',False)
    line(ax,(66,215),(80,215));gnd(ax,80,215)
    ax.annotate('',xy=(58,217),xytext=(58,233),arrowprops={'arrowstyle':'->','lw':1});line(ax,(58,233),(115,233));label(ax,115,233,'AI7',side='right')
    text(ax,170,207,'ADC_REF来自模块参考输出，历史实测约2.5V；需故障后复核。\n压力支路上限由4.7k/10k限制，仍需确认AI不超实际参考范围。\n3V3_ADC为ADC模块输出，不与另一稳压输出直接并联。',8,va='top')
    entry('RV1','10k slider',{'1':'ADC_REF','2':'AI7','3':'GND'})
    export(fig,'02_sensors',pdf)

    fig,ax=sheet('03  七颗单色LED与五颗功能按键',3)
    for i in range(7):
        y=49+i*24;label(ax,65,y,f'pad_led_o[{i}]');line(ax,(65,y),(75,y));resistor(ax,75,y,f'R{i+21}','1kΩ',False)
        line(ax,(91,y),(108,y));ax.add_patch(Polygon([(108,y-3),(108,y+3),(114,y)],fill=False,lw=1));line(ax,(114,y-3),(114,y+3));line(ax,(114,y),(136,y));gnd(ax,136,y)
        for dx in [0,3]:ax.annotate('',xy=(118+dx,y-10),xytext=(112+dx,y-4),arrowprops={'arrowstyle':'->','lw':.7})
        text(ax,150,y,f'D{i+1}  AI{i}对应灯',8)
        entry(f'R{i+21}','1k',{'1':f'pad_led_o[{i}]','2':f'LED_A_{i}'})
        entry(f'D{i+1}','single colour LED',{'A':f'LED_A_{i}','K':'GND'})
    keys=[('K1','panel_bank_down_n','音区减'),('K2','panel_bank_up_n','音区加'),('K3','panel_timbre_n','音色'),('K4','panel_song_back_n','曲目/返回'),('K5','panel_play_pause_n','开始/暂停')]
    for i,(ref,net,title) in enumerate(keys):
        y=53+i*30;label(ax,299,y,net);line(ax,(299,y),(316,y));ax.add_patch(Circle((316,y),.8,fill=False));line(ax,(317,y),(330,y-7));ax.add_patch(Circle((332,y),.8,fill=False));line(ax,(333,y),(365,y));gnd(ax,365,y)
        text(ax,319,y+13,f'{ref}  {title}',8,'center');entry(ref,'momentary NO',{'1':net,'2':'GND'})
    text(ax,219,218,'FPGA输入内部上拉至3.3V；按钮为常开、自复位。\n按下接GND，禁止把5V直接送入GPIO。\nK5灯环与触点分开，驱动见第5页。',8,va='top')
    text(ax,24,240,'LED每颗独立限流；方向以实物长脚/平边和通断测试确认，不能只靠导线颜色判断。',8)
    export(fig,'03_controls_led',pdf)

    fig,ax=sheet('04  OLED与JDY-23通信接口',4)
    oled=module(ax,82,58,88,92,'U_OLED','SSD1315 / I²C模块',left=['GND','VCC','SCL','SDA'])
    for pin,net in {'GND':'GND','VCC':'3V3_FPGA','SCL':'oled_scl','SDA':'oled_sda'}.items():label(ax,*oled[pin],net)
    entry('U_OLED','SSD1315 OLED module',{'GND':'GND','VCC':'3V3_FPGA','SCL':'oled_scl','SDA':'oled_sda'})
    jdy=module(ax,285,58,100,112,'U_BLE','JDY-23带底板',left=['VCC','GND','TXD','RXD','BRK','STAT'])
    mp={'VCC':'5V_EXT','GND':'GND','TXD':'ble_uart_rx','RXD':'ble_uart_tx'}
    for pin,net in mp.items():label(ax,*jdy[pin],net)
    for pin in ['BRK','STAT']:
        x,y=jdy[pin];line(ax,(x-1,y-1),(x+1,y+1));line(ax,(x-1,y+1),(x+1,y-1))
    entry('U_BLE','JDY-23 carrier',mp)
    text(ax,30,184,'OLED：模块供电/上拉保持3.3V，SCL/SDA由FPGA开漏驱动。\n型号与地址应按实物确认，图示为模块外部连接，不重画内部升压电路。',8,va='top')
    text(ax,224,184,'JDY载板VCC丝印3.6～6V，采用5V_EXT。\nTXD是模块发出，接FPGA的ble_uart_rx；RXD反向连接。\nUART逻辑为3.3V；BRK/STAT当前未接入。\n不把BLE透传模块当作蓝牙音频接收器。',8,va='top')
    text(ax,30,239,'同名网在FPGA侧的实际排针位置与当前CST逐项核对；本图不以照片方向猜测脚序。',8)
    export(fig,'04_oled_ble',pdf)

    fig,ax=sheet('05  外放音频、旋钮与可选灯环驱动',5)
    amp=module(ax,95,52,92,110,'U_AMP','MAX98357A模块',left=['VIN','GND','BCLK','LRC','DIN','SD','GAIN'],right=['OUT+','OUT-'])
    amap={'VIN':'5V_EXT','GND':'GND','BCLK':'dac_bclk','LRC':'dac_lrclk','DIN':'dac_din'}
    for pin,net in amap.items():label(ax,*amp[pin],net)
    # SD uses a real 10k pull-up branch rather than connection to GPIO.
    sx,sy=amp['SD'];line(ax,(sx,sy),(62,sy),(62,116));resistor(ax,62,100,'R31','10kΩ');line(ax,(62,100),(62,93));label(ax,62,93,'5V_EXT',side='left')
    gx,gy=amp['GAIN'];line(ax,(gx-1,gy-1),(gx+1,gy+1));line(ax,(gx-1,gy+1),(gx+1,gy-1))
    a=amp['OUT+'];b=amp['OUT-'];line(ax,a,(210,a[1]),(210,70),(230,70),(230,86));line(ax,b,(218,b[1]),(218,112),(230,112))
    ax.add_patch(Rectangle((230,82),9,34,fill=False));ax.add_patch(Polygon([(239,82),(254,74),(254,124),(239,116)],fill=False));text(ax,241,135,'SPK1',8,'center')
    entry('U_AMP','MAX98357A module',{**amap,'SD':'MAX_SD','OUT+':'SPK_P','OUT-':'SPK_N'})
    entry('R31','10k',{'1':'5V_EXT','2':'MAX_SD'});entry('SPK1','speaker (verify impedance)',{'1':'SPK_P','2':'SPK_N'})
    enc=module(ax,310,50,82,100,'ENC1','EC11载板 / 3.3V逻辑',left=['VCC','GND','S1','S2','KEY'])
    emap={'VCC':'3V3_FPGA','GND':'GND','S1':'enc_s1_n','S2':'enc_s2_n','KEY':'enc_key_n'}
    for pin,net in emap.items():label(ax,*enc[pin],net)
    entry('ENC1','EC11 carrier',emap)
    text(ax,24,181,'可选K5灯环驱动（尚未实物确认）',9,bold=True)
    label(ax,70,207,'guide_button_led_o');resistor(ax,70,207,'R32','4.7kΩ',False);line(ax,(86,207),(102,207))
    line(ax,(102,200),(102,216));line(ax,(102,204),(113,194),(113,184));line(ax,(102,210),(113,222),(113,230));gnd(ax,113,230)
    ax.annotate('',xy=(111,220),xytext=(107,215),arrowprops={'arrowstyle':'->','lw':1})
    line(ax,(94,207),(94,220));resistor(ax,94,220,'R33','100kΩ');line(ax,(94,236),(94,239));gnd(ax,94,239)
    text(ax,120,210,'Q1 NPN开关',7);label(ax,113,184,'K5_LED−',side='right')
    text(ax,175,180,'灯环正端接匹配的额定电源；是否需外置限流按到手件确认。\nGPIO不能直接驱动未知电流灯环。此支路为预留设计，非已装实物。\n扬声器为桥接输出：OUT−不能接GND或耳机公共端。\n恢复版使用开发板原3.5mm孔；PT8211内部信号不在本接口接线。',8,va='top')
    entry('R32','4.7k base resistor',{'1':'guide_button_led_o','2':'K5_BASE'},'optional')
    entry('R33','100k base-emitter pull-down',{'1':'K5_BASE','2':'GND'},'optional')
    entry('Q1','NPN driver selected to lamp current',{'B':'K5_BASE','C':'K5_LED_NEG','E':'GND'},'optional')
    export(fig,'05_audio_encoder',pdf)

    # Detail used at full readable size inside the A4 technical document.
    fig,ax=plt.subplots(figsize=(10.5,5.2),dpi=180);ax.set_xlim(0,210);ax.set_ylim(104,0);ax.set_aspect('equal');ax.axis('off')
    for x,ref in [(30,'CHi')]:
        label(ax,x,12,'3V3_ADC',side='right');line(ax,(x,12),(x,20));resistor(ax,x,20,'R_TOP','4.7kΩ')
        line(ax,(x,36),(x,42));resistor(ax,x,42,'FSR_i','压力片',variable=True)
        line(ax,(x,58),(x,64));dot(ax,x,64);line(ax,(x,64),(73,64));label(ax,73,64,'AIi',side='right')
        resistor(ax,x,70,'R_BOTTOM','10kΩ');line(ax,(x,64),(x,70));gnd(ax,x,86)
    label(ax,117,32,'GPIO_LED');line(ax,(117,32),(122,32));resistor(ax,122,32,'R_LED','1kΩ',False)
    line(ax,(138,32),(151,32));ax.add_patch(Polygon([(151,29),(151,35),(157,32)],fill=False));line(ax,(157,29),(157,35));line(ax,(157,32),(178,32));gnd(ax,178,32)
    for dx in [0,3]:ax.annotate('',xy=(163+dx,23),xytext=(157+dx,29),arrowprops={'arrowstyle':'->','lw':.8})
    text(ax,145,62,'常开功能键：',9,'center');label(ax,122,77,'GPIO_KEY');line(ax,(122,77),(140,77));ax.add_patch(Circle((140,77),.7,fill=False));line(ax,(141,77),(155,70));ax.add_patch(Circle((157,77),.7,fill=False));line(ax,(158,77),(178,77));gnd(ax,178,77)
    text(ax,105,97,'GPIO_KEY内部上拉至3.3V；按下为低电平',8)
    fig.tight_layout(pad=.5);fig.savefig(OUT/'detail_sensors_led.png',facecolor='white');fig.savefig(OUT/'detail_sensors_led.svg');plt.close(fig)

    # Every current FPGA signal in the wiring source must occur in the net model.
    wiring=json.loads((ROOT/'docs/wiring_manual_data_2026-10-26.json').read_text(encoding='utf-8'))
    allnets={p['net'] for p in nets};required={p['signal'] for p in wiring['signals']}
    missing=required-allnets;assert not missing,missing
    refs=[p['reference'] for p in bom];assert len(refs)==len(set(refs))
    (OUT/'electrical_netlist.json').write_text(json.dumps({'components':bom,'connections':nets,'status':'module-level design review; power new revision pending rating checks'},ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'schematic_validation.json').write_text(json.dumps({'sheets':5,'components':len(bom),'component_pins':len(nets),'existing_fpga_signal_coverage':len(required),'missing_signals':sorted(missing),'net_model_checked':True,'erc_by_eda_tool_performed':False,'purchased_module_internal_schematic_inferred':False},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'sheets':5,'components':len(bom),'pins':len(nets),'signals':len(required),'missing':list(missing)},ensure_ascii=False))

if __name__=='__main__':build()
