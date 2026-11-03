from pathlib import Path
import subprocess,json,os
R=Path(__file__).resolve().parents[1];B=R/'build/product_repair_20261103/expression';B.mkdir(exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
ref=R/'build/product_repair_20261103/expression_reference.v'
(B/'reference.v').write_text(ref.read_text().replace('module pressure_expression32 #','module pressure_expression32_ref #'))
bench=r'''
`timescale 1ns/1ps
module tb_expression_equivalence;
reg clk=0,rst=0,tick=0,pv=0;always #5 clk=~clk;
reg[31:0]gate=0,remote=0;reg[95:0]zones=0;reg[255:0]attack=0;reg[2:0]channel=0;reg[7:0]force=0;
wire[255:0]a,b,c,d;
pressure_expression32 #(.ATTACK_HOLD_FRAMES(8),.CONTROL_INTERVAL(2)) dut(.clk(clk),.rst_n(rst),.sample_tick(tick),.gate(gate),.remote_owner(remote),.voice_zone(zones),.attack_velocity(attack),.pressure_valid(pv),.pressure_channel(channel),.pressure_velocity(force),.performance_velocity(a),.expression(b));
pressure_expression32_ref #(.ATTACK_HOLD_FRAMES(8),.CONTROL_INTERVAL(2)) refdut(.clk(clk),.rst_n(rst),.sample_tick(tick),.gate(gate),.remote_owner(remote),.voice_zone(zones),.attack_velocity(attack),.pressure_valid(pv),.pressure_channel(channel),.pressure_velocity(force),.performance_velocity(c),.expression(d));
integer i,j,n;reg[31:0]seed=32'h86d93af1;
function[31:0]rnd;input[31:0]x;reg[31:0]y;begin y=x^(x<<13);y=y^(y>>17);rnd=y^(y<<5);end endfunction
initial begin
for(i=0;i<256;i=i+1)for(j=0;j<256;j=j+1)if(dut.approach(i,j)!==refdut.approach(i,j))$fatal(1,"force recurrence mismatch %d %d",i,j);
repeat(3)@(negedge clk);rst=1;
for(n=0;n<30000;n=n+1)begin
 @(negedge clk);tick=n%256==0;seed=rnd(seed);pv=seed[0];channel=seed[3:1];force=seed[11:4];
 if(n%51==0)begin gate=seed;remote=seed^32'h85a6f102;for(i=0;i<32;i=i+1)begin seed=rnd(seed);attack[i*8+:8]=seed[7:0];zones[i*3+:3]=seed[10:8];end end
 @(posedge clk);#1;
 if(n%256==255 && (a!==c || b!==d))$fatal(1,"frame output mismatch cycle%d",n);
 for(j=0;j<32;j=j+1)if(n%256==1+j*5 && (a[j*8+:8]!==c[j*8+:8] || b[j*8+:8]!==d[j*8+:8]))$fatal(1,"voice missed audio service deadline %d",j);
end
$display("PASS:65536 approach states,30000cycles frame equality and all32audio service deadlines match the original");$finish;
end
endmodule
'''
(B/'tb_expression_equivalence.v').write_text(bench.replace('force','force_value'))
for top,sources in [('tb_expression_equivalence',[B/'tb_expression_equivalence.v',B/'reference.v',R/'rtl/pressure_expression32.v']),('tb_pressure_expression32',[R/'tb/tb_pressure_expression32.v',R/'rtl/pressure_expression32.v'])]:
 binary=B/(top+'.vvp')
 c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s',top,'-o',str(binary),*map(str,sources)],cwd=R,capture_output=True,text=True);assert c.returncode==0,(c.returncode,c.stdout,c.stderr)
 r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True);(B/(top+'.log')).write_text(r.stdout+r.stderr);print(r.stdout,flush=True);assert r.returncode==0 and 'PASS' in r.stdout
(B/'results.json').write_text(json.dumps(dict(approach_pairs=65536,compared_cycles=30000,frame_period_clocks=256,update_clocks=8,comparison='frame outputs and per-voice audio service deadlines',passed=True)))
