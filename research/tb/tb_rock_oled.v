`timescale 1ns/1ps
module tb_rock_oled;
reg clk=0,rst_n=0;
always #1 clk=~clk;
tri1 scl,sda;
oled_status_ssd1315 #(.I2C_DIV(1),.REFRESH_CYCLES(10)) dut(
 .clk(clk),.rst_n(rst_n),.bank(3'd2),.key(4'd0),.timbre(2'd3),.tone_edit(1'b1),.tone_drive(4'd12),
 .volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),.menu_song(8'd0),.menu_mode_select(1'b0),
 .menu_mode_cursor(1'b0),.demo_mode(1'b0),.guide_step(11'd0),.guide_target(3'd7),
 .guide_target_bank(3'd0),.playback_state(2'd0),.auth_pending(1'b0),.remote_write_allowed(1'b0),
 .ble_frame_seen(1'b0),.pad_active(7'd0),.force_levels(56'd0),.contrast(8'd160),
 .lyric_mode(1'b0),.lyric_phrase(7'd0),.lyric_character(5'd0),.lyric_progress(8'd0),
 .capture_payload(88'd0),.oled_scl(scl),.oled_sda(sda));
initial begin
 repeat(3)@(negedge clk);rst_n=1;
 force dut.shown_timbre=2'd3;force dut.shown_tone_edit=1'b1;force dut.shown_tone_drive=4'd12;
 force dut.page_index=3'd2;force dut.column=7'd0;#1;
 if(dut.selected_hanzi==0)$fatal(1,"missing metal first glyph");
 force dut.column=7'd16;#1;if(dut.selected_hanzi==0)$fatal(1,"missing metal second glyph");
 force dut.page_index=3'd0;force dut.column=7'd48;#1;
 if(dut.selected_hanzi==0 || dut.shown_value!=12)$fatal(1,"missing distortion edit");
 force dut.column=7'd64;#1;if(dut.selected_hanzi==0)$fatal(1,"missing distortion second glyph");
 $display("PASS: OLED metal name and distortion value use complete 7-bit glyph IDs");$finish;
end
endmodule
