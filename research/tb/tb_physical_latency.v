`timescale 1ns/1ps
// Voltage-step ADC model -> production scanner/detector/allocator/synth/I2S.
// This is digital evidence; mechanical FSR and analog DAC still need a scope.
module tb_physical_latency;
    reg clk=0,rst_n=0,timbre=1,measuring=0,seen=0;
    always #40.690 clk=~clk;
    reg [6:0] hit=0;
    wire cs,sclk,mosi,miso,bclk,lr,sd;
    reg [11:0] conversion=1000;
    integer kind,pad,cycles,fd,slot=0;
    reg lr_last=1;
    reg [15:0] word_value=0;
    real began,latency;
    pressure_i2s_additive32_core #(.BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),
        .REMOTE_ENABLE(1),.EFFECTS_AVAILABLE(1),.OFFLINE_PLAYER(1)) dut(
        .clk_audio(clk),.rst_n(rst_n),.adc_cs_n(cs),.adc_sclk(sclk),.adc_mosi(mosi),.adc_miso(miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),.key_up_n(1'b1),.key_down_n(1'b1),
        .panel_bank(3'd0),.panel_timbre(timbre),.panel_vibrato_enabled(1'b0),.panel_vibrato_depth(4'd4),
        .panel_volume_level(5'd16),.panel_effect_mask(3'd0),.remote_command_valid(1'b0),
        .remote_command_type(8'd0),.remote_command_value(8'd0),.remote_session_active(1'b0),
        .remote_strike_valid(1'b0),.remote_strike_channel(3'd0),.remote_strike_velocity(8'd0),
        .remote_pressed(7'd0),.autoplay_note_gate(1'b0),.autoplay_note_index(6'd0),.autoplay_timbre(1'b1),
        .dac_bclk(bclk),.dac_lrclk(lr),.dac_din(sd));
    always @(negedge cs)conversion=dut.scanner.scan_channel==7 ? 2048 :
        hit[dut.scanner.scan_channel] ? 2200:1000;
    assign miso=dut.scanner.bit_index<=11 ? conversion[dut.scanner.bit_index] : 1'b0;
    always @(posedge bclk)if(rst_n)begin
        if(lr!=lr_last)begin slot=0;lr_last=lr;end
        else slot=slot+1;
        if(!lr && slot>=1 && slot<=16)word_value[16-slot]=sd;
        if(!lr && slot==16 && measuring && !seen &&
            ($signed(word_value)>=64 || $signed(word_value)<=-64))begin
            latency=$realtime-began;seen=1;
        end
    end
    initial begin
        fd=$fopen("build/physical_latency.csv","w");
        $fdisplay(fd,"timbre,pad,voltage_step_to_i2s_word_ns,threshold_abs_pcm");
        for(kind=0;kind<2;kind=kind+1)for(pad=0;pad<7;pad=pad+1)begin
            measuring=0;rst_n=0;hit=0;timbre=kind;
            repeat(5)@(negedge clk);rst_n=1;
            wait(dut.detector.cal_count[6]==16);
            // Just miss this pad's result, forcing nearly a full scan wait.
            @(negedge clk);
            while(!(dut.adc_valid && dut.adc_channel==pad))@(negedge clk);
            @(negedge clk);hit[pad]=1;seen=0;measuring=1;began=$realtime;cycles=0;
            while(!seen && cycles<62000)begin @(negedge clk);cycles=cycles+1;end
            if(!seen || latency>=5000000)$fatal(1,"digital latency >=5 ms timbre=%0d pad=%0d",kind,pad);
            $fdisplay(fd,"%0d,%0d,%0.3f,64",kind,pad,latency);
            $display("latency timbre=%0d pad=%0d: %0.3f us",kind,pad,latency/1000);
            measuring=0;
        end
        $fclose(fd);$display("PASS: all 14 worst-scan-phase digital paths <5ms to actual I2S word above 64 counts");$finish;
    end
endmodule
