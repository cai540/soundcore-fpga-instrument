`timescale 1ns/1ps

module tb_pt8211_tx;
    reg clk = 1'b0;
    always #10 clk = ~clk; // 50 MHz
    reg rst_n = 1'b0;
    reg signed [15:0] sample_in = 16'h1234;
    wire sample_tick, audio_bclk, audio_ws, audio_din;
    integer frames = 0;
    integer bit_count = 0;
    integer clock_count = 0;
    integer last_frame_clock = 0;
    reg expected_bit;

    pt8211_tx dut (
        .clk_50m(clk), .rst_n(rst_n), .sample_in(sample_in),
        .sample_tick(sample_tick), .audio_bclk(audio_bclk),
        .audio_ws(audio_ws), .audio_din(audio_din)
    );

    initial begin
        #40 rst_n = 1'b1;
        #250000;
        $fatal(1, "DAC serial transmitter timed out");
    end

    always @(posedge clk) begin
        if (rst_n)
            clock_count = clock_count + 1;
        if (rst_n && sample_tick) begin
            if (frames != 0 &&
                (clock_count - last_frame_clock < 1040 ||
                 clock_count - last_frame_clock > 1043))
                $fatal(1, "Audio frame rate differs from 48 kHz");
            last_frame_clock = clock_count;
            frames = frames + 1;
            if (frames == 5) begin
                if (bit_count < 120 || bit_count > 170)
                    $fatal(1, "Unexpected BCLK/frame count: %0d", bit_count);
                $display("PASS: %0d stereo frames, %0d BCLK rising edges",
                         frames, bit_count);
                $finish;
            end
        end
    end

    always @(posedge audio_bclk) begin
        if (rst_n) begin
            bit_count = bit_count + 1;
            if (frames >= 1) begin
                expected_bit = sample_in[15 - dut.slot[3:0]];
                if (audio_din !== expected_bit || audio_ws !== dut.slot[4])
                    $fatal(1, "Serial audio bit or channel select mismatch");
            end
        end
    end
endmodule
