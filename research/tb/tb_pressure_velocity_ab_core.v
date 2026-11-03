`timescale 1ns/1ps
module tb_pressure_velocity_ab_core;
    reg clk_audio = 1'b0;
    reg rst_n = 1'b0;
    reg key_up_n = 1'b1;
    reg key_down_n = 1'b1;
    wire dac_bclk, dac_lrclk, dac_din;
    integer weak_peak = 0;
    integer strong_peak = 0;
    integer magnitude;
    integer i;

    always #40 clk_audio = ~clk_audio;
    pressure_velocity_ab_core dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .key_up_n(key_up_n), .key_down_n(key_down_n),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk), .dac_din(dac_din)
    );

    initial begin
        repeat (4) @(negedge clk_audio);
        rst_n = 1'b1;
        key_up_n = 1'b0;
        repeat (2300) @(posedge dut.sample_tick);
        if (dut.velocity[7:0] !== 8'd60)
            $fatal(1, "weak key did not select velocity 60");
        for (i = 0; i < 512; i = i + 1) begin
            @(posedge dut.sample_tick);
            magnitude = dut.audio_sample < 0 ? -dut.audio_sample : dut.audio_sample;
            if (magnitude > weak_peak) weak_peak = magnitude;
        end
        key_up_n = 1'b1;
        key_down_n = 1'b0;
        repeat (4) @(posedge dut.sample_tick);
        if (dut.velocity[7:0] !== 8'd240)
            $fatal(1, "strong key did not select velocity 240");
        for (i = 0; i < 512; i = i + 1) begin
            @(posedge dut.sample_tick);
            magnitude = dut.audio_sample < 0 ? -dut.audio_sample : dut.audio_sample;
            if (magnitude > strong_peak) strong_peak = magnitude;
        end
        if (weak_peak == 0 || strong_peak < 3 * weak_peak ||
            strong_peak > 5 * weak_peak)
            $fatal(1, "audio amplitude ratio not near four: weak=%0d strong=%0d",
                   weak_peak, strong_peak);
        $display("PASS: fixed-velocity A/B audio peak %0d -> %0d", weak_peak, strong_peak);
        $finish;
    end
    initial begin
        #300000000;
        $fatal(1, "A/B diagnostic timed out");
    end
endmodule
