`timescale 1ns/1ps
module tb_handpan_modal32;
reg clk=0,rst_n=0,tick=0,enabled=1,hit=0,style=0;
reg [6:0] note=24;reg [7:0] velocity=200;
reg [7:0] bend=128;
wire signed [15:0] pcm;wire valid,overflow;wire [5:0] count;
wire [31:0] stolen_step;
note_step_table72 stolen_lookup(.note_index(7'd31),.phase_step(stolen_step));
always #1 clk=~clk;
handpan_modal32 dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.enabled(enabled),
 .strike_valid(hit),.strike_note(note),.strike_velocity(velocity),.rhythmic(style),.bend(bend),
 .sample_out(pcm),.sample_valid(valid),.overflow(overflow),.active_count(count));
integer n,j,clocks,max_clocks=0,fd,render=0,mode=0;
reg [1023:0] destination;
reg [23:0] airy_decay;
reg [31:0] prior_phase,phase_change;
task frame;
begin
 @(negedge clk);tick=1;@(negedge clk);tick=0;clocks=0;
 while(!valid && clocks<250)begin @(negedge clk);clocks=clocks+1;end
 if(!valid || clocks>224)$fatal(1,"handpan missed 256-clock frame: %d",clocks);
 if(clocks>max_clocks)max_clocks=clocks;
 if((^pcm)===1'bx)$fatal(1,"unknown PCM");
 @(negedge clk);
end endtask
task strike;input [6:0] pitch;input [7:0] strength;
begin @(negedge clk);note=pitch;velocity=strength;hit=1;@(negedge clk);hit=0;repeat(3)@(negedge clk);end endtask
task reset;
begin @(negedge clk);rst_n=0;tick=0;hit=0;repeat(3)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);end endtask
initial begin
 if($value$plusargs("render=%d",render))begin end
 if($value$plusargs("style=%d",mode))begin end
 reset();
 if(render)begin
  if(!$value$plusargs("out=%s",destination))$fatal(1,"render path missing");
  fd=$fopen(destination,"w");style=mode!=0;
  for(n=0;n<384000;n=n+1)begin
   // Same deterministic 16-beat phrase, plus a quick repeated-note flourish.
   if(n<288000 && n%18000==0)begin
    case((n/18000)%8)
     0:strike(12,210);1:strike(19,145);2:strike(21,185);3:strike(24,160);
     4:strike(12,230);5:strike(26,160);6:strike(21,190);7:strike(19,140);
    endcase
   end
   if(n>=288000 && n<312000 && n%4000==0)strike(24,160);
   frame();$fwrite(fd,"%d\n",pcm);
   if(overflow)$fatal(1,"render dropped an event");
  end
  $fclose(fd);$display("PASS render style=%d samples=384000 max_cycles=%d",mode,max_clocks);$finish;
 end
 strike(24,200);frame();if(count!=1 || overflow)$fatal(1,"first strike not allocated");
 for(n=0;n<4800;n=n+1)frame();
 airy_decay=dut.body[0];
 if(airy_decay<24'd4000000 || dut.octave[0]>=dut.body[0] || dut.fifth[0]>=dut.octave[0])$fatal(1,"independent resonances/decay");
 strike(24,100);frame();if(count!=2 || dut.strength[0]!=200 || dut.strength[1]!=100)$fatal(1,"repeat replaced previous tail/force");
 for(n=0;n<30;n=n+1)begin strike(n+12,180);frame();end
 if(count!=32)$fatal(1,"not 32 independent strikes");
 strike(31,220);frame();if(dut.step[0]!=stolen_step || count!=32 || dut.strength[0]!=220)$fatal(1,"deterministic steal");
 enabled=0;repeat(3)@(negedge clk);if(pcm!=0 || count!=0)$fatal(1,"disabled engine not silent");
 enabled=1;style=1;strike(24,200);frame();for(n=0;n<4800;n=n+1)frame();
 if(dut.body[1]>=airy_decay)$fatal(1,"rhythmic style not shorter");
 prior_phase=dut.phase[1];bend=255;frame();phase_change=dut.phase[1]-prior_phase;
 if(phase_change<=dut.step[1])$fatal(1,"metal bend up did not affect active tail");
 prior_phase=dut.phase[1];bend=0;frame();phase_change=dut.phase[1]-prior_phase;
 if(phase_change>=dut.step[1])$fatal(1,"metal bend down did not affect active tail");
 bend=128;
 reset();
 for(j=0;j<7;j=j+1)strike(24+j,100+j);
 frame();if(count!=7 || overflow)$fatal(1,"seven-pad burst was lost");
 for(j=0;j<7;j=j+1)if(dut.strength[j]!=100+j)$fatal(1,"burst order/strength changed");
 // A full queue must report overflow, never silently pretend every hit was kept.
 reset();frame();@(negedge clk);tick=1;@(negedge clk);tick=0;
 for(j=0;j<9;j=j+1)begin @(negedge clk);hit=1;@(negedge clk);hit=0;end
 if(!overflow)$fatal(1,"overflow was not observable");
 $display("PASS: 32 slots, force latch, repeat tails, modal decay, style, disable, bounded schedule and overflow; max_cycles=%d",max_clocks);$finish;
end
endmodule
