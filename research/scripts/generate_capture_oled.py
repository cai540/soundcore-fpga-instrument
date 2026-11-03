from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
titles=['','手机录音','选择片段','识别旋律','旋律已识别','原声试听','旋律试听','修正旋律','读取音频','传入设备','旋律演奏','亮灯指引','旋律暂停','旋律结束']
captions=['','对手机清晰哼唱','手机选段后识别','正在整理音高节奏','手机核对后传入','原声对照同时间轴','参考音可修正音符','手机修正支持撤销','文件最长三分钟','完成后可演奏指引','','','','']
fixed='进度共个音待传入当前口琴二胡区键收音偏弱正常过强起止请稍候'
chars=list(dict.fromkeys(''.join(titles+captions)+fixed))+[chr(i) for i in range(32,127)]
ids={c:i+1 for i,c in enumerate(chars)}
font=ImageFont.truetype('C:/Windows/Fonts/simhei.ttf',16)
rom=[0]*8192
for c,i in ids.items():
 im=Image.new('1',(16,16));ImageDraw.Draw(im).text((0,0),c,font=font,fill=1)
 for page in range(2):
  for x in range(16):rom[i*32+page*16+x]=sum(int(im.getpixel((x,page*8+y)))<<y for y in range(8))
(ROOT/'board/capture_font.mem').write_text('\n'.join(f'{v:02x}' for v in rom)+'\n',encoding='ascii')

def linecase(values):
 lines=[]
 for stage,text in enumerate(values):
  if not text:continue
  clauses=' '.join(f'3\'d{i}: tile=32\'h{ord(c):08x};' for i,c in enumerate(text[:8]))
  lines.append(f"8'd{stage}: case(slot) {clauses} default:tile=0;endcase")
 return '\n'.join(lines)
