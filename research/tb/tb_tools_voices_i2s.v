`timescale 1ns/1ps
module tb_tools_voices_i2s;
 reg clk=0,rst_n=0;always #1 clk=~clk;
 reg[31:0] gates=0;reg[223:0] notes=0;wire[5:0] active;
 wire fault,valid,tick,bck,ws,din;wire[8:0]cycles;wire signed[15:0]pcm;
 playable_synth32 #(.DIAGNOSTIC_AVAILABLE(1),.EXPRESSION_TEXTURE(2)) synth(
  .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gates),.note_index(notes),
  .velocity({32{8'd16}}),.expression({32{8'd16}}),.bend(8'd128),.timbre(1'b1),
  .diagnostic_sine(1'b1),.active_count(active),.deadline_fault(fault),.max_frame_cycles(cycles),.sample_out(pcm),.sample_valid(valid));
 i2s_stereo_tx tx(.clk_audio(clk),.rst_n(rst_n),.sample_in(pcm),.sample_tick(tick),.i2s_bclk(bck),.i2s_lrclk(ws),.i2s_sd(din));
 integer slot=0,frames=0,f, i;reg started=0;reg[15:0]word,expected;reg[31:0]other_phase;
 always @(posedge clk)if(rst_n && tick)started=1;
 always @(posedge bck)if(rst_n && started)begin
  if(ws!==(slot>=32))$fatal(1,"I2S word select");
  if(slot==1)expected=pcm;
  if(slot>=1 && slot<=16)begin word[16-slot]=din;if(din!==expected[16-slot])$fatal(1,"I2S left PCM mismatch");end
  if(slot>=33 && slot<=48 && din!==expected[48-slot])$fatal(1,"I2S right PCM mismatch");
  if(slot==63)begin
   frames=frames+1;slot=0;
   if(frames>4000 && frames<=20384)$fwrite(f,"%0d\n",$signed(word));
   if(frames==20384)begin
    if(active!=32 || fault || cycles>=256)$fatal(1,"32 voices/sample deadline active=%d cycles=%d",active,cycles);
    gates[3]=0;
   end
   if(frames==28384)begin
    if(active!=31)$fatal(1,"independent release did not leave 31");
    other_phase=synth.synth.phase[4];notes[3*7+:7]=60;gates[3]=1;
   end
   if(frames==30384)begin
    if(active!=32 || synth.synth.phase[4]==other_phase || synth.note_frame[21+:7]!=60)$fatal(1,"independent retune");
    $fclose(f);$display("PASS:32 audible original-engine voices, independent release/retrigger/retune, exact stereo I2S; max_frame_cycles=%0d",cycles);$finish;
   end
  end else slot=slot+1;
 end
 initial begin
  for(i=0;i<32;i=i+1)notes[i*7+:7]=24+i;
  f=$fopen("build/acceptance_20261102/voices32_i2s.txt","w");
  repeat(4)@(negedge clk);rst_n=1;gates=32'hffffffff;
 end
 initial begin #18000000;$fatal(1,"voice render timeout");end
endmodule
