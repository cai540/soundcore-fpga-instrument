from pathlib import Path
import os,subprocess,json
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
s=(R/'tb/tb_tools_recorder.v').read_text().replace('tb_tools_recorder','tb_tools_record_full').replace('.MAX_SAMPLES(1024)','.MAX_SAMPLES(64000)').replace('count!=1024','count!=64000').replace('k<512','k<32000').replace('#5000000','#220000000')
for name in ['filtered','bytes','crc']:s=s.replace('record_'+name+'.txt','record_full_'+name+'.txt')
tb=B/'tb_tools_record_full.v';tb.write_text(s);binary=B/'tb_tools_record_full.vvp'
r=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s','tb_tools_record_full','-o',str(binary),str(tb),str(R/'rtl/audio_record_adpcm.v')],cwd=R,capture_output=True,text=True);assert r.returncode==0,r.stderr
r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=600);(B/'record_full.log').write_text(r.stdout+r.stderr);print(r.stdout,flush=True);assert r.returncode==0 and 'PASS'in r.stdout
data=bytes(int(x,16)for x in(B/'record_full_bytes.txt').read_text().split());assert len(data)==32000
crc=65535
for b in data:
 crc^=b<<8
 for _ in range(8):crc=((crc<<1)^0x1021)&65535 if crc&32768 else crc<<1&65535
assert crc==int((B/'record_full_crc.txt').read_text(),16)
(B/'record_capacity_results.json').write_text(json.dumps(dict(samples=64000,bytes=32000,seconds=8,sample_rate=8000,crc16=crc,bounded=True),indent=2));print('PASS:full default8-second capacity, last RAM address and CRC16')
