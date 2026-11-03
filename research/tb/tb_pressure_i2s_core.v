`timescale 1ns/1ps
module tb_pressure_i2s_core;
    reg clk_audio = 0;
    reg rst_n = 0;
    reg hit = 0;
    reg [11:0] channel0_pressure = 12'd1600;
    reg [11:0] slider_value = 12'd2048;
    reg enc_s1_n = 1, enc_s2_n = 1, enc_key_n = 1;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire dac_bclk, dac_lrclk, dac_din;
    integer strikes = 0;
    integer nonzero = 0;
    integer clipped_at_default_gain = 0;
    integer loops;
    reg [7:0] initial_velocity;
    reg [7:0] previous_ramp;
    wire [11:0] mock_sample = dut.scanner.scan_channel == 3'd7 ? slider_value :
        !hit ? 12'd1000 :
        dut.scanner.scan_channel == 0 ? channel0_pressure :
        dut.scanner.scan_channel == 1 ? 12'd1900 :
        dut.scanner.scan_channel == 2 ? 12'd1700 :
        dut.scanner.scan_channel == 3 ? 12'd1800 : 12'd1000;

    always #41 clk_audio = ~clk_audio;
    pressure_i2s_core #(
        .SCAN_HALF_CYCLES(3), .SCAN_GAP_CYCLES(4),
        .CAL_SAMPLES(2), .PEAK_SAMPLES(2), .REARM_SAMPLES(3),
        .HOLD_SAMPLES(240), .SLIDER_ENABLE(1),
        .ENC_DEBOUNCE_CYCLES(3), .ENC_LONG_PRESS_CYCLES(80),
        .VIBRATO_ENABLE(1),
        .ON_THRESHOLD(12'd200),
        .OFF_THRESHOLD(12'd50)
    ) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .enc_s1_n(enc_s1_n), .enc_s2_n(enc_s2_n), .enc_key_n(enc_key_n),
        .key_up_n(1'b1), .key_down_n(1'b1),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk),
        .dac_din(dac_din)
    );
    assign adc_miso = dut.scanner.bit_index <= 11
        ? mock_sample[dut.scanner.bit_index] : 1'b0;
    always @(posedge clk_audio) if (rst_n) begin
        if (dut.strike_valid) strikes = strikes + 1;
        if (dut.unused_sample_valid) begin
            if (dut.audio_sample != 0)
                nonzero = nonzero + 1;
            if (dut.gain_level == 3'd2 &&
                (dut.boosted_wide > 20'sd32767 ||
                 dut.boosted_wide < -20'sd32768))
                clipped_at_default_gain = clipped_at_default_gain + 1;
        end
    end
    initial begin
        repeat (3) @(negedge clk_audio);
        rst_n = 1;
        loops = 0;
        while ((dut.detector.cal_count[0] < 2 ||
                dut.detector.cal_count[1] < 2 ||
                dut.detector.cal_count[2] < 2 ||
                dut.detector.cal_count[3] < 2) && loops < 10000) begin
            @(negedge clk_audio); loops = loops + 1;
        end
        if (loops == 10000 || strikes != 0)
            $fatal(1, "ADC baseline calibration failed");
        hit = 1;
        loops = 0;
        while ((strikes < 4 || nonzero < 2 || dut.gate != 4'b1111) && loops < 160000) begin
            @(negedge clk_audio); loops = loops + 1;
        end
        if (strikes != 4 || nonzero < 2 || dut.gate != 4'b1111 ||
            dut.allocator.active_note[0] != 5'd0 ||
            dut.allocator.active_note[1] != 5'd2 ||
            dut.allocator.active_note[2] != 5'd4 ||
            dut.allocator.active_note[3] != 5'd7)
            $fatal(1, "ADC-to-I2S path failed: strikes=%0d samples=%0d",
                   strikes, nonzero);
        initial_velocity = dut.allocator.active_velocity[0];
        channel0_pressure = 12'd4095;
        loops = 0;
        while (dut.allocator.active_velocity[0] <= initial_velocity && loops < 10000) begin
            @(negedge clk_audio); loops = loops + 1;
        end
        if (loops == 10000 || dut.allocator.active_velocity[0] <= initial_velocity)
            $fatal(1, "held-pressure update failed: before=%0d after=%0d",
                   initial_velocity, dut.allocator.active_velocity[0]);
        $display("held-pressure velocity: %0d -> %0d",
                 initial_velocity, dut.allocator.active_velocity[0]);
        previous_ramp = dut.velocity_ramp[0];
        loops = 0;
        while (dut.velocity_ramp[0] != dut.allocator.active_velocity[0] &&
               loops < 100000) begin
            @(negedge clk_audio);
            if (dut.velocity_ramp[0] > previous_ramp + 4)
                $fatal(1, "velocity changed too abruptly: %0d -> %0d",
                       previous_ramp, dut.velocity_ramp[0]);
            previous_ramp = dut.velocity_ramp[0];
            loops = loops + 1;
        end
        if (loops == 100000)
            $fatal(1, "velocity slew did not reach held-pressure target");
        if (dut.voice_zone !== {3'd3, 3'd2, 3'd1, 3'd0} ||
            dut.compensated_velocity[7:0] !== (dut.smoothed_velocity[7:0] >> 1) ||
            dut.compensated_velocity[31:8] !== dut.smoothed_velocity[31:8])
            $fatal(1, "AI0-only loudness compensation failed");
        slider_value = 12'd3072;
        loops = 0;
        while (dut.slider_bend != 8'd192 && loops < 5000) begin
            @(negedge clk_audio); loops = loops + 1;
        end
        repeat (2) @(negedge clk_audio);
        if (dut.slider_bend != 8'd192 || dut.effective_bend_q != 8'd192 || strikes != 4)
            $fatal(1, "CH7 slider bend failed or falsely triggered a strike");
        enc_key_n = 0;
        repeat (12) @(negedge clk_audio);
        if (dut.vibrato_enabled)
            $fatal(1, "short press toggled vibrato before release");
        enc_key_n = 1;
        repeat (12) @(negedge clk_audio);
        if (!dut.vibrato_enabled)
            $fatal(1, "EC11 short release did not enable I2S vibrato");
        enc_s1_n = 0;
        repeat (12) @(negedge clk_audio);
        if (dut.vibrato_depth != 4'd5)
            $fatal(1, "EC11 turn did not change I2S vibrato depth");
        loops = 0;
        while (dut.effective_bend_q == 8'd192 && loops < 200000) begin
            @(negedge clk_audio); loops = loops + 1;
        end
        if (loops == 200000)
            $fatal(1, "enabled vibrato did not modulate live I2S pitch");
        enc_key_n = 0;
        repeat (110) @(negedge clk_audio);
        if (dut.timbre_select !== 1'b0 || dut.vibrato_enabled !== 1'b1)
            $fatal(1, "long press did not select bright preset cleanly");
        repeat (100) @(negedge clk_audio);
        if (dut.timbre_select !== 1'b0 ||
            dut.synth.synth.v0.timbre_latched !== 1'b1)
            $fatal(1, "long hold changed preset repeatedly");
        enc_key_n = 1;
        repeat (12) @(negedge clk_audio);
        if (dut.vibrato_enabled !== 1'b1)
            $fatal(1, "long release accidentally toggled vibrato");
        force dut.volume_control.gain_level = 3'd3;
        force dut.audio_sample = 16'sd1000;
        #1;
        if (dut.boosted_wide !== 20'sd6000)
            $fatal(1, "intermediate 6x speaker gain failed");
        force dut.audio_sample = 16'sd10000;
        #1;
        if (dut.boosted_sample !== 16'sh7fff)
            $fatal(1, "positive speaker limiter failed");
        force dut.audio_sample = -16'sd10000;
        #1;
        if (dut.boosted_sample !== 16'sh8000)
            $fatal(1, "negative speaker limiter failed");
        release dut.audio_sample;
        release dut.volume_control.gain_level;
        if (clipped_at_default_gain != 0)
            $fatal(1, "new instrument clipped %0d frames at default 4x",
                   clipped_at_default_gain);
        $display("PASS: four pressure voices, CH7 slider, vibrato and EC11 long-press preset");
        $finish;
    end
endmodule
