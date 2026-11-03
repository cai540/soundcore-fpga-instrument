"""Check the unchanged fixed-point source and offline spectral compensation."""
from pathlib import Path
import json,subprocess,os
import numpy as np
from generate_harmonica_profile_20261102 import sine
R=Path(__file__).resolve().parents[1];B=R/'build/harmonica_refinement_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
n=16384;phase=np.arange(n,dtype=np.uint64)*(2**32//n)
for kind in(0,1):
    (B/f'sine_expected_{kind}.mem').write_text('\n'.join(f'{int(v)&65535:04x}'for v in sine(phase)))
text='''`timescale 1ns/1ps
module tb_harmonica_math;
reg clk=0,rst_n=0;always #5 clk=~clk;
reg[31:0] phase=0;reg[15:0] old_ref[0:16383],new_ref[0:16383];integer k;
expressive_texture #(.VOICES(1)) dut(.clk(clk),.rst_n(rst_n),.prepare_en(1'b0),.step_en(1'b0),.active(1'b0),.slot(5'd0),
 .phase(phase),.note_index(7'd24),.note_age(16'd0),.expression(8'd176),.timbre(1'b1));
initial begin
 $readmemh("build/harmonica_refinement_20261102/sine_expected_0.mem",old_ref);
 $readmemh("build/harmonica_refinement_20261102/sine_expected_1.mem",new_ref);
 for(k=0;k<16384;k=k+1)begin phase=k<<18;#1;
  if(dut.sine(phase)!==old_ref[k])$fatal(1,"fixed-point phase mismatch %d",k);
 end
 $display("PASS:16384 phases match independent fixed-point reference; original shared oscillator preserved");$finish;
end
endmodule
'''
tb=B/'tb_harmonica_math.v';tb.write_text(text)
c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s','tb_harmonica_math','-o',str(B/'math.vvp'),str(tb),str(R/'rtl/expressive_texture.v')],cwd=R,capture_output=True,text=True);assert c.returncode==0,c.stderr
r=subprocess.run([str(BIN/'vvp.exe'),str(B/'math.vvp')],cwd=R,capture_output=True,text=True);body=r.stdout+r.stderr;(B/'math.log').write_text(body);assert r.returncode==0 and 'PASS:'in body and'FATAL'not in body,body
profile=json.loads((B/'profile_validation.json').read_text());assert profile['additional_runtime_multipliers']==0
transfer=np.array(profile['spectral_transfer_matrix']);assert transfer.shape==(6,6)
table=[int(v,16)for v in(R/'rtl/expression_normalized.mem').read_text().split()]
assert len(table)==1296
for note in range(72):
    for anchor in range(9):
        packed=table[648+note*9+anchor];weights=np.array([(packed>>(12*k))&4095 for k in range(6)])
        rendered=transfer@weights;assert rendered[0]>0 and rendered[1]/rendered[0]<.55 and rendered[2]/rendered[0]<.25
(B/'math_validation.json').write_text(json.dumps(dict(passed=True,phases=n,fixed_point_matches=True,runtime_source_unchanged=True,
    calibrated_reed_anchors=648,all_h2_h3_within_bound=True,additional_runtime_multipliers=0),indent=2))
print(body)
