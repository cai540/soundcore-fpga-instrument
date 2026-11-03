`timescale 1ns/1ps
module tb_guide_rhythm_cue;
 reg clk=0,rst_n=0,active=0,paused=0,correct=0;
 reg[10:0] step_index=0;reg[15:0] target_duration_ms=200;reg[6:0] target_led=1;
 wire[6:0]led;
 always #5 clk=~clk;
 guide_rhythm_cue #(.CLOCKS_PER_MS(2)) dut(.*);
 task cycles;input integer n;integer i;begin for(i=0;i<n;i=i+1)@(negedge clk);end endtask
 initial begin
  cycles(3);rst_n=1;active=1;cycles(4);
  if(led!=1)$fatal(1,"first target must be immediately bright");
  correct=1;step_index=1;target_duration_ms=100;target_led=2;cycles(1);correct=0;cycles(1);
  if(dut.remaining<198 || dut.remaining>200)$fatal(1,"previous note duration not retained");
  if(led!=0 && led!=2)$fatal(1,"wrong target");
  // A continuation and rest both add time without requiring an extra strike.
  step_index=2;target_led=0;target_duration_ms=50;cycles(2);
  if(dut.remaining<245)$fatal(1,"continuation duration missing");
  step_index=3;target_duration_ms=30;cycles(2);
  if(dut.remaining<273)$fatal(1,"rest duration missing");
  step_index=4;target_led=4;target_duration_ms=100;paused=1;cycles(1);
  begin: pause_check reg[15:0] held;held=dut.remaining;cycles(20);
   if(dut.remaining!=held || led!=0)$fatal(1,"pause did not freeze cue");end
  paused=0;cycles(600);if(dut.remaining!=0 || led!=4)$fatal(1,"deadline must show target steadily");
  // An early correct strike advances immediately; this hint is not a gate.
  correct=1;step_index=5;target_led=8;cycles(1);correct=0;cycles(1);
  if(led!=0 && led!=8)$fatal(1,"early strike delayed target");
  active=0;cycles(2);if(led!=0 || dut.remaining!=0)$fatal(1,"exit left a stale hint");
  $display("PASS: immediate target, previous duration, continuation/rest accumulation, pause, no blocking, exit");$finish;
 end
endmodule
