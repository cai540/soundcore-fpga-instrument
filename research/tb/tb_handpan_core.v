`timescale 1ns/1ps
module tb_handpan_core;
reg clk=0,rst_n=0,physical_hit=0,remote_hit=0,absolute_note=0;
always #41 clk=~clk;
reg[2:0]pad=3;reg[1:0]style=1;reg[6:0]exact_note=37;
wire bck,ws,din;
wire[31:0]expected_manual,expected_exact;
note_step_table72 manual(.note_index(7'd31),.phase_step(expected_manual));
note_step_table72 exact(.note_index(7'd37),.phase_step(expected_exact));
pressure_i2s_additive32_core #(.BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),.REMOTE_ENABLE(1),
 .HANDPAN_AVAILABLE(1),.HEADPHONE_OUTPUT(0),.EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1),.CAL_SAMPLES(2)) dut(
 .clk_audio(clk),.rst_n(rst_n),.adc_miso(1'b0),.enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
 .key_up_n(1'b1),.key_down_n(1'b1),.panel_bank(3'd2),.panel_key(4'd0),.panel_timbre(1'b1),
 .panel_handpan_style(style),.panel_volume_level(5'd16),.panel_effect_mask(3'd0),.panel_vibrato_enabled(1'b0),
 .panel_vibrato_depth(4'd4),.guide_override(1'b0),.guide_pad(3'd0),.guide_note(7'd0),
 .remote_absolute(absolute_note),.remote_note(exact_note),.remote_strike_valid(remote_hit),.remote_strike_channel(pad),
 .remote_strike_velocity(8'd190),.remote_pressed(7'd0),.remote_session_active(1'b1),
 .remote_command_valid(1'b0),.remote_command_type(8'd0),.remote_command_value(8'd0),
 .autoplay_note_gate(1'b0),.autoplay_note_index(7'd0),.autoplay_timbre(1'b1),
 .dac_bclk(bck),.dac_lrclk(ws),.dac_din(din));
task frames;input integer n;begin repeat(n)begin @(posedge dut.sample_tick);@(negedge clk);end end endtask
integer n,nonzero=0;
always @(posedge dut.sample_tick)if(rst_n && dut.output_sample!=0)nonzero=nonzero+1;
initial begin
 force dut.strike_valid=physical_hit;force dut.strike_channel=pad;force dut.strike_velocity=8'd210;
 repeat(3)@(negedge clk);rst_n=1;frames(4);
 @(negedge clk);physical_hit=1;@(negedge clk);physical_hit=0;frames(4);
 if(dut.handpan_instrument.sound.step[0]!=expected_manual || dut.handpan_instrument.sound.strength[0]!=210)$fatal(1,"physical manual mapping/force");
 absolute_note=1;pad=5;@(negedge clk);remote_hit=1;@(negedge clk);remote_hit=0;frames(4);
 if(dut.handpan_instrument.sound.step[1]!=expected_exact || dut.handpan_instrument.sound.strength[1]!=190)$fatal(1,"exact phone pitch was quantized");
 absolute_note=0;pad=3;@(negedge clk);remote_hit=1;@(negedge clk);remote_hit=0;frames(300);
 if(dut.handpan_instrument.sound.step[2]!=expected_manual || nonzero<250)$fatal(1,"phone pad or final output missing");
 if(dut.handpan_instrument.sound.overflow)$fatal(1,"ordinary events overflow");
 style=2;absolute_note=1;@(negedge clk);remote_hit=1;@(negedge clk);remote_hit=0;frames(300);
 if(dut.handpan_instrument.metal.overflow || dut.handpan_sample==0)$fatal(1,"metal route missing or missed deadline");
 if(dut.handpan_sample!==dut.handpan_instrument.metal_sample)$fatal(1,"metal bypassed nonlinear path");
 style=0;frames(3);if(dut.handpan_sample!=0 || dut.handpan_enabled)$fatal(1,"song/melodic override not silent");
 $display("PASS: product audio core routes physical and phone pentatonic pads, exact chromatic notes, velocity, mixed output and melodic/song override");$finish;
end
endmodule
