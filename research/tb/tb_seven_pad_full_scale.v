`timescale 1ns/1ps
// Real SPI scanning -> seven detectors -> allocator -> expression -> synth input.
// No forced internal velocities: soft onset, sustained full press, weak pad 7,
// recovery to full press and release must all keep the original seven voices.
module tb_seven_pad_full_scale #(
    parameter integer CALIBRATED_TEST=0
);
    reg clk=0,rst_n=0;
    always #41 clk=~clk;
    reg [11:0] pressure[0:6];
    wire cs,sclk,mosi,miso,bck,ws,din;
    wire [55:0] meter;
    wire [11:0] equivalent_code=dut.scanner.scan_channel<7 ?
        pressure[dut.scanner.scan_channel] : 12'd2048;
    // Independent measured analogue span ratio, not the DUT's Q12 function.
    // Baseline remains the same; pad 7 supplies 39/41 of the force excursion.
    wire [11:0] sample_code=CALIBRATED_TEST && dut.scanner.scan_channel==6 && equivalent_code>=1000 ?
        1000+((equivalent_code-1000)*39+20)/41 : equivalent_code;
    integer i,j,owner,cycles,events=0;
    reg [6:0] observed;
    pressure_i2s_additive32_core #(
        .BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),.HEADPHONE_OUTPUT(0),
        .EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1),
        .CAL_SAMPLES(2),.REARM_SAMPLES(3),
        .SCAN_HALF_CYCLES(3),.SCAN_GAP_CYCLES(4)
    ) dut(
        .clk_audio(clk),.rst_n(rst_n),
        .adc_cs_n(cs),.adc_sclk(sclk),.adc_mosi(mosi),.adc_miso(miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .key_up_n(1'b1),.key_down_n(1'b1),
        .panel_bank(3'd0),.panel_timbre(1'b1),.panel_volume_level(5'd6),
        .panel_effect_mask(3'd0),.panel_vibrato_enabled(1'b0),.panel_vibrato_depth(4'd4),
        .dac_bclk(bck),.dac_lrclk(ws),.dac_din(din),.force_visual_o(meter)
    );
    assign miso=dut.scanner.bit_index<=11 ? sample_code[dut.scanner.bit_index] : 1'b0;
    always @(posedge clk)if(rst_n && dut.strike_valid)events=events+1;
    task frames;
        input integer n;
        begin repeat(n)begin @(posedge dut.sample_tick);@(negedge clk);end end
    endtask
    task full_scale;
        begin
            observed=0;
            for(j=0;j<32;j=j+1)if(dut.gate[j])begin
                owner=dut.voice_zone[j*3+:3];
                if(owner>6)$fatal(1,"unexpected pad owner");
                observed[owner]=1;
                if(dut.performance_velocity[j*8+:8]!==8'd255 ||
                   dut.synth_velocity[j*8+:8]!==8'd255)
                    $fatal(1,"pad %0d did not reach full velocity: expression=%0d synth=%0d",
                        owner+1,dut.performance_velocity[j*8+:8],dut.synth_velocity[j*8+:8]);
            end
            if(observed!==7'h7f || events!=7)$fatal(1,"missing/retriggered pad: mask=%h events=%0d",observed,events);
            for(j=0;j<7;j=j+1)if(meter[j*8+:8]!==8'd255)
                $fatal(1,"pad %0d meter not full",j+1);
        end
    endtask
    initial begin
        for(i=0;i<7;i=i+1)pressure[i]=1000;
        repeat(3)@(negedge clk);rst_n=1;
        cycles=0;
        while(dut.detector.cal_count[6]!=2 && cycles<30000)begin
            @(negedge clk);cycles=cycles+1;
        end
        if(cycles==30000)$fatal(1,"automatic empty baseline timeout");
        for(i=0;i<7;i=i+1)pressure[i]=1600;
        frames(500);
        for(j=0;j<32;j=j+1)if(dut.gate[j] &&
            (dut.performance_velocity[j*8+:8]!==8'd30 || dut.synth_velocity[j*8+:8]!==8'd30))
            $fatal(1,"unequal soft onset on pad %0d",dut.voice_zone[j*3+:3]+1);
        for(i=0;i<7;i=i+1)pressure[i]=2300;
        frames(4200);full_scale();
        // A reduced physical ADC span must remain visible, not be hidden by
        // an invented pad-7 boost. Its identical response follows the curve.
        pressure[6]=2080;frames(4000);
        if(meter[6*8+:8]!==dut.detector.pressure_velocity(12'd1080))
            $fatal(1,"pad 7 excursion mapped incorrectly");
        for(j=0;j<32;j=j+1)if(dut.gate[j])begin
            owner=dut.voice_zone[j*3+:3];
            if(owner==6 && dut.synth_velocity[j*8+:8]>=190)
                $fatal(1,"weak pad 7 reading was incorrectly forced to full scale");
            if(owner!=6 && dut.synth_velocity[j*8+:8]!==255)
                $fatal(1,"pad 7 expression changed another voice");
        end
        pressure[6]=2300;frames(4000);full_scale();
        for(i=0;i<7;i=i+1)pressure[i]=1000;
        frames(200);
        if(dut.gate!==0 || events!=7)$fatal(1,"release or same-voice correction failed");
        $display("PASS: all 7 real SPI channels: equal soft onset, exact full 255 after pressure rise, pad 7 lower-span isolation/recovery, no retriggers and release; measured-span compensation=%0d",CALIBRATED_TEST);
        $finish;
    end
endmodule
