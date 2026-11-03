`timescale 1ns/1ps
module tb_pressure_instrument;
    reg clk = 0;
    reg rst_n = 0;
    reg adc_valid = 0;
    reg [2:0] adc_channel = 0;
    reg [11:0] adc_value = 0;
    reg enc_s1_n = 1, enc_s2_n = 1, enc_key_n = 1;
    wire strike_valid;
    wire [2:0] strike_channel;
    wire [7:0] strike_velocity;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    integer strikes = 0;
    integer nonzero = 0;
    integer i;

    always #10 clk = ~clk;
    pressure_instrument #(
        .CAL_SAMPLES(2), .PEAK_SAMPLES(2), .REARM_SAMPLES(3),
        .HOLD_SAMPLES(240), .ENC_DEBOUNCE_CYCLES(2),
        .ON_THRESHOLD(12'd200),
        .OFF_THRESHOLD(12'd50)
    ) dut (
        .clk_50m(clk), .rst_n(rst_n), .adc_valid(adc_valid),
        .adc_channel(adc_channel), .adc_value(adc_value),
        .enc_s1_n(enc_s1_n), .enc_s2_n(enc_s2_n),
        .enc_key_n(enc_key_n),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .HP_BCK(HP_BCK),
        .HP_WS(HP_WS), .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );
    always @(posedge clk) if (rst_n) begin
        if (strike_valid) strikes = strikes + 1;
        if (dut.sample_valid && dut.audio_sample != 0) nonzero = nonzero + 1;
    end
    task put;
        input [2:0] ch;
        input [11:0] val;
        begin
            @(negedge clk); adc_channel=ch; adc_value=val; adc_valid=1;
            @(negedge clk); adc_valid=0;
        end
    endtask
    initial begin
        repeat (3) @(negedge clk); rst_n=1;
        put(0, 12'd1000); put(0, 12'd1000);
        put(1, 12'd1000); put(1, 12'd1000);
        put(7, 12'd0); put(7, 12'd4095);
        repeat (3) @(negedge clk);
        if (strikes != 0 || dut.slider_bend != 8'd255 ||
            dut.allocator.pending != 0)
            $fatal(1, "CH7 must bend pitch but never strike");
        put(0, 12'd1400); put(0, 12'd1700); put(0, 12'd1500);
        put(1, 12'd1400); put(1, 12'd1900); put(1, 12'd1600);
        repeat (3) @(negedge clk);
        if (strikes != 2 || dut.allocator.pending != 4'b0011)
            $fatal(1, "two pressure taps did not enter the voice allocator");
        for (i = 0; i < 150000; i = i + 1) @(negedge clk);
        if (nonzero < 2 || dut.allocator.active_note[0] != 5'd0 ||
            dut.allocator.active_note[1] != 5'd2 ||
            dut.allocator.active_velocity[1] <= dut.allocator.active_velocity[0])
            $fatal(1, "sensor-to-audio synthesis or velocity failed");
        if (dut.synth.steps[31:0] <= 32'd23409859)
            $fatal(1, "slider did not bend active voice pitch upward");
        enc_key_n = 0;
        repeat (8) @(negedge clk);
        if (!dut.vibrato_enabled)
            $fatal(1, "EC11 push did not reach instrument vibrato control");
        enc_s1_n = 0;
        repeat (8) @(negedge clk);
        if (dut.vibrato_depth != 4'd5)
            $fatal(1, "EC11 rotation did not change instrument depth");
        // Let the short minimum tap timer expire while the FSR is held.
        // The channel must still sustain, then release when pressure falls.
        repeat (180000) @(negedge clk);
        if (dut.allocator.gate[0] !== 1'b1)
            $fatal(1, "held FSR stopped after the minimum tap timer");
        for (i = 0; i < 5; i = i + 1) put(0, 12'd1000);
        repeat (1000) @(negedge clk);
        if (dut.allocator.gate[0] !== 1'b0 ||
            dut.synth.synth.v0.envelope == 0)
            $fatal(1, "sensor release must start an audible fade");
        $display("PASS: pressure hold/release, CH7 bend, EC11 and two voices");
        $finish;
    end
endmodule
