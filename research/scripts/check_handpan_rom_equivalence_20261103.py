from pathlib import Path
import subprocess,os,json
R=Path(__file__).resolve().parents[1];B=R/'build/product_repair_20261103/rom';B.mkdir(exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
for name,source in [('handpan_modal32','handpan_modal_reference'),('rock_voice_fx','rock_voice_reference')]:
 text=(B.parent/(source+'.v')).read_text().replace('module '+name+' #','module '+name+'_ref #')
 if name=='handpan_modal32':text=text[:text.index('\nmodule handpan_pitch_layout')]
 (B/(name+'_ref.v')).write_text(text)
bench=r'''
`timescale 1ns/1ps
module tb_handpan_rom_equivalence;
reg clk=0,rst=0,tick=0,enabled=1,hit=0,rhythm=0;always #5 clk=~clk;
reg[6:0]note=24;reg[7:0]velocity=180,bend=128;wire signed[15:0]a,b;wire av,bv,ao,bo;
handpan_modal32 dut(.clk(clk),.rst_n(rst),.sample_tick(tick),.enabled(enabled),.strike_valid(hit),.strike_note(note),.strike_velocity(velocity),.rhythmic(rhythm),.bend(bend),.sample_out(a),.sample_valid(av),.overflow(ao));
handpan_modal32_ref refdut(.clk(clk),.rst_n(rst),.sample_tick(tick),.enabled(enabled),.strike_valid(hit),.strike_note(note),.strike_velocity(velocity),.rhythmic(rhythm),.bend(bend),.sample_out(b),.sample_valid(bv),.overflow(bo));
reg fx_input=0;reg signed[15:0]fx_sample=0;reg[3:0]drive=0;reg[7:0]tone=80;wire signed[15:0]x,y;wire xv,yv,xo,yo;integer n,i,count=0,fx_count=0;reg signed[15:0]last_reference=0;
rock_voice_fx fx(.clk(clk),.rst_n(rst),.enabled(enabled),.input_valid(fx_input),.sample_in(fx_sample),.drive(drive),.tone(tone),.sample_out(x),.sample_valid(xv),.overflow(xo));
rock_voice_fx_ref fx_ref(.clk(clk),.rst_n(rst),.enabled(enabled),.input_valid(fx_input),.sample_in(fx_sample),.drive(drive),.tone(tone),.sample_out(y),.sample_valid(yv),.overflow(yo));
always @(posedge clk)begin #1;
 if(rst)begin
  if(av!==bv || ao!==bo)$fatal(1,"modal timing/overflow mismatch");
  if(av)begin if(a!==b)$fatal(1,"modal PCM mismatch %d %d",a,b);count=count+1;end
  if(yv)last_reference=y;
  if(xv)begin if(x!==last_reference)$fatal(1,"metal PCM mismatch %d %d",x,last_reference);fx_count=fx_count+1;end
 end
end
initial begin
 repeat(3)@(negedge clk);rst=1;
 for(n=0;n<384;n=n+1)begin
  for(i=0;i<256;i=i+1)begin @(negedge clk);tick=i==0;hit=i==6 && n%4==0;
   note=12+n%60;velocity=100+n%156;rhythm=n>160;bend=64+n%128;
   fx_input=i==1;fx_sample=n*7919;drive=n%16;tone=n%256;
  end
 end
 if(count!=384 || fx_count!=384 || xo || yo)$fatal(1,"sample counts or deadline");
 $display("PASS:384 full modal frames and384 nonlinear samples exactly match, block-ROM scheduling stays inside48kHz deadline");$finish;
end
endmodule
'''
(B/'bench.v').write_text(bench)
sources=[B/'bench.v',B/'handpan_modal32_ref.v',B/'rock_voice_fx_ref.v',R/'rtl/handpan_modal32.v',R/'rtl/rock_voice_fx.v',R/'rtl/note_step_table72.v']
c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s','tb_handpan_rom_equivalence','-o',str(B/'test.vvp'),*map(str,sources)],cwd=R,capture_output=True,text=True);assert c.returncode==0,c.stderr
r=subprocess.run([str(BIN/'vvp.exe'),str(B/'test.vvp')],cwd=R,capture_output=True,text=True,timeout=180)
(B/'result.log').write_text(r.stdout+r.stderr);print(r.stdout,flush=True);assert r.returncode==0 and 'PASS' in r.stdout
(B/'results.json').write_text(json.dumps(dict(modal_frames=384,nonlinear_samples=384,passed=True)))