glyphcase='\n'.join(f"16'h{ord(c):04x}: font_id=8'd{i};" for c,i in ids.items())
source='''// Generated 16px Chinese tiles and paired 8px ASCII. Full glyph baseline.
module oled_capture_columns(
 input wire clk,input wire [87:0] payload,
 input wire timbre,input wire [2:0] bank,pad,
 input wire [2:0] page,input wire [6:0] column,output wire [7:0] pixels
);
 wire [7:0] stage=payload[15:8],progress=payload[23:16],midi=payload[79:72],level=payload[87:80];
 wire [15:0] position=payload[39:24],duration=payload[55:40],count=payload[71:56];
 wire [1:0] row=page[2:1];wire [2:0] slot=column[6:4];
 reg [31:0] tile;
 function [7:0] digit;input integer v;begin digit=8'd48+v%10;end endfunction
 function [31:0] pair;input [7:0] a,b;begin pair={16'hffff,a,b};end endfunction
 function [7:0] pitch_letter;input [7:0] m;begin case(m%12)
 0,1:pitch_letter="C";2,3:pitch_letter="D";4:pitch_letter="E";5,6:pitch_letter="F";
 7,8:pitch_letter="G";9,10:pitch_letter="A";default:pitch_letter="B";endcase end endfunction
 function sharp;input [7:0] m;begin case(m%12)1,3,6,8,10:sharp=1;default:sharp=0;endcase end endfunction
 always @* begin
  tile=0;
  if(row==0)begin case(stage)
@TITLES@
   default:tile=0;
  endcase
  if(stage>=10 && slot>=4)case(slot)
   4:tile=pair(digit(position/100),digit(position/10));
   5:tile=pair(digit(position),"/");
   6:tile=pair(digit(duration/100),digit(duration/10));
   7:tile=pair(digit(duration)," ");default:tile=0;endcase
  end
  else if(row==1)begin
   if(stage==1 || stage==2 || stage==5 || stage==6)case(slot)
    0:tile=pair(digit(position/6000),digit(position/600));
    1:tile=pair(":",digit(position/100));2:tile=pair(digit(position/10),"/");
    3:tile=pair(digit(duration/6000),digit(duration/600));
    4:tile=pair(":",digit(duration/100));5:tile=pair(digit(duration/10)," ");
    6:tile=stage!=1 ? 0 : level>240 ? 32'h8fc7 : level<8 ? 32'h504f : 32'h6b63;
    7:tile=stage!=1 ? 0 : level>240 ? 32'h5f3a : level<8 ? 32'h5f31 : 32'h5e38;
    default:tile=0;endcase
   else if(stage==3)case(slot)
    0:tile=32'h8fdb;1:tile=32'h5ea6;2:tile=pair(digit(progress/100),digit(progress/10));
    3:tile=pair(digit(progress),"%");default:tile=0;endcase
   else if(stage==4)case(slot)
    0:tile=32'h5171;1:tile=pair(digit(count/100),digit(count/10));2:tile=pair(digit(count)," ");
    3:tile=32'h4e2a;4:tile=32'h97f3;5:tile=32'h5f85;6:tile=32'h4f20;7:tile=32'h5165;default:tile=0;endcase
   else if(stage==7)case(slot)
    0:tile=32'h5f53;1:tile=32'h524d;
    2:tile=midi==255 ? pair("-","-") : pair(pitch_letter(midi),sharp(midi)?"#":" ");
    3:tile=midi==255 ? 0 : pair(digit(midi/12-1)," ");default:tile=0;endcase
   else if(stage==8)case(slot)0:tile=32'h8bf7;1:tile=32'h7a0d;2:tile=32'h5019;default:tile=0;endcase
   else if(stage==9)case(slot)
    0:tile=pair(digit(position/100),digit(position/10));1:tile=pair(digit(position),"/");
    2:tile=pair(digit(duration/100),digit(duration/10));3:tile=pair(digit(duration)," ");
    4:tile=32'h4e2a;5:tile=32'h97f3;default:tile=0;endcase
   else if(stage>=10)case(slot)
    0:tile=timbre ? 32'h53e3:32'h4e8c;1:tile=timbre ? 32'h7434:32'h80e1;
    3:tile=32'h533a;4:tile=pair(digit(bank+1)," ");
    5:tile=32'h952e;6:tile=pair(pad<7 ? digit(pad+1):"-"," ");default:tile=0;endcase
  end
  else if(row==3)begin case(stage)
@CAPTIONS@
   default:tile=0;
  endcase end
 end
 wire paired=tile[31:16]==16'hffff;
 wire [15:0] unicode=paired ? (column[3] ? {8'd0,tile[7:0]} : {8'd0,tile[15:8]}) : tile[15:0];
 reg [7:0] font_id;
 always @*begin case(unicode)
@GLYPHS@
 default:font_id=0;endcase end
 wire [12:0] address={font_id,page[0],4'd0}+(paired ? {10'd0,column[2:0]} : {9'd0,column[3:0]});
 reg [7:0] font [0:8191];reg [7:0] glyph;
 initial $readmemh("D:/FPGA/Projects/soundcore_2026/board/capture_font.mem",font);
 always @(posedge clk)glyph<=font[address];
 wire [6:0] x=column;
 wire progress_fill=stage==1 ? {1'b0,x} < level[7:1] : stage==9 ?
  ({9'd0,x}*duration < {16'd0,position}*16'd128) : stage==2 ?
  ({9'd0,x}*duration >= {16'd0,position}*16'd128) : x < progress*8'd127/100;
 wire bar=(column>=2 && column<=125);
 assign pixels=row==2 && stage<=9 ?
   (page[0]==0 ? (bar ? (progress_fill ? 8'hfc : 8'h84):0) : 0) : glyph;
endmodule
'''.replace('@TITLES@',linecase(titles)).replace('@CAPTIONS@',linecase(captions)).replace('@GLYPHS@',glyphcase)
(ROOT/'rtl/oled_capture_columns.v').write_text(source,encoding='utf8')
(ROOT/'build/melody_workbench_20261028/oled_glyphs.json').write_text(json.dumps(ids,ensure_ascii=False,indent=2),encoding='utf8')
print('generated',len(ids),'glyphs')
