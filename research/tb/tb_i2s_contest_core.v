`timescale 1ns/1ps

module tb_i2s_contest_core;
    reg clk_audio = 1'b0;
    always #40.690 clk_audio = ~clk_audio;

    reg rst_n = 1'b0;
    reg test_enable = 1'b0;
    reg [3:0] test_voice_mask = 4'b1111;
    reg [3:0] live_gate = 4'b0001;
    reg [19:0] live_note_index = {4{5'd31}};
    reg [31:0] live_velocity = 32'h40_40_40_60;
    reg [7:0] live_bend = 8'd128;
    reg live_timbre = 1'b0;
    reg echo_enable = 1'b0;
    wire i2s_bclk, i2s_lrclk, i2s_sd;
    wire sample_tick;
    wire signed [15:0] sample_out;

    integer slot = 0;
    integer frames = 0;
    integer live_nonzero = 0;
    integer test_nonzero = 0;
    integer live_return_nonzero = 0;
    integer echo_changed = 0;
    reg started = 1'b0;
    reg [15:0] left_word = 16'd0;
    reg [15:0] right_word = 16'd0;

    i2s_contest_core #(.ECHO_DEPTH(8)) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .test_enable(test_enable), .test_voice_mask(test_voice_mask),
        .live_gate(live_gate), .live_note_index(live_note_index),
        .live_velocity(live_velocity), .live_bend(live_bend),
        .live_timbre(live_timbre), .echo_enable(echo_enable),
        .sample_tick(sample_tick), .sample_out(sample_out),
        .i2s_bclk(i2s_bclk), .i2s_lrclk(i2s_lrclk), .i2s_sd(i2s_sd)
    );

    initial begin
        repeat (4) @(negedge clk_audio);
        rst_n = 1'b1;
        #1 live_note_index = {5'd11, 5'd7, 5'd4, 5'd0};
        #30000000;
        $fatal(1, "Integrated I2S core timed out");
    end

    always @(posedge clk_audio) begin
        if (rst_n && sample_tick)
            started = 1'b1;
    end

    // Observe the control bus that actually feeds the synthesizer, as well
    // as the final serial audio. This catches a disconnected test-mode mux.
    always @(negedge clk_audio) begin
        if (rst_n && frames > 2) begin
            if (!test_enable) begin
                if (dut.selected_gate !== live_gate ||
                    dut.selected_note_index !== live_note_index ||
                    dut.selected_velocity !== live_velocity ||
                    dut.selected_bend !== live_bend ||
                    dut.selected_timbre !== live_timbre)
                    $fatal(1, "Live controls not passed to audio engine");
            end else begin
                if (dut.selected_gate !== test_voice_mask ||
                    dut.selected_note_index !== {5'd11, 5'd7, 5'd4, 5'd0} ||
                    dut.selected_velocity !== 32'h40_40_40_40 ||
                    dut.selected_bend !== 8'd128 ||
                    dut.selected_timbre !== 1'b1)
                    $fatal(1, "Four-frequency test controls not selected");
            end
        end
    end

    always @(posedge i2s_bclk) begin
        if (rst_n && started) begin
            if (i2s_lrclk !== (slot >= 32))
                $fatal(1, "LRCLK framing failed at slot %0d", slot);
            if (slot >= 1 && slot <= 16)
                left_word[16-slot] = i2s_sd;
            if (slot == 1 && frames > 112 && frames < 200 &&
                sample_out !== dut.dry_sample)
                echo_changed = echo_changed + 1;
            if (slot == 1 && frames > 225 &&
                sample_out !== dut.dry_sample)
                $fatal(1, "Echo bypass altered the dry output");
            if (slot >= 33 && slot <= 48)
                right_word[48-slot] = i2s_sd;
            if (slot == 63) begin
                if (left_word !== right_word)
                    $fatal(1, "I2S left/right samples differ");
                if (frames < 100 && left_word != 0)
                    live_nonzero = live_nonzero + 1;
                if (frames >= 100 && frames < 220 && left_word != 0)
                    test_nonzero = test_nonzero + 1;
                if (frames >= 220 && left_word != 0)
                    live_return_nonzero = live_return_nonzero + 1;
                frames = frames + 1;
                slot = 0;
                left_word = 0;
                right_word = 0;

                if (frames == 100) begin
                    test_enable = 1'b1;
                    echo_enable = 1'b1;
                end
                if (frames == 160)
                    test_voice_mask = 4'b0101;
                if (frames == 220) begin
                    test_enable = 1'b0;
                    echo_enable = 1'b0;
                    live_bend = 8'd180;
                end
                if (frames == 300) begin
                    if (live_nonzero < 60 || test_nonzero < 80 ||
                        live_return_nonzero < 60 || echo_changed < 20)
                        $fatal(1, "An audio mode went silent: %0d/%0d/%0d",
                               live_nonzero, test_nonzero,
                               live_return_nonzero);
                    $display("PASS: integrated live and four-frequency I2S modes");
                    $finish;
                end
            end else
                slot = slot + 1;
        end
    end
endmodule
