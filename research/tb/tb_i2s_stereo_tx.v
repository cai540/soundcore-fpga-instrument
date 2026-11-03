`timescale 1ns/1ps

module tb_i2s_stereo_tx;
    reg clk_audio = 1'b0;
    always #40.690 clk_audio = ~clk_audio; // nominal 12.288 MHz

    reg rst_n = 1'b0;
    reg signed [15:0] sample_in = 16'h1234;
    wire sample_tick;
    wire i2s_bclk, i2s_lrclk, i2s_sd;
    integer clk_count = 0;
    integer last_tick = -1;
    integer ticks = 0;
    integer last_bclk = -1;
    integer bclk_edges = 0;
    integer slot = 0;
    integer frames = 0;
    reg started = 1'b0;
    reg [15:0] expected_word = 16'd0;
    reg expected_bit;

    i2s_stereo_tx dut (
        .clk_audio(clk_audio), .rst_n(rst_n), .sample_in(sample_in),
        .sample_tick(sample_tick), .i2s_bclk(i2s_bclk),
        .i2s_lrclk(i2s_lrclk), .i2s_sd(i2s_sd)
    );

    initial begin
        repeat (4) @(posedge clk_audio);
        rst_n = 1'b1;
        #500000;
        $fatal(1, "I2S test timed out");
    end

    always @(posedge clk_audio) begin
        if (rst_n) begin
            clk_count = clk_count + 1;
            if (sample_tick) begin
                if (last_tick != -1 && clk_count - last_tick != 256)
                    $fatal(1, "Frame interval was %0d input clocks, not 256",
                           clk_count - last_tick);
                last_tick = clk_count;
                ticks = ticks + 1;
                started = 1'b1;
            end
        end
    end

    // I2S receiver samples on rising BCLK. Every frame has 64 BCLKs.
    always @(posedge i2s_bclk) begin
        if (rst_n && started) begin
            if (last_bclk != -1 && clk_count - last_bclk != 4)
                $fatal(1, "BCLK interval was %0d input clocks, not 4",
                       clk_count - last_bclk);
            last_bclk = clk_count;
            bclk_edges = bclk_edges + 1;

            if (i2s_lrclk !== (slot >= 32))
                $fatal(1, "LRCLK mismatch at slot %0d", slot);
            if (slot == 1)
                expected_word = sample_in;

            if (slot >= 1 && slot <= 16)
                expected_bit = expected_word[16-slot];
            else if (slot >= 33 && slot <= 48)
                expected_bit = expected_word[48-slot];
            else
                expected_bit = 1'b0;
            if (i2s_sd !== expected_bit)
                $fatal(1, "DIN mismatch at slot %0d: got %b expected %b",
                       slot, i2s_sd, expected_bit);

            // Change the input in the middle of a frame. The transmitted
            // left and right words must still be one coherent held sample.
            if (slot == 20)
                sample_in <= (sample_in == 16'h1234) ? 16'hfedc : 16'h1234;

            if (slot == 63) begin
                frames = frames + 1;
                slot = 0;
                if (frames == 6) begin
                    if (ticks < 6 || bclk_edges != 384)
                        $fatal(1, "Unexpected ticks or BCLK count: %0d %0d",
                               ticks, bclk_edges);
                    $display("PASS: standard I2S 48k/16-bit stereo framing");
                    $finish;
                end
            end else
                slot = slot + 1;
        end
    end
endmodule
