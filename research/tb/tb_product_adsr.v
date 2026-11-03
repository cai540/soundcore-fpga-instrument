`timescale 1ns/1ps
module tb_product_adsr;
 reg clk=0,rst_n=0,sample_tick=0;always #5 clk=~clk;
 reg[31:0]gate=0;reg[1023:0]phase_step=0;reg[255:0]velocity={32{8'd180}},expression={32{8'd180}};
 reg[223:0]pitch_index=0;reg timbre=1;wire[5:0]active_count;wire signed[15:0]sample_out;wire sample_valid;
 poly_synth32_tm dut(.diagnostic_sine(1'b0),.*);
 synth_voice #(.INSTRUMENT_PRESETS(1)) solo(.clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
  .gate(gate[0]),.phase_step(phase_step[31:0]),.velocity(8'd180),.timbre(timbre),
  .expression(8'd180),.pitch_index(7'd24),.sample_out());
 integer n;reg saw_decay=0,saw_sustain=0;reg[15:0]last_env=0;reg[1:0]last_state=0;
 task frame;begin @(negedge clk);sample_tick=1;@(negedge clk);sample_tick=0;repeat(255)@(negedge clk);end endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;phase_step[31:0]=32'd23409859;gate[0]=1;
  for(n=0;n<3000;n=n+1)begin frame();
   if(dut.state[0]==2)begin saw_decay=1;if(last_state==2 && dut.envelope[0]>last_env)$fatal(1,"decay rose");end
   if(dut.state[0]==3)saw_sustain=1;
   if(dut.envelope[0]>30000)$fatal(1,"attack overshoot");
   last_env=dut.envelope[0];last_state=dut.state[0];
  end
  if(!saw_decay || !saw_sustain || dut.envelope[0]!=28500 || solo.envelope!=28500)$fatal(1,"real D/S stages missing");
  gate[0]=0;last_env=dut.envelope[0];
  for(n=0;n<5000;n=n+1)begin frame();if(dut.envelope[0]>last_env)$fatal(1,"release rose");last_env=dut.envelope[0];end
  if(dut.envelope[0]!=0 || solo.envelope!=0)$fatal(1,"release did not finish");
  timbre=0;gate[0]=1;saw_decay=0;saw_sustain=0;last_env=0;last_state=0;
  for(n=0;n<2200;n=n+1)begin frame();
   if(dut.state[0]==2)begin saw_decay=1;if(last_state==2 && dut.envelope[0]>last_env)$fatal(1,"erhu decay rose");end
   if(dut.state[0]==3)saw_sustain=1;
   if(dut.envelope[0]>28000)$fatal(1,"erhu attack overshoot");
   last_env=dut.envelope[0];last_state=dut.state[0];
  end
  if(!saw_decay || !saw_sustain || dut.envelope[0]!=26600 || solo.envelope!=26600)$fatal(1,"erhu D/S missing");
  $display("PASS: accepted attack unchanged/no overshoot, real monotonic decay, sustain, release in live and offline engines");$finish;
 end
endmodule
