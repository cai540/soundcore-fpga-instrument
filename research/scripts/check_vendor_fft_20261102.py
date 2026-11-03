from pathlib import Path
import subprocess,os,json
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
s=(R/'tb/tb_tools_analyzer.v').read_text();s=s.replace('integer n,fd;real x;','integer n,fd;real x;\n reg signed[17:0] observed_r[0:255],observed_i[0:255];\n always @(posedge clk)if(dut.state==9)begin observed_r[dut.power_bin]=dut.ra;observed_i[dut.power_bin]=dut.ia;end\n GSR GSR(.GSRI(1\'b1));')
s=s.replace('for(n=0;n<1024;n=n+1)$fwrite(fd,"%d %d\\n",dut.real_mem[n],dut.imag_mem[n]);','for(n=1;n<256;n=n+1)$fwrite(fd,"%d %d\\n",observed_r[n],observed_i[n]);').replace('fft_complex.txt','fft_vendor_complex.txt').replace('analysis_vectors.txt','analysis_vendor_vectors.txt')
s=s.replace('phase_bitmap.txt','phase_vendor_bitmap.txt')
tb=B/'tb_vendor_fft.v';tb.write_text(s);binary=B/'tb_vendor_fft.vvp'
lib=Path('D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')
r=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-DTOOLS_GOWIN_RAM','-s','tb_tools_analyzer','-o',str(binary),str(tb),str(R/'rtl/product_audio_analyzer.v'),str(lib)],cwd=R,capture_output=True,text=True)
assert r.returncode==0,r.stderr
r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=120)
(B/'vendor_fft.log').write_text(r.stdout+r.stderr);print(r.stdout);assert r.returncode==0 and 'PASS'in r.stdout
x=np.loadtxt(B/'fft_vendor_complex.txt');assert np.isfinite(x).all()
n=np.arange(1024);src=np.trunc(11000*np.sin(2*np.pi*13*n/1024)+5000*np.sin(2*np.pi*53*n/1024));error=float(np.max(np.abs(x[:,0]+1j*x[:,1]-np.fft.fft(src)[1:256]/1024)))
assert error<32,error
assert (B/'analysis_vendor_vectors.txt').read_text()==(B/'analysis_vectors.txt').read_text(),'vendor RAM changed rendered vectors'
assert (B/'phase_vendor_bitmap.txt').read_text()==(B/'phase_bitmap.txt').read_text(),'vendor bitmap RAM pixels differ'
(B/'vendor_fft_results.json').write_text(json.dumps(dict(vendor_model=str(lib),fft_max_complex_error=error,bitmap_vectors_bit_exact=True),indent=2));print('PASS: actual Gowin primitive model matches portable FFT and all plotted vectors')
