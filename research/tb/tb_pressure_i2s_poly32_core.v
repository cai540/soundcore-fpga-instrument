`timescale 1ns/1ps

module tb_pressure_i2s_poly32_core;
    reg clk_audio = 1'b0;
    always #41 clk_audio = ~clk_audio;
    reg rst_n = 1'b0;
    reg hit = 1'b0;
    reg [11:0] ch0_pressure = 12'd1600;
    reg key_up_n = 1'b1, key_down_n = 1'b1;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire dac_bclk, dac_lrclk, dac_din;
    integer strikes = 0;
    integer nonzero = 0;
    integer demo_nonzero = 0;
    integer cycles = 0;
    wire [11:0] mock_sample = dut.scanner.scan_channel == 3'd7 ?
        12'd2048 : !hit ? 12'd1000 :
        dut.scanner.scan_channel == 3'd0 ? ch0_pressure :
        dut.scanner.scan_channel == 3'd1 ? 12'd1900 :
        dut.scanner.scan_channel == 3'd2 ? 12'd1700 :
        dut.scanner.scan_channel == 3'd3 ? 12'd1800 : 12'd1000;

    pressure_i2s_poly32_core #(
        .SCAN_HALF_CYCLES(3), .SCAN_GAP_CYCLES(4),
        .CAL_SAMPLES(2), .PEAK_SAMPLES(2), .REARM_SAMPLES(3),
        .HOLD_SAMPLES(240), .ENC_DEBOUNCE_CYCLES(3),
        .ENC_LONG_PRESS_CYCLES(80), .VOLUME_DEBOUNCE_CYCLES(3),
        .DEMO_HOLD_CYCLES(12),
        .ON_THRESHOLD(12'd200), .OFF_THRESHOLD(12'd50)
    ) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .enc_s1_n(1'b1), .enc_s2_n(1'b1), .enc_key_n(1'b1),
        .key_up_n(key_up_n), .key_down_n(key_down_n),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk),
        .dac_din(dac_din)
    );
    assign adc_miso = dut.scanner.bit_index <= 11 ?
        mock_sample[dut.scanner.bit_index] : 1'b0;

    always @(posedge clk_audio) begin
        if (rst_n && dut.strike_valid)
            strikes = strikes + 1;
        if (rst_n && dut.unused_sample_valid && dut.audio_sample != 0)
            nonzero = nonzero + 1;
        if (rst_n && dut.demo_mode && dut.unused_sample_valid &&
            dut.audio_sample != 0)
            demo_nonzero = demo_nonzero + 1;
    end

    initial begin
        repeat (4) @(negedge clk_audio);
        rst_n = 1'b1;
        while ((dut.detector.cal_count[0] < 2 ||
                dut.detector.cal_count[1] < 2 ||
                dut.detector.cal_count[2] < 2 ||
                dut.detector.cal_count[3] < 2) && cycles < 20000) begin
            @(negedge clk_audio);
            cycles = cycles + 1;
        end
        if (cycles >= 20000 || strikes != 0)
            $fatal(1, "32-voice path baseline calibration failed");
        hit = 1'b1;
        cycles = 0;
        while ((strikes < 4 || nonzero < 2 ||
                dut.gate[3:0] != 4'b1111) && cycles < 180000) begin
            @(negedge clk_audio);
            cycles = cycles + 1;
        end
        if (strikes != 4 || nonzero < 2 ||
            dut.gate[3:0] != 4'b1111 ||
            dut.allocator.active_note[0] != 5'd0 ||
            dut.allocator.active_note[1] != 5'd2 ||
            dut.allocator.active_note[2] != 5'd4 ||
            dut.allocator.active_note[3] != 5'd7)
            $fatal(1, "32-voice live ADC-to-I2S path failed: strikes=%0d samples=%0d gate=%h",
                   strikes, nonzero, dut.gate);
        key_up_n = 1'b0;
        key_down_n = 1'b0;
        repeat (18) @(negedge clk_audio);
        if (!dut.demo_mode || dut.selected_gate != 32'hffffffff ||
            dut.selected_notes[31*6 +: 6] != 6'd31)
            $fatal(1, "both-key hold did not select all 32 test notes");
        cycles = 0;
        // The current instrument envelope takes more than eight audio
        // frames to leave quantized silence; this is a sound check, not an
        // end-to-end latency test. Keep a finite 128-frame audition window.
        while ((demo_nonzero < 3 || dut.synth.synth.envelope[31] == 0) &&
               cycles < 128*256) begin
            @(negedge clk_audio);
            cycles = cycles + 1;
        end
        if (demo_nonzero < 3 ||
            dut.synth.synth.envelope[31] == 0)
            $fatal(1, "32-note proof mode did not render audio");
        key_up_n = 1'b1;
        key_down_n = 1'b1;
        repeat (4) @(negedge clk_audio);
        if (!dut.demo_mode || dut.selected_gate != 32'd0)
            $fatal(1, "32-note test mode did not release cleanly");
        key_up_n = 1'b0;
        key_down_n = 1'b0;
        repeat (18) @(negedge clk_audio);
        if (dut.demo_mode || dut.selected_gate != dut.gate)
            $fatal(1, "both-key hold did not restore seven-pad mode");
        $display("PASS: seven-pad ADC path and built-in 32-note proof mode");
        $finish;
    end
endmodule
