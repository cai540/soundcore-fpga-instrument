"""Deterministic integer tables for the FPGA analyzer and genuine audio recorder."""
from pathlib import Path
import math,json
from PIL import Image,ImageFont,ImageDraw
R=Path(__file__).resolve().parents[1]
def save(name,values,bits):
 (R/'rtl'/name).write_text(''.join(f'{v&((1<<bits)-1):0{bits//4}x}\n'for v in values),encoding='ascii')
save('tools_fft_twiddle.mem',[(round(math.cos(-2*math.pi*i/1024)*32767)&65535)|((round(math.sin(-2*math.pi*i/1024)*32767)&65535)<<16)for i in range(512)],32)
save('tools_sine.mem',[round(math.sin(2*math.pi*i/1024)*32767)for i in range(1024)],16)
n=127;fc=3000/48000
h=[(2*fc if i==63 else math.sin(2*math.pi*fc*(i-63))/(math.pi*(i-63)))*(.54-.46*math.cos(2*math.pi*i/(n-1)))for i in range(n)]
h=[round(v/sum(h)*32768)for v in h];h[63]+=32768-sum(h);save('tools_decimator.mem',h,16)
steps=[7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767]
save('tools_ima_step.mem',steps+[0]*(128-len(steps)),16)
edges=[1]
for i in range(1,33):edges.append(max(edges[-1]+1,round(256**(i/32))))
save('tools_fft_edges.mem',edges,16)
font=ImageFont.truetype('C:/Windows/Fonts/simhei.ttf',16)
headers=[]
for text in ['波形','频谱','相图']:
 im=Image.new('1',(128,16));ImageDraw.Draw(im).text((0,-1),text+'  实时音频',font=font,fill=1)
 for page in range(2):
  for x in range(128):headers.append(sum(int(im.getpixel((x,page*8+b))!=0)<<b for b in range(8)))
save('tools_display_headers.mem',headers,8)
(R/'build/acceptance_20261102/tables.json').write_text(json.dumps(dict(fft=1024,twiddle_q=15,stages=10,fft_normalization=1024,fir_taps=127,source_rate=48000,record_rate=8000,fir_sum=sum(h),spectrum_edges=edges,adpcm='IMA 4bit low-nibble first; initial predictor/index 0/0'),indent=2),encoding='utf8')
print('Generated FFT, sine,127-tap anti-alias FIR, IMA step and OLED header tables')
