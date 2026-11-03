`timescale 1ns/1ps
module tb_pressure_i2s_additive32_core;
    reg clk_audio=0;
    always #41 clk_audio=~clk_audio;
    reg rst_n=0, hit=0;
    reg [11:0] ch0_pressure=12'd1600;
    reg key_up_n=1, key_down_n=1;
    wire adc_cs_n,adc_sclk,adc_mosi,adc_miso;
    wire dac_bclk,dac_lrclk,dac_din;
    integer strikes=0, cycles=0, additive_nonzero=0;
    integer zone, slot, found;
    wire [11:0] mock_sample =
        dut.scanner.scan_channel==3'd7 ? 12'd2048 :
        !hit ? 12'd1000 :
        dut.scanner.scan_channel==3'd0 ? ch0_pressure :
        dut.scanner.scan_channel==3'd1 ? 12'd1900 :
        dut.scanner.scan_channel==3'd2 ? 12'd1700 :
        dut.scanner.scan_channel==3'd3 ? 12'd1800 : 12'd1000;
    pressure_i2s_additive32_core #(
        .SCAN_HALF_CYCLES(3),.SCAN_GAP_CYCLES(4),
        .CAL_SAMPLES(2),.PEAK_SAMPLES(2),.REARM_SAMPLES(3),
        .HOLD_SAMPLES(30),.ENC_DEBOUNCE_CYCLES(3),
        .ENC_LONG_PRESS_CYCLES(80),.VOLUME_DEBOUNCE_CYCLES(3),
        .DEMO_HOLD_CYCLES(12),.ON_THRESHOLD(12'd200),
        .OFF_THRESHOLD(12'd50)
    ) dut(
        .clk_audio(clk_audio),.rst_n(rst_n),
        .adc_cs_n(adc_cs_n),.adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi),.adc_miso(adc_miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .key_up_n(key_up_n),.key_down_n(key_down_n),
        .dac_bclk(dac_bclk),.dac_lrclk(dac_lrclk),
        .dac_din(dac_din));
    assign adc_miso = dut.scanner.bit_index<=11 ?
        mock_sample[dut.scanner.bit_index] : 1'b0;
    always @(posedge clk_audio) begin
        if(rst_n && dut.strike_valid) strikes=strikes+1;
        if(rst_n && dut.additive_mode && dut.additive_sample_valid &&
           dut.additive_sample!=0) additive_nonzero=additive_nonzero+1;
    end
    initial begin
        repeat(4) @(negedge clk_audio); rst_n=1;
        cycles=0;
        while((dut.detector.cal_count[0]<2 ||
               dut.detector.cal_count[1]<2 ||
               dut.detector.cal_count[2]<2 ||
               dut.detector.cal_count[3]<2 ||
               dut.detector.cal_count[4]<2 ||
               dut.detector.cal_count[5]<2 ||
               dut.detector.cal_count[6]<2) && cycles<20000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(cycles>=20000) $fatal(1,"baseline calibration failed");
        hit=1;
        cycles=0;
        while((strikes<4 || dut.gate[3:0]!=4'b1111) &&
              cycles<180000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(strikes<4 || dut.base_gate[3:0]!=4'b1111)
            $fatal(1,"normal seven-pad route changed strikes=%0d gate=%b base=%b pressed=%b led=%b",
                strikes, dut.gate[3:0], dut.base_gate[3:0], dut.pressed,
                dut.pad_led_on);
        hit=0;
        cycles=0;
        while((dut.pressed[0] || dut.feature_gate) &&
              cycles<100000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(cycles>=100000) $fatal(1,"AI0 did not release");
        key_up_n=0; key_down_n=0;
        repeat(24) @(negedge clk_audio);
        key_up_n=1; key_down_n=1;
        cycles=0;
        while(!dut.additive_mode && cycles<300) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(!dut.additive_mode)
            $fatal(1,"additive mode did not activate");
        hit=1; ch0_pressure=12'd1800;
        cycles=0;
        while((strikes<8 || !dut.feature_gate ||
               additive_nonzero<4) && cycles<180000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(strikes<8 || additive_nonzero<4 ||
           dut.additive.envelope[31]==0)
            $fatal(1,"playable additive sound missing");
        for (slot=0; slot<32; slot=slot+1)
            if (dut.base_gate[slot] && dut.voice_zone[slot*3 +: 3]==3'd0)
                $fatal(1,"AI0 doubled by ordinary synth");
        for (zone=1; zone<4; zone=zone+1) begin
            found=0;
            for (slot=0; slot<32; slot=slot+1)
                if (dut.base_gate[slot] &&
                    dut.voice_zone[slot*3 +: 3]==zone)
                    found=1;
            if (!found) $fatal(1,"held zone %0d stolen",zone);
        end
        ch0_pressure=12'd1000;
        cycles=0;
        while(dut.feature_gate && cycles<100000) begin
            @(negedge clk_audio); cycles=cycles+1;
        end
        if(cycles>=100000)
            $fatal(1,"AI0 did not finish release");
        for (zone=1; zone<4; zone=zone+1) begin
            found=0;
            for (slot=0; slot<32; slot=slot+1)
                if (dut.base_gate[slot] &&
                    dut.voice_zone[slot*3 +: 3]==zone)
                    found=1;
            if (!found) $fatal(1,"AI0 release disturbed zone %0d",zone);
        end
        $display("PASS: normal pads, playable 32-partial AI0 and chord isolation");
        $finish;
    end
endmodule
