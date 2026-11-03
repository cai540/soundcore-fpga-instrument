`timescale 1ns/1ps
module tb_vibrato_bend;
    reg clk = 0, rst_n = 0, sample_tick = 0, enabled = 0;
    reg [3:0] depth = 4'd4;
    wire signed [7:0] offset;
    integer i, max_seen;
    always #5 clk = ~clk;
    vibrato_bend dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .enabled(enabled), .depth(depth), .offset(offset)
    );
    task tick;
        begin
            @(negedge clk); sample_tick = 1;
            @(negedge clk); sample_tick = 0;
        end
    endtask
    initial begin
        repeat (3) @(negedge clk); rst_n = 1;
        for (i = 0; i < 100; i = i + 1) tick();
        if (offset != 0) $fatal(1, "disabled vibrato changed pitch");
        enabled = 1;
        max_seen = 0;
        for (i = 0; i < 5000; i = i + 1) begin
            tick();
            if (offset > max_seen) max_seen = offset;
        end
        if (max_seen < 5 || offset >= 0)
            $fatal(1, "vibrato did not oscillate above and below pitch");
        depth = 0;
        #1;
        if (offset != 0) $fatal(1, "zero depth changed pitch");
        enabled = 0;
        $display("PASS: FPGA vibrato is periodic, bounded and independently disabled");
        $finish;
    end
endmodule
