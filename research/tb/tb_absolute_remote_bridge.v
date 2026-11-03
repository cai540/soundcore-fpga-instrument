`timescale 1ns/1ps
module tb_absolute_remote_bridge;
reg clk=0,rst_n=0,command_valid=0,physical_strike=0,voice_ready=0;always #5 clk=~clk;
reg[7:0]command_type=0,command_value=0,command_value2=0;reg[111:0]command_payload=0;
wire[6:0]remote_pressed,remote_strike_note;wire[2:0]remote_strike_channel;wire[7:0]remote_strike_velocity;
wire remote_strike_valid,remote_absolute;wire[48:0]remote_notes;integer fired=0,i;
remote_note_bridge #(.REALTIME_ENABLED(1),.LEASE_CYCLES(1000),.PENDING_LIMIT_CYCLES(20)) dut(
.clk(clk),.rst_n(rst_n),.write_allowed(1'b1),.command_valid(command_valid),.command_type(command_type),.command_value(command_value),.command_value2(command_value2),.command_payload(command_payload),.physical_strike(physical_strike),.voice_ready(voice_ready),.remote_pressed(remote_pressed),.remote_strike_valid(remote_strike_valid),.remote_strike_channel(remote_strike_channel),.remote_strike_velocity(remote_strike_velocity),.remote_absolute(remote_absolute),.remote_strike_note(remote_strike_note),.remote_notes(remote_notes));
always @(posedge clk)if(remote_strike_valid)begin
 if(remote_strike_note!=70-remote_strike_channel)$fatal(1,"slot lost its exact pitch");fired=fired+1;
end
task snapshot;input[6:0]held,attacks;begin
 @(negedge clk);command_type=8'h25;command_value=held;command_value2=attacks;command_payload[23:16]=200;
 for(i=0;i<7;i=i+1)command_payload[24+i*8+:8]=70-i;
 command_valid=1;@(negedge clk);command_valid=0;
end endtask
initial begin
 repeat(3)@(negedge clk);rst_n=1;
 snapshot(127,127);repeat(5)@(negedge clk);snapshot(0,0);voice_ready=1;repeat(30)@(negedge clk);
 if(fired || remote_pressed)$fatal(1,"released snapshots replayed a queued tail");
 voice_ready=0;snapshot(127,127);repeat(22)@(negedge clk);voice_ready=1;repeat(10)@(negedge clk);
 if(fired)$fatal(1,"expired attacks replayed after contention");
 snapshot(0,0);physical_strike=1;snapshot(127,127);repeat(5)@(negedge clk);
 if(fired)$fatal(1,"phone preempted physical input");
 physical_strike=0;repeat(10)@(negedge clk);
 if(fired!=7 || !remote_absolute || remote_pressed!=127)$fatal(1,"seven concurrent exact owners were not serviced");
 snapshot(0,0);repeat(10)@(negedge clk);if(fired!=7 || remote_pressed)$fatal(1,"release reattacked");
 $display("PASS: seven exact remote owners, authoritative release, no stale replay, bounded contention and physical priority");$finish;
end
endmodule
