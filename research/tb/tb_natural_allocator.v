`timescale 1ns/1ps
module tb_natural_allocator;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,sample_tick=0,strike_valid=0,remote_strike_valid=0;
reg [2:0]strike_channel=0,remote_strike_channel=0,bank=2,guide_pad=0;
reg [3:0] key=0;reg guide_override=0,remote_absolute=0;
reg [6:0] guide_note=0,remote_note=0,pressed=127,remote_pressed=127;
wire [31:0]gate,remote_owner;wire[223:0]note_index;wire[255:0]velocity;wire[95:0]voice_zone;wire ready;
strike_voice_allocator32 #(.BANKED_MODE(1),.REMOTE_ENABLE(1),.HOLD_SAMPLES(1),.RELEASE_SAMPLES(2)) dut(
.clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),.strike_valid(strike_valid),.strike_channel(strike_channel),.strike_velocity(8'd200),
.level_valid(1'b0),.level_channel(3'd0),.level_velocity(8'd0),.pressed(pressed),
.remote_strike_valid(remote_strike_valid),.remote_strike_channel(remote_strike_channel),.remote_strike_velocity(8'd180),.remote_pressed(remote_pressed),
.key(key),.bank(bank),.banked_enable(1'b1),.sustain(1'b0),.clear_all(1'b0),
.guide_override(guide_override),.guide_pad(guide_pad),.guide_note(guide_note),.remote_absolute(remote_absolute),.remote_note(remote_note),
.gate(gate),.note_index(note_index),.velocity(velocity),.voice_zone(voice_zone),.remote_voice_ready(ready),.remote_owner(remote_owner));
integer i;reg[4:0]slot;
task strike;input integer pad_i,expected;input phone;begin
 @(negedge clk);slot=dut.chosen_voice;strike_channel=pad_i;remote_strike_channel=pad_i;
 strike_valid=!phone;remote_strike_valid=phone;
 @(negedge clk);strike_valid=0;remote_strike_valid=0;sample_tick=1;
 @(negedge clk);sample_tick=0;
 if(!gate[slot] || note_index[slot*7+:7]!==expected || remote_owner[slot]!=phone)$fatal(1,"allocated pitch/owner mismatch slot=%0d gate=%b note=%0d mapped=%0d expected=%0d",slot,gate[slot],note_index[slot*7+:7],dut.mapped_note,expected);
end endtask
initial begin
 repeat(3)@(negedge clk);rst_n=1;strike_channel=7;@(negedge clk);
 strike(0,24,0);strike(1,26,0);strike(6,35,0);
 key=5;strike(0,29,0);bank=4;strike(6,64,0);
 guide_override=1;guide_pad=2;guide_note=70;strike(2,70,0);
 strike(1,55,0);strike(2,70,1);
 remote_absolute=1;remote_note=1;strike(6,1,1);
 if(!gate[5])$fatal(1,"phone note retired physical owner");
 $display("PASS: natural and accidental guide allocation, exact remote pitch, physical/phone isolation, seven-bit high pitches");$finish;
end
endmodule
