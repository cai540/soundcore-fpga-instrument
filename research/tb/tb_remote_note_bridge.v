`timescale 1ns/1ps
module tb_remote_note_bridge;
    reg clk=0,rst_n=0,write_allowed=0,command_valid=0;
    reg physical_strike=0,voice_ready=1;
    reg [7:0] command_type=0,command_value=0,command_value2=0;
    wire [6:0] remote_pressed;
    wire remote_strike_valid;
    wire [2:0] remote_strike_channel;
    wire [7:0] remote_strike_velocity;
    always #5 clk=~clk;
    remote_note_bridge #(.LEASE_CYCLES(20)) dut (
        .clk(clk),.rst_n(rst_n),.write_allowed(write_allowed),
        .command_valid(command_valid),.command_type(command_type),
        .command_value(command_value),.command_value2(command_value2),
        .physical_strike(physical_strike),.voice_ready(voice_ready),
        .remote_pressed(remote_pressed),
        .remote_strike_valid(remote_strike_valid),
        .remote_strike_channel(remote_strike_channel),
        .remote_strike_velocity(remote_strike_velocity)
    );
    task command;
        input [7:0] typ,val,val2;
        begin
            @(negedge clk);command_type=typ;command_value=val;
            command_value2=val2;command_valid=1;
            @(negedge clk);command_valid=0;
        end
    endtask
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        command(8'h16,8'd0,8'd100);
        if(remote_pressed!=0 || remote_strike_valid)
            $fatal(1,"locked command accepted");
        write_allowed=1;voice_ready=0;
        command(8'h16,8'd0,8'd100);
        if(remote_pressed!=1 || remote_strike_valid)
            $fatal(1,"pending phone note should wait for a slot");
        voice_ready=1;physical_strike=1;
        @(negedge clk);
        if(remote_strike_valid) $fatal(1,"physical strike lost priority");
        physical_strike=0;
        #1;
        if(!remote_strike_valid || remote_strike_channel!=0 ||
           remote_strike_velocity!=100)
            $fatal(1,"pending phone note not delivered");
        @(negedge clk);
        if(remote_strike_valid) $fatal(1,"phone note retriggered");
        command(8'h16,8'd1,8'd180);
        if(remote_pressed!=7'b11) $fatal(1,"two phone keys not held");
        command(8'h17,8'd0,0);
        if(remote_pressed!=7'b10) $fatal(1,"NOTE_OFF cleared another key");
        command(8'h21,8'b0000010,0);
        repeat(10) @(negedge clk);
        if(remote_pressed!=7'b10) $fatal(1,"lease refresh lost held key");
        repeat(22) @(negedge clk);
        if(remote_pressed!=0) $fatal(1,"lost NOTE_OFF remained stuck");
        command(8'h16,8'd2,8'd80);
        write_allowed=0;
        @(negedge clk);
        if(remote_pressed!=0 || remote_strike_valid)
            $fatal(1,"authorization expiry left a phone key held");
        $display("PASS: remote note queue, physical priority, release and revoke");
        $finish;
    end
endmodule
