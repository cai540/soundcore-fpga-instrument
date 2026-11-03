import math,struct,wave
from pathlib import Path
out=Path('build/fx_review');out.mkdir(exist_ok=True)
samples=[]
for i in range(240000):
    t=i/48000;value=0
    if i==24000:value=10000
    for a,b,hz in [(1.5,1.8,523.25),(1.85,2.2,659.25),(2.25,2.9,783.99)]:
        if a<=t<b:
            env=min(1,(t-a)/.01,(b-t)/.02)
            value=round(5000*env*(math.sin(2*math.pi*hz*(t-a))+.15*math.sin(4*math.pi*hz*(t-a))))
    samples.append(value)
(out/'input.hex').write_text(''.join(f'{x&65535:04x}\n' for x in samples),encoding='ascii')
with wave.open(str(out/'dry_probe.wav'),'wb') as f:
    f.setparams((1,2,48000,0,'NONE','not compressed'))
    f.writeframes(b''.join(struct.pack('<h',x) for x in samples))
print('FX probe ready, peak',max(abs(x) for x in samples))
