`timescale 1ns/1ps
module tb_realtime_voice_integration;
    reg clk=0,rst_n=0,valid=0,physical=0;
    reg [7:0] mask=0,attacks=0;
    reg [6:0] pressed=0;
    reg [1:0] divider=0;
    wire [6:0] held;
    wire fire,voice_ready;
    wire [2:0] pad;
    wire [7:0] velocity;
    wire [31:0] gate;
    integer i,pcount,rcount;
    always #5 clk=~clk;
    always @(posedge clk)divider<=divider+1'b1;
    remote_note_bridge #(.REALTIME_ENABLED(1),.LEASE_CYCLES(10000),.PENDING_LIMIT_CYCLES(200)) bridge(
        .clk(clk),.rst_n(rst_n),.write_allowed(1'b1),.command_valid(valid),.command_type(8'h24),
        .command_value(mask),.command_value2(attacks),.command_payload({32'd0,8'd190,attacks,mask}),
        .physical_strike(physical),.voice_ready(voice_ready),.remote_pressed(held),
        .remote_strike_valid(fire),.remote_strike_channel(pad),.remote_strike_velocity(velocity));
    strike_voice_allocator32 #(.BANKED_MODE(1),.REMOTE_ENABLE(1),.HOLD_SAMPLES(2),.RELEASE_SAMPLES(2)) pool(
        .clk(clk),.rst_n(rst_n),.sample_tick(divider==0),.strike_valid(physical),.strike_channel(3'd0),
        .strike_velocity(8'd150),.pressed(pressed),.level_valid(1'b0),.level_channel(3'd0),.level_velocity(8'd0),
        .remote_strike_valid(fire),.remote_strike_channel(pad),.remote_strike_velocity(velocity),.remote_pressed(held),
        .bank(3'd2),.banked_enable(1'b1),.sustain(1'b0),.clear_all(1'b0),.gate(gate),.remote_voice_ready(voice_ready));
    task packet;
        input [6:0] m,a;
        begin @(negedge clk);mask=m;attacks=a;valid=1;@(negedge clk);valid=0;end
    endtask
    task counts;
        input integer p,r;
        begin
            repeat(40)@(negedge clk);pcount=0;rcount=0;
            for(i=0;i<32;i=i+1)if(gate[i])begin
                if(pool.active_remote[i])rcount=rcount+1;else pcount=pcount+1;
            end
            if(pcount!=p || rcount!=r)$fatal(1,"voice ownership got %0d/%0d expected %0d/%0d",pcount,rcount,p,r);
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        pressed=1;physical=1;@(negedge clk);physical=0;
        packet(7'h7f,7'h7f);counts(1,7);
        packet(7'h7e,0);counts(1,6);
        repeat(12)begin packet(7'h7f,1);packet(7'h7e,0);end
        counts(1,6);
        packet(0,0);counts(1,0);
        pressed=0;counts(0,0);
        $display("PASS: real-time chord reaches real allocator; rapid same-pad release preserves six other phone notes and physical owner");$finish;
    end
endmodule
