from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/melody_workbench_20261028';OUT=ROOT/'output/melody_workbench_20261028';OUT.mkdir(exist_ok=True)
labels=['录音中','选择片段','识别中','识别完成','对照原声','试听旋律','逐音修订','读取音频','传入设备','自动演奏','亮灯指引','暂停','结束']
frames=[]
for i in range(1,14):
 data=[int(x,16) for x in (B/f'oled_{i}.hex').read_text().split()];assert len(data)==1024
 im=Image.new('RGB',(128,64),(0,0,0))
 for p in range(8):
  for x in range(128):
   for y in range(8):
    if data[p*128+x]>>y&1:im.putpixel((x,p*8+y),(165,229,255))
 im.save(OUT/f'OLED_{i:02}.png');frames.append(im)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21)
def sheet(indices,name):
 rows=(len(indices)+2)//3;im=Image.new('RGB',(1200,rows*290+60),(8,18,27));d=ImageDraw.Draw(im)
 d.text((12,12),'OLED 实际 RTL 像素仿真 · 数值为测试输入，实物显示待验收',font=font,fill=(154,180,190))
 for j,i in enumerate(indices):
  x=j%3*400+8;y=j//3*290+60;d.text((x,y),labels[i-1],font=font,fill=(235,245,247))
  im.paste(frames[i-1].resize((384,192),Image.Resampling.NEAREST),(x,y+36))
 im.save(OUT/name)
sheet(list(range(1,14)),'OLED全过程_实际RTL像素.png')
sheet([1,3,7,9,10,11],'OLED六阶段预览.png')
print('rendered 13 native frames and two contact sheets')
