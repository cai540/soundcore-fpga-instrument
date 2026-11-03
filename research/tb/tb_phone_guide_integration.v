`timescale 1ns/1ps
module tb_phone_guide_integration;
    reg clk=0,rst_n=0,command_valid=0;
    reg [7:0] command_type=0,command_value=0,command_value2=0;
    wire [6:0] held,guide_led;
    wire fire,done,correct,wrong;
    wire [2:0] channel,target;
    wire [7:0] velocity;
    wire [3:0] step,length;
    always #5 clk=~clk;
    remote_note_bridge notes (
        .clk(clk),.rst_n(rst_n),.write_allowed(1'b1),
        .command_valid(command_valid),.command_type(command_type),
        .command_value(command_value),.command_value2(command_value2),
        .physical_strike(1'b0),.voice_ready(1'b1),
        .remote_pressed(held),.remote_strike_valid(fire),
        .remote_strike_channel(channel),.remote_strike_velocity(velocity)
    );
    song_guide_rom guide (
        .clk(clk),.rst_n(rst_n),.ui_state(2'd2),.song_index(8'd0),
        .strike_valid(fire),.strike_channel(channel),
        .step_index(step),.target_pad(target),.song_length(length),
        .completed(done),.correct_pulse(correct),.wrong_pulse(wrong),
        .target_led(guide_led)
    );
    task press;
        input [7:0] pad;
        begin
            @(negedge clk);command_type=8'h16;command_value=pad;
            command_value2=8'd176;command_valid=1;
            @(negedge clk);command_valid=0;
            repeat(4)@(negedge clk);
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        repeat(3)@(negedge clk);
        if(target!=0 || step!=0)$fatal(1,"guide did not start at pad 0");
        press(0);
        if(step!=1 || target!=1 || guide_led!=7'b0000010)
            $fatal(1,"phone correct key did not advance guide");
        press(3);
        if(step!=1)$fatal(1,"wrong phone key advanced guide");
        press(1);
        if(step!=2 || target!=2)$fatal(1,"next phone key did not advance");
        $display("PASS: phone NOTE_ON advances only correct guide notes");
        $finish;
    end
endmodule
