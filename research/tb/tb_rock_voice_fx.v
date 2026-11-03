`timescale 1ns/1ps
module tb_rock_voice_fx;
reg clk=0,rst_n=0,enabled=1,valid_in=0;
always #1 clk=~clk;
reg signed[15:0] input_sample=0;
reg[3:0]drive=4;reg[7:0]tone=128;
wire signed[15:0]pcm;wire valid,overflow;
rock_voice_fx dut(.clk(clk),.rst_n(rst_n),.enabled(enabled),.input_valid(valid_in),
 .sample_in(input_sample),.drive(drive),.tone(tone),.sample_out(pcm),.sample_valid(valid),.overflow(overflow));
integer n,cycles,max_cycles=0;
task frame;input signed[15:0]value;begin
 @(negedge clk);input_sample=value;valid_in=1;@(negedge clk);valid_in=0;cycles=0;
 while(!valid && cycles<20)begin @(negedge clk);cycles=cycles+1;end
 if(!valid || cycles>8 || (^pcm)===1'bx)$fatal(1,"FX missed source-to-I2S deadline");
 if(cycles>max_cycles)max_cycles=cycles;
 if(pcm>10501 || pcm< -10501)$fatal(1,"FX added unsafe output gain");
 repeat(3)@(negedge clk);
end endtask
initial begin
 repeat(3)@(negedge clk);rst_n=1;
 for(n=0;n<512;n=n+1)frame(n[0] ? 32767:-32768);
 drive=15;tone=255;
 for(n=0;n<512;n=n+1)frame(n[4] ? 20000:-20000);
 if(dut.drive_smooth!=240)$fatal(1,"drive knob did not converge");
 for(n=0;n<5000;n=n+1)frame(0);
 if(pcm>1 || pcm< -1)$fatal(1,"DC/noise tail after silence");
 if(overflow)$fatal(1,"normal input overflowed");
 enabled=0;repeat(3)@(negedge clk);if(pcm!=0)$fatal(1,"disabled FX not silent");
 $display("PASS: rock FX bounded amplitude, smooth drive, silence convergence and <=8 clocks; max_cycles=%d",max_cycles);$finish;
end
endmodule
