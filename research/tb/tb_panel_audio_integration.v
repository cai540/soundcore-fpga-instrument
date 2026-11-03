`timescale 1ns/1ps
module tb_panel_audio_integration #(
    parameter integer HEADPHONE_TEST=0,
    parameter integer EARLY_TEST=0
);
    reg clk_audio = 0;
    always #41 clk_audio = ~clk_audio;
    reg rst_n = 0;
    reg [6:0] hit = 0;
    reg [2:0] panel_bank = 0;
    reg panel_timbre = 1;
    reg panel_vibrato_enabled = 0;
    reg [3:0] panel_vibrato_depth = 4;
    reg [4:0] panel_volume_level = 16;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire dac_bclk, dac_lrclk, dac_din;
    wire [2:0] bank_index;
    wire [55:0] force_visual;
    wire [1:0] display_mode;
    wire strike_event;
    wire [2:0] strike_channel_o;
    integer cycles, i, pad_i, found, early_strikes=0;
    always @(posedge clk_audio) if(rst_n && dut.detector.strike_early)
        early_strikes=early_strikes+1;
    wire [11:0] mock_sample = dut.scanner.scan_channel == 3'd7 ?
        12'd2048 : hit[dut.scanner.scan_channel] ? 12'd1900 : 12'd1000;
    pressure_i2s_additive32_core #(
        .BANKED32_AVAILABLE(1), .PANEL_CONTROL(1), .HEADPHONE_OUTPUT(HEADPHONE_TEST),
        .PANEL_GAIN_RAMP_FRAMES(2),
        .SCAN_HALF_CYCLES(3), .SCAN_GAP_CYCLES(4),
        .CAL_SAMPLES(2), .PEAK_SAMPLES(EARLY_TEST ? 4 : 2),
        .EARLY_FORCE_ENABLE(EARLY_TEST),
        .REARM_SAMPLES(3), .HOLD_SAMPLES(4),
        .ENC_DEBOUNCE_CYCLES(3), .ENC_LONG_PRESS_CYCLES(80),
        .VOLUME_DEBOUNCE_CYCLES(3), .DEMO_HOLD_CYCLES(12),
        .ON_THRESHOLD(12'd200), .OFF_THRESHOLD(12'd50)
    ) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .enc_s1_n(1'b1), .enc_s2_n(1'b1), .enc_key_n(1'b1),
        .key_up_n(1'b1), .key_down_n(1'b1),
        .panel_bank(panel_bank), .panel_timbre(panel_timbre),
        .panel_vibrato_enabled(panel_vibrato_enabled),
        .panel_vibrato_depth(panel_vibrato_depth),
        .panel_volume_level(panel_volume_level),
        .panel_effect_mask(3'd0),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk),
        .dac_din(dac_din), .bank_index(bank_index),
        .force_visual_o(force_visual),
        .display_mode(display_mode), .strike_event(strike_event),
        .strike_channel_o(strike_channel_o)
    );
    assign adc_miso = dut.scanner.bit_index <= 11 ?
        mock_sample[dut.scanner.bit_index] : 1'b0;
    reg headphone_ready=0;
    reg [15:0] headphone_expected=0,headphone_decoded=0;
    integer headphone_bits=0,headphone_words=0;
    always @(posedge dut.sample_tick)if(HEADPHONE_TEST && rst_n)begin
        headphone_expected=$signed(dut.output_sample)>>>2;
        headphone_ready=1;headphone_bits=0;
    end
    always @(posedge dac_bclk)if(HEADPHONE_TEST && rst_n && headphone_ready)begin
        headphone_decoded={headphone_decoded[14:0],dac_din};
        if(dac_lrclk!==(headphone_bits>=16))$fatal(1,"integrated PT8211 WS mismatch");
        if(headphone_bits%16==15)begin
            if(headphone_decoded!==headphone_expected)$fatal(1,"integrated PT8211 audio word mismatch");
            headphone_words=headphone_words+1;
        end
        headphone_bits=headphone_bits+1;
    end
    task wait_pad;
        input [2:0] pad;
        input desired;
        begin
            cycles = 0;
            while (dut.pressed[pad] !== desired && cycles < 100000) begin
                @(negedge clk_audio); cycles = cycles + 1;
            end
            if (cycles >= 100000) $fatal(1, "pad%0d timeout", pad);
        end
    endtask
    task expect_note;
        input [5:0] expected_note;
        begin
            found = 0;
            cycles = 0;
            while (!found && cycles < 10000) begin
                for (i=0; i<32; i=i+1)
                    if (dut.gate[i] &&
                        dut.note_index[i*6 +: 6] == expected_note)
                        found = 1;
                if (!found) begin
                    @(negedge clk_audio);
                    cycles = cycles + 1;
                end
            end
            if (!found)
                $fatal(1, "expected note %0d not gated", expected_note);
        end
    endtask
    initial begin
        repeat (4) @(negedge clk_audio); rst_n = 1;
        cycles = 0;
        while ((dut.detector.cal_count[0] < 2 ||
                dut.detector.cal_count[6] < 2) && cycles < 30000) begin
            @(negedge clk_audio); cycles = cycles + 1;
        end
        if (cycles >= 30000) $fatal(1, "calibration timeout");
        if (display_mode != 2 || bank_index != 0 ||
            dut.timbre_select != 1)
            $fatal(1, "panel initial state not selected");
        hit[0] = 1; wait_pad(3'd0, 1'b1); expect_note(6'd0);
        cycles = 0;
        while (force_visual[7:0] == 0 && cycles < 10000) begin
            @(negedge clk_audio); cycles = cycles + 1;
        end
        if (cycles >= 10000 || force_visual[7:0] !== dut.level_velocity)
            $fatal(1, "visual force must follow detector velocity");
        cycles = 0;
        while (dut.velocity_ramp[0] == 0 && cycles < 10000) begin
            @(negedge clk_audio); cycles = cycles + 1;
        end
        if (cycles >= 10000 || dut.voice_zone[2:0] != 0 ||
            dut.synth_velocity[7:0] !== dut.velocity_ramp[0])
            $fatal(1, "pad 1 must retain its full voice velocity");
        hit[0] = 0; wait_pad(3'd0, 1'b0);
        repeat (2) @(negedge clk_audio);
        if (force_visual[7:0] != 0)
            $fatal(1, "visual force must clear on release");
        panel_bank = 3'd1; panel_timbre = 0;
        panel_vibrato_enabled = 1; panel_vibrato_depth = 4'd9;
        repeat (2) @(negedge clk_audio);
        if (bank_index != 1 || dut.timbre_select != 0 ||
            dut.vibrato_enabled != 1 || dut.vibrato_depth != 9)
            $fatal(1, "panel sound controls not routed");
        hit[0] = 1; wait_pad(3'd0, 1'b1); expect_note(6'd7);
        hit[0] = 0; wait_pad(3'd0, 1'b0);
        panel_bank = 3'd4;
        for (pad_i = 0; pad_i < 7; pad_i = pad_i + 1) begin
            hit[pad_i] = 1;
            wait_pad(pad_i[2:0], 1'b1);
            expect_note(6'd28 + pad_i);
            hit[pad_i] = 0;
            wait_pad(pad_i[2:0], 1'b0);
        end
        panel_volume_level = 0;
        cycles = 0;
        while (dut.panel_gain_q != 0 && cycles < 100000) begin
            @(negedge clk_audio); cycles = cycles + 1;
        end
        if (cycles >= 100000 || dut.panel_gain_q != 0)
            $fatal(1, "volume ramp to mute failed");
        force dut.mixed_sample = 16'sd1000;
        #1;
        if (dut.output_sample != 0)
            $fatal(1, "volume zero not silent");
        panel_volume_level = 31;
        cycles = 0;
        while (dut.panel_gain_q != 62 && cycles < 150000) begin
            @(negedge clk_audio); cycles = cycles + 1;
        end
        #1;
        if (cycles >= 150000 || dut.output_sample != 16'sd7750)
            $fatal(1, "volume full-scale gain or ramp failed: %0d",
                   dut.output_sample);
        release dut.mixed_sample;
        if(HEADPHONE_TEST && headphone_words<20)$fatal(1,"headphone stream was not decoded");
        if(EARLY_TEST && early_strikes!=9)$fatal(1,"early path did not reach all nine expected strikes: %0d",early_strikes);
        $display("PASS: panel banks 0/1/4 incl notes 28-34, timbre/vibrato, smooth mute/full volume; headphone=%0d words=%0d early_strikes=%0d",HEADPHONE_TEST,headphone_words,early_strikes);
        $finish;
    end
endmodule
