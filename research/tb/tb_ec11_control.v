`timescale 1ns/1ps
module tb_ec11_control;
    reg clk = 0, rst_n = 0;
    reg s1_n = 1, s2_n = 1, key_n = 1;
    wire enabled;
    wire [3:0] depth;
    wire timbre_select;
    always #5 clk = ~clk;
    ec11_control #(.DEBOUNCE_CYCLES(2), .LONG_PRESS_CYCLES(20),
                   .LONG_PRESS_ENABLE(1)) dut (
        .clk(clk), .rst_n(rst_n), .s1_n(s1_n),
        .s2_n(s2_n), .key_n(key_n),
        .enabled(enabled), .depth(depth), .timbre_select(timbre_select)
    );
    task settle;
        begin repeat (8) @(negedge clk); end
    endtask
    initial begin
        settle(); rst_n = 1;
        settle();
        if (enabled || depth != 4'd4 || !timbre_select)
            $fatal(1, "EC11 reset state");
        s1_n = 0; settle();
        if (depth != 4'd5) $fatal(1, "first turn not counted once");
        settle();
        if (depth != 4'd5) $fatal(1, "held contact repeated turn");
        s1_n = 1; settle();
        s2_n = 0; settle();
        s1_n = 0; settle();
        if (depth != 4'd4) $fatal(1, "reverse turn failed");
        key_n = 0; settle();
        if (enabled) $fatal(1, "short press toggled before release");
        key_n = 1; settle();
        if (!enabled) $fatal(1, "short release did not enable vibrato");
        key_n = 0; settle();
        key_n = 1; settle();
        if (enabled) $fatal(1, "second short release did not disable vibrato");
        key_n = 0; repeat (35) @(negedge clk);
        if (timbre_select || enabled)
            $fatal(1, "long press did not switch timbre cleanly");
        repeat (40) @(negedge clk);
        if (timbre_select || enabled)
            $fatal(1, "held long press repeated or toggled vibrato");
        key_n = 1; settle();
        if (enabled || timbre_select)
            $fatal(1, "long release toggled vibrato");
        $display("PASS: EC11 rotation, short-release vibrato and one-shot long-press timbre");
        $finish;
    end
endmodule
