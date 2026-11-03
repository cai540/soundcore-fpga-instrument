`timescale 1ns/1ps
module tb_banked32_integration;
    reg clk_audio=0;
    always #41 clk_audio=~clk_audio;
    reg rst_n=0, key_up_n=1, key_down_n=1, enc_key_n=1;
    reg [6:0] hit=0;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire dac_bclk, dac_lrclk, dac_din;
    wire [6:0] pad_led_on;
    wire [2:0] bank_index;
    wire sustain_on;
    wire [5:0] active_voice_count;
    wire [1:0] display_mode;
    integer cycles, found0, found7, found14, i;
    wire [11:0] mock_sample = dut.scanner.scan_channel==3'd7 ?
        12'd2048 : hit[dut.scanner.scan_channel] ? 12'd1900 : 12'd1000;

    pressure_i2s_additive32_core #(
        .BANKED32_AVAILABLE(1), .SCAN_HALF_CYCLES(3),
        .SCAN_GAP_CYCLES(4), .CAL_SAMPLES(2), .PEAK_SAMPLES(2),
        .REARM_SAMPLES(3), .HOLD_SAMPLES(4),
        .ENC_DEBOUNCE_CYCLES(3), .ENC_LONG_PRESS_CYCLES(80),
        .VOLUME_DEBOUNCE_CYCLES(3), .DEMO_HOLD_CYCLES(12),
        .ON_THRESHOLD(12'd200), .OFF_THRESHOLD(12'd50)
    ) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .enc_s1_n(1'b1), .enc_s2_n(1'b1), .enc_key_n(enc_key_n),
        .key_up_n(key_up_n), .key_down_n(key_down_n),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk),
        .dac_din(dac_din), .pad_led_on(pad_led_on),
        .bank_index(bank_index), .sustain_on(sustain_on),
        .active_voice_count(active_voice_count),
        .display_mode(display_mode)
    );
    assign adc_miso = dut.scanner.bit_index<=11 ?
        mock_sample[dut.scanner.bit_index] : 1'b0;

    task cycle_mode;
        input [1:0] target;
        begin
            @(negedge clk_audio); key_up_n=0; key_down_n=0;
            repeat(24) @(negedge clk_audio);
            key_up_n=1; key_down_n=1;
            cycles=0;
            while (display_mode != target && cycles<3000) begin
                @(negedge clk_audio); cycles=cycles+1;
            end
            if (cycles>=3000) $fatal(1,"mode did not reach %0d",target);
            repeat(8) @(negedge clk_audio);
        end
    endtask
    task bank_up;
        begin
            @(negedge clk_audio); key_up_n=0;
            repeat(9) @(negedge clk_audio);
            key_up_n=1;
            repeat(9) @(negedge clk_audio);
        end
    endtask
    task enc_short;
        begin
            @(negedge clk_audio); enc_key_n=0;
            repeat(9) @(negedge clk_audio);
            enc_key_n=1;
            repeat(9) @(negedge clk_audio);
        end
    endtask
    task hit_pad0;
        begin
            @(negedge clk_audio); hit[0]=1;
            cycles=0;
            while (!dut.pressed[0] && cycles<100000) begin
                @(negedge clk_audio); cycles=cycles+1;
            end
            if (cycles>=100000) $fatal(1,"pad0 failed to press");
            @(negedge clk_audio); hit[0]=0;
            cycles=0;
            while (dut.pressed[0] && cycles<100000) begin
                @(negedge clk_audio); cycles=cycles+1;
            end
            if (cycles>=100000) $fatal(1,"pad0 failed to release");
        end
    endtask
    initial begin
        repeat(4) @(negedge clk_audio); rst_n=1;
        cycles=0;
        while ((dut.detector.cal_count[0]<2 ||
                dut.detector.cal_count[6]<2) && cycles<30000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(cycles>=30000) $fatal(1,"calibration failed");
        cycle_mode(2'd1);
        if(display_mode!==2'd1) $fatal(1,"first chord not additive");
        cycle_mode(2'd2);
        if(display_mode!==2'd2) $fatal(1,"second chord not banked");
        enc_short();
        if(!sustain_on) $fatal(1,"sustain did not enable");
        hit_pad0();
        bank_up();
        if(bank_index!==3'd1) $fatal(1,"bank did not advance");
        hit_pad0();
        bank_up();
        hit_pad0();
        found0=0; found7=0; found14=0;
        for(i=0;i<32;i=i+1) if(dut.gate[i]) begin
            if(dut.note_index[i*6 +: 6]==6'd0) found0=1;
            if(dut.note_index[i*6 +: 6]==6'd7) found7=1;
            if(dut.note_index[i*6 +: 6]==6'd14) found14=1;
        end
        if(!found0 || !found7 || !found14 || active_voice_count<3)
            $fatal(1,"three-bank notes missing: %0d %0d %0d count=%0d",
                   found0,found7,found14,active_voice_count);
        enc_short();
        cycles=0;
        while(active_voice_count!=0 && cycles<30000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(active_voice_count!=0) $fatal(1,"sustain off did not release");
        $display("PASS: normal/additive/banked mode, three latched banks and sustain release");
        $finish;
    end
endmodule
