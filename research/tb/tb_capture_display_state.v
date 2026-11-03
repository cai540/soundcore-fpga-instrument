`timescale 1ns/1ps
module tb_capture_display_state;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,link=1,valid=0,receiving=0,playing=0,guiding=0,paused=0,finished=0;
 reg [87:0] payload=0;wire [87:0] shown;
 reg [9:0] step=0;reg [2:0] pad=0,bank=0;
 capture_display_state #(.LEASE_CYCLES(40)) dut(.clk(clk),.rst_n(rst_n),.link_active(link),.summary_valid(valid),
  .summary_payload(payload),.score_receiving(receiving),.score_playing(playing),.score_guiding(guiding),
  .score_paused(paused),.score_finished(finished),.score_step(step),.score_count(10'd66),
  .score_received(10'd12),.score_expected(10'd100),.score_bank(bank),.score_pad(pad),.display_payload(shown));
 task check;input condition;input [511:0]message;begin if(!condition)$fatal(1,"%s",message);end endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  payload=0;payload[7:0]=1;payload[15:8]=1;payload[39:24]=120;valid=1;
  @(negedge clk);valid=0;check(shown[15:8]==1,"phone recording phase");
  repeat(41)@(negedge clk);check(shown[15:8]==0,"phone lease expires without commands");
  playing=1;step=12;pad=4;bank=3;link=0;#1;
  check(shown[15:8]==10 && shown[39:24]==12 && shown[55:40]==66,"autonomous play survives disconnect");
  check(shown[79:72]==85,"actual device pitch");
  paused=1;#1;check(shown[15:8]==12,"pause explicit");
  paused=0;playing=0;guiding=1;#1;check(shown[15:8]==11,"guide distinct from autoplay");
  finished=1;#1;check(shown[15:8]==13,"finish explicit");
  link=1;payload[15:8]=2;valid=1;@(negedge clk);valid=0;#1;
  check(shown[15:8]==2,"new source selection can dismiss completed playback");
  guiding=0;finished=0;receiving=1;#1;
  check(shown[15:8]==9 && shown[39:24]==12 && shown[55:40]==100,"transfer owns confirmed counts");
  receiving=0;link=0;@(negedge clk);#1;check(shown[15:8]==0,"stop restores normal screen");
  $display("PASS: leased phone summary, autonomous progress/guide/pause/end, disconnect and stop");$finish;
 end
endmodule
