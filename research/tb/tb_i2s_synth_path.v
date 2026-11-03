`timescale 1ns/1ps

module tb_i2s_synth_path;
    reg clk_audio = 1'b0;
    always #40.690 clk_audio = ~clk_audio;

    reg rst_n = 1'b0;
    reg [3:0] gate = 4'b1111;
    reg [19:0] note_index = {4{5'd31}};
    reg [31:0] velocity = 32'h40_40_40_80;
    reg [7:0] bend = 8'd128;
    reg timbre = 1'b0;
    wire signed [15:0] sample_out;
    wire sample_valid;
    wire sample_tick, i2s_bclk, i2s_lrclk, i2s_sd;

    integer slot = 0;
    integer frames = 0;
    integer nonzero_words = 0;
    integer left_right_mismatch = 0;
    reg started = 1'b0;
    reg [15:0] expected_word = 16'd0;
    reg [15:0] left_word = 16'd0;
    reg [15:0] right_word = 16'd0;

    playable_synth4 synth (
        .clk(clk_audio), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(gate), .note_index(note_index), .velocity(velocity),
        .bend(bend), .timbre(timbre),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );
    i2s_stereo_tx tx (
        .clk_audio(clk_audio), .rst_n(rst_n), .sample_in(sample_out),
        .sample_tick(sample_tick), .i2s_bclk(i2s_bclk),
        .i2s_lrclk(i2s_lrclk), .i2s_sd(i2s_sd)
    );

    initial begin
        repeat (4) @(posedge clk_audio);
        rst_n = 1'b1;
        #1 note_index = {5'd11, 5'd7, 5'd4, 5'd0};
        #20000000;
        $fatal(1, "Live I2S synthesis test timed out");
    end

    always @(posedge clk_audio) begin
        if (rst_n && sample_tick)
            started = 1'b1;
    end

    always @(posedge i2s_bclk) begin
        if (rst_n && started) begin
            if (i2s_lrclk !== (slot >= 32))
                $fatal(1, "Live-path LRCLK mismatch at slot %0d", slot);
            if (slot == 1)
                expected_word = sample_out;
            if (slot >= 1 && slot <= 16) begin
                left_word[16-slot] = i2s_sd;
                if (i2s_sd !== expected_word[16-slot])
                    $fatal(1, "Live left sample corrupted at bit %0d", slot);
            end
            if (slot >= 33 && slot <= 48) begin
                right_word[48-slot] = i2s_sd;
                if (i2s_sd !== expected_word[48-slot])
                    $fatal(1, "Live right sample corrupted at bit %0d", slot);
            end
            if (slot == 63) begin
                if (left_word !== right_word)
                    left_right_mismatch = left_right_mismatch + 1;
                if (left_word != 16'd0)
                    nonzero_words = nonzero_words + 1;
                frames = frames + 1;
                slot = 0;

                if (frames == 250) begin
                    bend = 8'd200;
                    #1;
                    if (synth.steps[31:0] <= 32'd23409859)
                        $fatal(1, "Live pitch bend did not raise phase step");
                end
                if (frames == 350)
                    gate[0] = 1'b0; // other three notes must keep sounding
                if (frames == 500) begin
                    if (nonzero_words < 400 || left_right_mismatch != 0)
                        $fatal(1, "Live I2S words failed: %0d nonzero, %0d mismatches",
                               nonzero_words, left_right_mismatch);
                    $display("PASS: live four-voice synthesis over standard I2S");
                    $finish;
                end
            end else
                slot = slot + 1;
        end
    end
endmodule
