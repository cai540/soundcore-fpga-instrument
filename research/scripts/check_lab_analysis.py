"""Synthetic fixture checks ONLY; these are not physical test evidence."""
from pathlib import Path
import sys,json
import numpy as np
from lab_audio_inspect import pcm_from_i2s,latency,spectrum,verify_voices
rate=48000;fs=12288000;n=2000;bits=[];ws=[];bclk=[]
source=np.round(7000*np.sin(2*np.pi*440*np.arange(n)/rate)).astype(np.int16)
for value in source:
 for channel in(0,1):
  word=int(value)&65535
  for slot in range(32):
   d=((word>>(16-slot))&1)if 1<=slot<=16 else 0
   bclk.extend([0,0,3.3,3.3]);ws.extend([channel*3.3]*4);bits.extend([d*3.3]*4)
t=np.arange(len(bits))/fs;at,pcm=pcm_from_i2s(t,np.array(bclk),np.array(ws),np.array(bits))
assert np.array_equal(pcm,source[1:]),(len(pcm),pcm[:10],source[:10])
assert abs(spectrum(pcm,rate)[0]['hz']-440)<25
tt=np.arange(10000)/1e6;pressure=np.where(tt>=.003,1.2,1.0);audio=np.where(tt>=.005,100,0)
r=latency(tt,pressure,tt,audio,.05,64);assert abs(r['latency_ms']-2)<1e-9
tone_t=np.arange(24000)/rate
tones=[np.sin(2*np.pi*440*2**((m-69)/12)*tone_t)*500 for m in range(60,92)]
assert verify_voices(np.sum(tones,axis=0),rate,32)['passed']
assert not verify_voices(np.sum(tones[:-1],axis=0),rate,32)['passed']
out=Path(__file__).resolve().parents[1]/'build/acceptance_20261102/lab_tool_selftest.json'
out.write_text(json.dumps(dict(synthetic_only=True,i2s_words=len(pcm),known_latency_ms=2,voice_presence_missing_tone_rejected=True,passed=True),indent=2));print('PASS:synthetic I2S decoding, signed PCM,FFT,missing-tone rejection and latency analysis; not a board measurement')
