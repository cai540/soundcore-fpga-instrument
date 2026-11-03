`timescale 1ns/1ps
module tb_volume_buttons;
    reg clk = 0, rst_n = 0, key_up_n = 1, key_down_n = 1;
    wire [2:0] gain_level;
    always #5 clk = ~clk;
    volume_buttons #(.DEBOUNCE_CYCLES(3)) dut (
        .clk(clk), .rst_n(rst_n), .key_up_n(key_up_n),
        .key_down_n(key_down_n), .gain_level(gain_level)
    );
    task press_up;
        begin
            key_up_n = 0; repeat (12) @(negedge clk);
            key_up_n = 1; repeat (12) @(negedge clk);
        end
    endtask
    task press_down;
        begin
            key_down_n = 0; repeat (12) @(negedge clk);
            key_down_n = 1; repeat (12) @(negedge clk);
        end
    endtask
    initial begin
        repeat (3) @(negedge clk); rst_n = 1;
        if (gain_level != 2) $fatal(1, "initial gain must be 4x");
        key_up_n = 0; repeat (2) @(negedge clk);
        key_up_n = 1; repeat (12) @(negedge clk);
        if (gain_level != 2) $fatal(1, "bounce changed gain");
        press_up();
        if (gain_level != 3) $fatal(1, "one up press should give 6x");
        repeat (50) @(negedge clk);
        if (gain_level != 3) $fatal(1, "holding/releasing retriggered");
        press_up(); press_up();
        if (gain_level != 5) $fatal(1, "upper limit failed");
        press_down();
        if (gain_level != 4) $fatal(1, "one down press should give 8x");
        press_down(); press_down(); press_down(); press_down();
        if (gain_level != 0) $fatal(1, "lower limit failed");
        $display("PASS: volume keys debounce, one step per press and clamp");
        $finish;
    end
endmodule
