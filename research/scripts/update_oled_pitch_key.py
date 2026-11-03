from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];p=R/'rtl/oled_status_ssd1315.v';t=p.read_text(encoding='utf8')
t=t.replace('input wire [2:0] bank,','input wire [2:0] bank,\n    input wire [3:0] key,')
t=t.replace('reg [2:0] shown_bank,','reg [3:0] shown_key;\n    reg [2:0] shown_bank,')
t=t.replace('bank != shown_bank ||','bank != shown_bank || key != shown_key ||')
t=t.replace('shown_bank <= 0;','shown_bank <= 2;\n            shown_key<=0;')
t=t.replace('shown_bank <= bank;','shown_bank <= bank;\n                    shown_key<=key;')
t=t.replace('0:hanzi_at=1; 1:hanzi_at=2; // 音区','0:hanzi_at=48+shown_key; 1:hanzi_at=60; // C调 / C#调')
entries=[]
for i,label in enumerate(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B','调']):
    im=Image.new('1',(16,16));d=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/simhei.ttf' if label=='调' else 'C:/Windows/Fonts/arialbd.ttf',16 if label=='调' else 13)
    box=d.textbbox((0,0),label,font=font);w=box[2]-box[0];h=box[3]-box[1]
    d.text(((16-w)//2-box[0],(16-h)//2-box[1]),label,font=font,fill=1)
    data=[]
    for page in range(2):
        for x in range(16):data.append(sum(im.getpixel((x,page*8+y))<<y for y in range(8)))
    entries.append(f"                6'd{48+i}: hanzi_bitmap=256'h{bytes(data).hex()}; // {label}")
t=t.replace("                default: hanzi_bitmap=256'd0;",'\n'.join(entries)+"\n                default: hanzi_bitmap=256'd0;")
p.write_text(t,encoding='utf8')
print('OLED key/octave, atomic frame latch; existing lyrics and meters retained.')
