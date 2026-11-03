`timescale 1ns/1ps
module tb_expression_core;
    reg clk=0,rst_n=0;always #41 clk=~clk;
    reg [11:0] pressure=1000;
    wire cs,sclk,mosi,miso;wire bck,ws,din;
    wire [11:0] mock=dut.scanner.scan_channel==1 ? pressure : (dut.scanner.scan_channel==7 ? 2048 : 1000);
    integer clocks,events=0,owner=-1,i,start_level,words=0,bits=0;
    reg ready=0;reg [15:0] expected=0,decoded=0;
    always @(posedge dut.sample_tick)if(rst_n)begin expected=$signed(dut.output_sample)>>>2;ready=1;bits=0;end
    always @(posedge bck)if(rst_n && ready)begin
        decoded={decoded[14:0],din};
        if(ws!==(bits>=16))$fatal(1,"new expression headphone WS mismatch");
        if(bits%16==15)begin
            if(decoded!==expected)$fatal(1,"new expression headphone sample mismatch");words=words+1;
        end
        bits=bits+1;
    end
    pressure_i2s_additive32_core #(.BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),.HEADPHONE_OUTPUT(1),
        .EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1),.CAL_SAMPLES(2),.REARM_SAMPLES(3),
        .SCAN_HALF_CYCLES(3),.SCAN_GAP_CYCLES(4)) dut(
        .clk_audio(clk),.rst_n(rst_n),.adc_cs_n(cs),.adc_sclk(sclk),.adc_mosi(mosi),.adc_miso(miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),.key_up_n(1'b1),.key_down_n(1'b1),
        .panel_bank(3'd0),.panel_timbre(1'b1),.panel_volume_level(5'd16),.panel_effect_mask(3'd0),
        .panel_vibrato_enabled(1'b0),.panel_vibrato_depth(4'd4),.dac_bclk(bck),.dac_lrclk(ws),.dac_din(din));
    assign miso=dut.scanner.bit_index<=11 ? mock[dut.scanner.bit_index] : 1'b0;
    always @(posedge clk)if(rst_n && dut.strike_valid)events=events+1;
    task frames;input integer n;begin repeat(n)begin @(posedge dut.sample_tick);@(negedge clk);end end endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        clocks=0;while(dut.detector.cal_count[6]!=2 && clocks<30000)begin @(negedge clk);clocks=clocks+1;end
        if(clocks==30000)$fatal(1,"automatic baseline timeout");
        pressure=2100;frames(80);
        for(i=0;i<32;i=i+1)if(dut.gate[i])owner=i;
        if(owner<0 || events!=1)$fatal(1,"initial note missing");
        if(dut.velocity[owner*8 +: 8]!=212)$fatal(1,"attack curve changed");
        pressure=1350;frames(1500);
        if(dut.performance_velocity[owner*8 +: 8]!=212)$fatal(1,"attack hold changed early");
        frames(2800);
        if(dut.performance_velocity[owner*8 +: 8]>30 || !dut.gate[owner] || events!=1)
            $fatal(1,"ADC falling expression did not reach original voice");
        start_level=dut.performance_velocity[owner*8 +: 8];pressure=2100;frames(2500);
        if(dut.performance_velocity[owner*8 +: 8]<200 || events!=1)$fatal(1,"rising expression retriggered or stalled");
        pressure=1000;frames(100);
        if(dut.gate[owner])$fatal(1,"release stuck");
        if(words<1000)$fatal(1,"headphone words were not decoded");
        $display("PASS:actual ADC scanner->early detector->same voice->continuous synth/headphone path, bidirectional212->%0d->212 without retrigger, release; %0d decoded headphone words",start_level,words);$finish;
    end
endmodule
