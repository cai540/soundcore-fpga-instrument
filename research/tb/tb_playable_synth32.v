`timescale 1ns/1ps

module tb_playable_synth32;
    reg clk = 1'b0;
    always #40.690 clk = ~clk; // nominal 12.288 MHz
    reg rst_n = 1'b0;
    reg [31:0] gate = 32'hffffffff;
    reg [191:0] note_index = {192{1'bx}};
    reg [255:0] velocity = 256'b0;
    reg [7:0] bend = 8'd128;
    reg timbre = 1'b1;
    wire signed [15:0] sample_out;
    wire sample_valid;
    wire sample_tick, bclk, lrclk, sd;
    integer i;
    integer frames = 0;
    integer rendered = 0;
    integer nonzero = 0;
    integer release_start;
    reg [31:0] neutral_step;

    playable_synth32 dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(gate), .note_index(note_index), .velocity(velocity),
        .bend(bend), .timbre(timbre),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );
    i2s_stereo_tx tx (
        .clk_audio(clk), .rst_n(rst_n), .sample_in(sample_out),
        .sample_tick(sample_tick), .i2s_bclk(bclk),
        .i2s_lrclk(lrclk), .i2s_sd(sd)
    );

    initial begin
        for (i = 0; i < 32; i = i + 1) begin
            note_index[i*6 +: 6] = i;
            velocity[i*8 +: 8] = 8'd220;
        end
        repeat (10) @(negedge clk);
        rst_n = 1'b1;
        // The current smooth attack quantizes its earliest samples to zero.
        // Check after that onset, using completed rather than started frames.
        wait (rendered == 48);
        @(negedge clk);
        for (i = 0; i < 32; i = i + 1) begin
            if (dut.steps[i*32 +: 32] == 0 ||
                dut.synth.envelope[i] == 0)
                $fatal(1, "voice %0d inactive step=%0d env=%0d frames=%0d",
                       i, dut.steps[i*32 +: 32],
                       dut.synth.envelope[i], frames);
            if (i > 0 && dut.steps[i*32 +: 32] <=
                         dut.steps[(i-1)*32 +: 32])
                $fatal(1, "notes %0d/%0d are not ordered", i-1, i);
        end
        if (rendered < 48 || nonzero < 5)
            $fatal(1, "I2S path did not render audible 32-voice frames rendered=%0d nonzero=%0d",rendered,nonzero);
        note_index[31*6 +: 6] = 6'd34;
        @(posedge sample_tick);
        @(posedge sample_valid);
        @(negedge clk);
        if (dut.steps[31*32 +: 32] !== 32'd166846509)
            $fatal(1, "top-bank Bb6 did not reach the active oscillator");
        neutral_step = dut.steps[0 +: 32];
        bend = 8'd200;
        @(posedge sample_tick);
        @(posedge sample_valid);
        @(negedge clk);
        if (dut.steps[0 +: 32] <= neutral_step)
            $fatal(1, "global pitch bend did not raise note 0");
        gate[3] = 1'b0;
        release_start = frames;
        wait (frames >= release_start + 8);
        repeat (200) @(negedge clk);
        if (dut.synth.envelope[3] >= dut.synth.envelope[4])
            $fatal(1, "released note did not fade independently");
        $display("PASS: 32 note pitches, shared mix, I2S frames and bend");
        $finish;
    end

    always @(posedge clk) begin
        if (rst_n && sample_tick)
            frames = frames + 1;
        if (rst_n && sample_valid) begin
            rendered = rendered + 1;
            if (sample_out != 0)
                nonzero = nonzero + 1;
        end
    end

    initial begin
        #15000000;
        $fatal(1, "32-voice I2S test timed out");
    end
endmodule
