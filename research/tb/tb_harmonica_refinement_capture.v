`timescale 1ns/1ps
// Actual mono synthesis RTL; preview clock spacing is shortened to4cycles.
// All note time/phase/envelope still advance exactly once per48kHz sample.
// Full32voice/256clock real-output scheduling is verified separately.
module tb_harmonica_refinement_capture;
 reg clk=0,rst_n=0,tick=0,local_gate=0,timbre=1,use_song=0,song_run=0;
 always #5 clk=~clk;
 reg[6:0] local_note=127;reg[7:0] velocity=176,expression=176;
 wire[6:0] song_note;wire song_gate;wire[31:0] step;
 wire gate=use_song ? song_gate:local_gate;
 wire[6:0] note=use_song ? song_note:local_note;
 wire signed[15:0] before_sound,after_sound,tonal_sound;
 note_step_table72 pitch(.note_index(note),.phase_step(step));
 song_event_player #(.CLK_HZ(192000),.LENGTH0(246),.LENGTH1(0),.ARTICULATION0_GAP_MS(12),
  .ROM0_FILE("D:/FPGA/Projects/soundcore_2026/songs/rom_product_songs/song_0.mem")) player(
  .clk(clk),.rst_n(rst_n),.run(song_run),.pause(1'b0),.restart(1'b0),.song_select(1'b0),.key(4'd5),
  .note_index(song_note),.note_gate(song_gate));
 harmonica_baseline_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) old(
  .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(step),.velocity(velocity),
  .expression(expression),.pitch_index(note),.timbre(timbre),.sample_out(before_sound));
 synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) revised(
  .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(step),.velocity(velocity),
  .expression(expression),.pitch_index(note),.timbre(timbre),.sample_out(after_sound));
 synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) tonal(
  .clk(clk),.rst_n(rst_n),.sample_tick(tick && !use_song),.gate(gate),.phase_step(step),.velocity(velocity),
  .expression(expression),.pitch_index(note),.timbre(timbre),.sample_out(tonal_sound));
 integer n,f,erhu_checks=0,attack_checks=0;reg[15:0] previous_envelope;
 task frame;begin tick=1;@(negedge clk);tick=0;repeat(3)@(negedge clk);
  if((^after_sound)===1'bx || (^before_sound)===1'bx)begin
   $display("debug n=%d old/new=%h/%h step=%h phase=%h/%h wave=%h/%h envelope=%h/%h drift=%h/%h",n,before_sound,after_sound,step,old.phase,revised.phase,old.texture_wave,revised.texture_wave,old.envelope,revised.envelope,old.texture_drift,revised.texture_drift);
   $display("weights old/new %h/%h prepared %h/%h",old.expressive_instrument.colour.weight[0],revised.expressive_instrument.colour.weight[0],old.expressive_instrument.colour.lower_weights,revised.expressive_instrument.colour.lower_weights);
   $fatal(1,"unknown synthesis sample");
  end
 end endtask
 task reset;begin rst_n=0;tick=0;local_gate=0;song_run=0;repeat(4)@(negedge clk);rst_n=1;end endtask
 initial begin
  force tonal.expressive_instrument.colour.noise_product=27'sd0;
  reset();f=$fopen("build/harmonica_refinement_20261102/phrase.tsv","w");
  for(n=0;n<288000;n=n+1)begin
   local_gate=(n>=4800 && n<33600)||(n>=38400 && n<67200)||(n>=72000 && n<100800)||
    (n>=105600 && n<134400)||(n>=139200 && n<163200 && n%4000<3000)||(n>=168000 && n<280000);
   local_note=n<38400 ? 24:n<72000 ? 28:n<105600 ? 31:n<139200 ? 36:n<168000 ? 28:36;
   velocity=n<38400 ? 96:176;expression=n<38400 ? 80:n<72000 ? 224:n<105600 ? 128:n<168000 ? 208:
    (n<264000 ? 64+(n-168000)/600:224);
   frame();$fdisplay(f,"%0d %0d %0d %0d %0d",before_sound,after_sound,tonal_sound,revised.envelope,local_gate);
  end
  $fclose(f);$display("PASS: actual old/new/tonal48kHz reed phrase captured");
  // The unchanged bow includes identical random-state history, not merely
  // matching coefficient metadata. Check every rendered sample from reset.
  timbre=0;use_song=0;reset();velocity=176;expression=176;local_note=42;
  for(n=0;n<24000;n=n+1)begin local_gate=n>=1000 && n<18000;frame();
   if(after_sound!==before_sound)$fatal(1,"bow waveform changed at sample%0d: %d/%d",n,before_sound,after_sound);
   erhu_checks=erhu_checks+1;
  end
  $display("PASS: %0d bow PCM samples bit-exact to A623",erhu_checks);
  timbre=1;use_song=1;reset();song_run=1;velocity=176;expression=176;
  f=$fopen("build/harmonica_refinement_20261102/zuguo20.tsv","w");
  for(n=0;n<960000;n=n+1)begin frame();$fdisplay(f,"%0d %0d",before_sound,after_sound);end
  $fclose(f);$display("PASS: actual native player20second old/new reed excerpt captured");$finish;
 end
endmodule
