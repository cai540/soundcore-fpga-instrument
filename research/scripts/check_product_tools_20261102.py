from pathlib import Path
import subprocess,json,sys,hashlib,os
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
results=[]
os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
for top in ['tb_tools_protocol','tb_tools_analyzer','tb_tools_recorder','tb_tools_bulk_endpoint','tb_tools_oled']:
 binary=B/(top+'.vvp')
 source=[R/'tb'/(top+'.v'),*list((R/'rtl').glob('*.v'))]
 c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s',top,'-o',str(binary),*map(str,source)],cwd=R,capture_output=True,text=True)
 (B/(top+'_compile.log')).write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=240)
 (B/(top+'.log')).write_text(r.stdout+r.stderr);print(top,r.stdout.strip(),flush=True)
 assert r.returncode==0 and 'PASS'in r.stdout,(top,r.stdout,r.stderr)
 results.append(dict(test=top,passed=True))
x=np.loadtxt(B/'fft_complex.txt');measured=x[:,0]+1j*x[:,1]
n=np.arange(1024);samples=np.trunc(11000*np.sin(2*np.pi*13*n/1024)+5000*np.sin(2*np.pi*53*n/1024))
expected=np.fft.fft(samples)/1024
peaks=sorted(np.argsort(np.abs(measured[:512]))[-2:].tolist());assert peaks==[13,53],peaks
error=float(np.max(np.abs(measured-expected)));assert error<32,error
data=bytes(int(x,16)for x in (B/'record_bytes.txt').read_text().split());filtered=np.loadtxt(B/'record_filtered.txt',dtype=int)
assert len(data)==512 and len(filtered)==1024,(len(data),len(filtered))
steps=[int(x,16)for x in (R/'rtl/tools_ima_step.mem').read_text().split()]
pred=0;index=0;codes=[];decoded=[]
adjust=[-1,-1,-1,-1,2,4,6,8]
for s in filtered:
 diff=int(s)-pred;step=steps[index];code=8 if diff<0 else 0;dist=abs(diff);delta=step>>3
 for bit,portion in [(4,step),(2,step>>1),(1,step>>2)]:
  if dist>=portion:code|=bit;dist-=portion;delta+=portion
 pred=max(-32768,min(32767,pred+(-delta if code&8 else delta)));index=max(0,min(88,index+adjust[code&7]));codes.append(code);decoded.append(pred)
encoded=bytes(codes[i]|codes[i+1]<<4 for i in range(0,len(codes),2));assert data==encoded,'RTL ADPCM != independent encoder'
(B/'record_decoded.txt').write_text('\n'.join(map(str,decoded)))
crc=0xffff
for b in data:
 crc^=b<<8
 for _ in range(8):crc=((crc<<1)^0x1021)&65535 if crc&32768 else crc<<1&65535
assert crc==int((B/'record_crc.txt').read_text(),16)
(B/'dsp_results.json').write_text(json.dumps(dict(tests=results,fft_peak_bins=peaks,fft_max_complex_error=error,adpcm_samples=len(filtered),adpcm_bytes=len(data),adpcm_independent_bit_exact=True,crc16=crc),indent=2))
print('PASS:independent numpy FFT and ADPCM/CRC verification',flush=True)
