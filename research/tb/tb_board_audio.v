`timescale 1ns/1ps

module tb_board_audio;
    reg sys_clk = 1'b0;
    always #10 sys_clk = ~sys_clk;
    reg rst_n = 1'b0;
    reg key0 = 1'b1;
    reg key1 = 1'b1;
    wire [7:0] led_o;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    integer nonzero_samples = 0;
    integer max_abs = 0;
    integer magnitude;
    time key0_down_time = 0;
    time first_nonzero_time = 0;

    tang_mega_60k_top dut (
        .sys_clk(sys_clk), .rst_n(rst_n), .key0(key0), .key1(key1),
        .led_o(led_o), .HP_BCK(HP_BCK), .HP_WS(HP_WS),
        .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );

    initial begin
        #40 rst_n = 1'b1;
        #1000 key0 = 1'b0;
        key0_down_time = $time;
        #10000000;
        if (nonzero_samples < 100 || max_abs < 500 ||
            first_nonzero_time == 0 ||
            first_nonzero_time - key0_down_time > 1000000)
            $fatal(1, "Board synth too quiet: nonzero=%0d peak=%0d",
                   nonzero_samples, max_abs);
        $display("PASS: board KEY0 audio, nonzero=%0d peak=%0d first=%0d ns",
                 nonzero_samples, max_abs,
                 first_nonzero_time - key0_down_time);
        $finish;
    end

    always @(posedge sys_clk) begin
        if (rst_n && dut.sample_tick && !key0) begin
            if (dut.audio_sample != 0) begin
                if (first_nonzero_time == 0)
                    first_nonzero_time = $time;
                nonzero_samples = nonzero_samples + 1;
                magnitude = dut.audio_sample < 0
                    ? -dut.audio_sample : dut.audio_sample;
                if (magnitude > max_abs)
                    max_abs = magnitude;
            end
        end
    end
endmodule
