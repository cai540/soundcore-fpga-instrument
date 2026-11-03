`timescale 1ns/1ps
module tb_song_guide_rest;
    reg clk=0,rst_n=0,hit=0;
    reg [1:0] state=0;
    reg [2:0] bank=0,pad=0;
    wire [10:0] step,length;
    wire [2:0] target_bank,target_pad;
    wire [15:0] duration;
    wire complete,correct,wrong;
    wire [6:0] led;
    always #5 clk=~clk;
    song_guide_long #(.LENGTH0(3),
        .ROM0_FILE("tb/song_event_fixture.mem")) dut (
        .clk(clk),.rst_n(rst_n),.ui_state(state),.song_select(1'b0),
        .strike_valid(hit),.strike_bank(bank),.strike_pad(pad),
        .step_index(step),.song_length(length),.target_bank(target_bank),
        .target_pad(target_pad),.target_duration_ms(duration),
        .completed(complete),.correct_pulse(correct),.wrong_pulse(wrong),
        .target_led(led)
    );
    initial begin
        repeat(2) @(negedge clk);rst_n=1;state=2;
        repeat(2) @(negedge clk);
        hit=1;@(negedge clk);hit=0;
        repeat(2) @(negedge clk);
        if(step!=2 || target_bank!=1 || target_pad!=0 || led!=7'b0000001)
            $fatal(1,"guide failed to skip rest");
        bank=1;hit=1;@(negedge clk);hit=0;
        if(!complete || step!=3) $fatal(1,"guide completion after rest failed");
        $display("PASS: guide skips rests, preserves bank and ends");
        $finish;
    end
endmodule
