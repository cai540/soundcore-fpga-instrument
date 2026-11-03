`timescale 1ns/1ps
module tb_song_guide_rom;
    reg clk = 0, rst_n = 0;
    reg [1:0] ui_state = 0;
    reg [7:0] song_index = 0;
    reg strike_valid = 0;
    reg [2:0] strike_channel = 0;
    wire [3:0] step_index, song_length;
    wire [2:0] target_pad;
    wire completed, correct_pulse, wrong_pulse;
    wire [6:0] target_led;
    always #5 clk = ~clk;
    song_guide_rom dut (
        .clk(clk), .rst_n(rst_n), .ui_state(ui_state),
        .song_index(song_index), .strike_valid(strike_valid),
        .strike_channel(strike_channel), .step_index(step_index),
        .target_pad(target_pad), .song_length(song_length),
        .completed(completed), .correct_pulse(correct_pulse),
        .wrong_pulse(wrong_pulse), .target_led(target_led)
    );
    task strike;
        input [2:0] pad;
        begin
            @(negedge clk); strike_channel = pad; strike_valid = 1;
            @(posedge clk); #1;
            @(negedge clk); strike_valid = 0;
        end
    endtask
    integer j;
    initial begin
        repeat (3) @(negedge clk); rst_n = 1;
        ui_state = 2; repeat (2) @(negedge clk);
        if (step_index != 0 || target_pad != 0 || target_led != 7'b1)
            $fatal(1, "song 0 start");
        strike(3'd2);
        if (step_index != 0 || !wrong_pulse)
            $fatal(1, "wrong pad advanced");
        strike(3'd0);
        if (step_index != 1 || !correct_pulse || target_pad != 1)
            $fatal(1, "correct pad did not advance");
        ui_state = 3; repeat (2) @(negedge clk);
        strike(3'd1);
        if (step_index != 1 || target_led != 0)
            $fatal(1, "pause failed");
        ui_state = 2; repeat (2) @(negedge clk);
        if (step_index != 1) $fatal(1, "resume reset progress");
        for (j = 1; j < 7; j = j + 1)
            strike(j[2:0]);
        if (!completed || step_index != 7 || target_led != 0)
            $fatal(1, "song 0 finish");
        strike(3'd6);
        if (!completed || step_index != 7 || correct_pulse)
            $fatal(1, "completed song advanced");
        ui_state = 0; repeat (2) @(negedge clk);
        ui_state = 1; song_index = 1; repeat (2) @(negedge clk);
        ui_state = 2; repeat (2) @(negedge clk);
        if (completed || step_index != 0 || target_pad != 0 ||
            song_length != 8)
            $fatal(1, "song 1 start");
        strike(3'd0); strike(3'd2); strike(3'd4); strike(3'd6);
        strike(3'd5); strike(3'd3); strike(3'd1); strike(3'd0);
        if (!completed || step_index != 8)
            $fatal(1, "song 1 finish");
        $display("PASS: offline guide advances only on correct strikes, holds pause, resets on song change");
        $finish;
    end
endmodule
