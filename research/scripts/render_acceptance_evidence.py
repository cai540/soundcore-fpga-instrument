from pathlib import Path
import json,csv,wave
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';O=R/'output/acceptance_20261102';P=O/'previews';P.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.sans-serif':['SimHei'],'axes.unicode_minus':False,'font.size':10})
x=np.loadtxt(B/'voices32_i2s.txt');n=len(x);freq=np.fft.rfftfreq(n,1/48000);amp=np.abs(np.fft.rfft(x*np.hanning(n)));db=20*np.log10(np.maximum(amp,1)/amp.max())
fig,ax=plt.subplots(figsize=(11,4));ax.plot(freq,db,color='#173f54',lw=.8)
expected=440*2**((np.arange(60,92)-69)/12)
for i,hz in enumerate(expected):
 k=np.argmin(abs(freq-hz));ax.plot(freq[k],db[k],'.',color='#138675');ax.text(hz,5+(i%2)*7,str(i+1),ha='center',fontsize=7)
ax.set(xlim=(220,1640),ylim=(-70,25),xlabel='频率 / Hz',ylabel='相对幅值 / dB',title='32声部：真实RTL I2S解码频谱（仿真，非上板测量）');ax.grid(alpha=.15);fig.tight_layout();fig.savefig(P/'32声部_仿真频谱.png',dpi=170);plt.close(fig)
rows=list(csv.DictReader((B/'latency/physical_latency.csv').open()));values=np.array([float(v['step_to_abs64_i2s_ns'])/1e6 for v in rows]);labels=[('二胡'if v['timbre']=='0'else'口琴')+' / 区'+str(int(v['bank'])+1)+' / 片'+str(int(v['pad'])+1)for v in rows]
fig,ax=plt.subplots(figsize=(11,4));ax.bar(np.arange(len(values)),values,color=['#173f54'if v['timbre']=='0'else'#138675'for v in rows]);ax.axhline(5,color='#a43d3d',ls='--',lw=1,label='5ms目标');ax.set_xticks(np.arange(len(labels)),labels,rotation=55,ha='right',fontsize=8);ax.set(ylim=(0,5.6),ylabel='延迟 / ms',title='ADC阶跃→实际I2S |PCM|≥64：16工况仿真（不含功放/喇叭）');ax.legend();fig.tight_layout();fig.savefig(P/'16工况_数字延迟仿真.png',dpi=170);plt.close(fig)
raw=[int(x,16)for x in(B/'oled_analysis_frames.hex').read_text().split()]
for frame,label in[(0,'频谱'),(1,'波形'),(3,'相图接口')]:
 pixels=np.zeros((64,128),dtype=np.uint8)
 for i,v in enumerate(raw[frame*1024:(frame+1)*1024]):
  for bit in range(8):pixels[(i//128)*8+bit,i%128]=255 if v>>bit&1 else 0
 Image.fromarray(pixels).resize((768,384),Image.Resampling.NEAREST).save(P/f'OLED_{label}_I2C仿真.png')
shapes=[int(s,16)for s in(B/'phase_bitmap.txt').read_text().split()];pixels=np.zeros((48,128),np.uint8)
for i,v in enumerate(shapes):
 for b in range(8):pixels[i//128*8+b,i%128]=255 if v>>b&1 else 0
Image.fromarray(pixels).resize((768,288),Image.Resampling.NEAREST).save(P/'OLED_实际相图位图_仿真.png')
# The short clip is decoded from the actual RTL serial output, not a reference synthesizer.
with wave.open(str(O/'32声部_I2S仿真试听.wav'),'wb')as f:f.setparams((1,2,48000,0,'NONE','NONE'));f.writeframes(x.astype('<i2').tobytes())
print('Rendered real numeric evidence and clearly labelled simulation previews')
