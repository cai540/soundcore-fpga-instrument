`timescale 1ns/1ps
module tb_seven_pad_repair_core;
    reg clk=0,rst_n=0;always #5 clk=~clk;
    wire cs,sclk,mosi,miso,bck,ws,din;wire [55:0] meter;
    reg [11:0] pressure[0:6];wire [2:0] channel=dut.scanner.scan_channel;
    wire [11:0] sample_code=channel<7 ? pressure[channel] : 12'd2048;
    integer i,j,owner,cycles,events=0;reg [6:0] observed;
    pressure_i2s_additive32_core #(.BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),.HEADPHONE_OUTPUT(0),
        .EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1),.CAL_SAMPLES(2),.REARM_SAMPLES(3),
        .SCAN_HALF_CYCLES(3),.SCAN_GAP_CYCLES(4)) dut(
        .clk_audio(clk),.rst_n(rst_n),.adc_cs_n(cs),.adc_sclk(sclk),.adc_mosi(mosi),.adc_miso(miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),.key_up_n(1'b1),.key_down_n(1'b1),
        .panel_bank(3'd0),.panel_timbre(1'b1),.panel_volume_level(5'd6),.panel_effect_mask(3'd0),
        .panel_vibrato_enabled(1'b0),.panel_vibrato_depth(4'd4),.dac_bclk(bck),.dac_lrclk(ws),.dac_din(din),.force_visual_o(meter));
    assign miso=dut.scanner.bit_index<=11 ? sample_code[dut.scanner.bit_index] : 1'b0;
    always @(posedge clk)if(rst_n && dut.strike_valid)events=events+1;
    task frames;input integer n;begin repeat(n)begin @(posedge dut.sample_tick);@(negedge clk);end end endtask
    task full_scale;
        begin observed=0;
            for(j=0;j<32;j=j+1)if(dut.gate[j])begin
                owner=dut.voice_zone[j*3+:3];if(owner>6)$fatal(1,"unexpected owner");observed[owner]=1;
                if(dut.performance_velocity[j*8+:8]!==255 || dut.synth_velocity[j*8+:8]!==255)$fatal(1,"audio path not full");
            end
            if(observed!==7'h7f || events!=7)$fatal(1,"missing pad or duplicate onset");
            for(j=0;j<7;j=j+1)if(meter[j*8+:8]!==255)$fatal(1,"visual path not full");
        end
    endtask
    initial begin
        for(i=0;i<7;i=i+1)pressure[i]=1000;
        repeat(3)@(negedge clk);rst_n=1;cycles=0;
        while(dut.detector.cal_count[6]!=2 && cycles<30000)begin @(negedge clk);cycles=cycles+1;end
        if(cycles==30000)$fatal(1,"zero acquisition timed out");
        for(i=0;i<7;i=i+1)pressure[i]=1600;
        frames(500);
        for(j=0;j<32;j=j+1)if(dut.gate[j])begin
            owner=dut.voice_zone[j*3+:3];
            if(dut.synth_velocity[j*8+:8]!==dut.detector.pad_velocity(owner,12'd600))$fatal(1,"soft onset wrong");
        end
        for(i=0;i<6;i=i+1)pressure[i]=2300;pressure[6]=2015;
        frames(4200);full_scale();
        pressure[6]=1750;frames(4000);
        if(meter[6*8+:8]!==dut.detector.pad_velocity(6,12'd750) || meter[6*8+:8]>=190)$fatal(1,"AI6 decrease not visible");
        for(j=0;j<32;j=j+1)if(dut.gate[j] && dut.voice_zone[j*3+:3]==6 && dut.synth_velocity[j*8+:8]>=190)$fatal(1,"AI6 sound remained maximum");
        pressure[6]=2015;frames(4200);full_scale();
        for(i=0;i<7;i=i+1)pressure[i]=1000;
        frames(1000);if(meter!==0 || events!=7)$fatal(1,"release meter or re-trigger failure");
        $display("PASS:real SPI scanner to7 owners; AI6 synthetic1015 span reaches255 in source/continuous/display; decrease/recovery/release; no re-trigger");$finish;
    end
endmodule
