`timescale 1ns/1ps
module tb_pressure_tap_top;
    reg sys_clk = 0;
    reg rst_n = 0;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    reg hit = 0;
    reg [11:0] slider = 12'd2048;
    reg enc_s1_n = 1, enc_s2_n = 1, enc_key_n = 1;
    integer strikes = 0;
    integer nonzero = 0;
    integer loops;
    wire [11:0] mock_sample = dut.scanner.scan_channel == 7 ? slider : !hit ? 12'd1000 :
        dut.scanner.scan_channel == 0 ? 12'd1600 :
        dut.scanner.scan_channel == 1 ? 12'd1900 : 12'd1000;

    always #10 sys_clk = ~sys_clk;
    pressure_tap_top #(
        .SCAN_HALF_CYCLES(3), .SCAN_GAP_CYCLES(4),
        .CAL_SAMPLES(2), .PEAK_SAMPLES(2), .REARM_SAMPLES(3),
        .HOLD_SAMPLES(240), .ON_THRESHOLD(12'd200),
        .OFF_THRESHOLD(12'd50), .SLIDER_ENABLE(1), .VIBRATO_ENABLE(1)
    ) dut (
        .sys_clk(sys_clk), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .enc_s1_n(enc_s1_n), .enc_s2_n(enc_s2_n),
        .enc_key_n(enc_key_n),
        .HP_BCK(HP_BCK), .HP_WS(HP_WS),
        .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );
    assign adc_miso = dut.scanner.bit_index <= 11
        ? mock_sample[dut.scanner.bit_index] : 1'b0;
    always @(posedge sys_clk) if (rst_n) begin
        if (dut.strike_valid) strikes = strikes + 1;
        if (dut.instrument.sample_valid && dut.instrument.audio_sample != 0)
            nonzero = nonzero + 1;
    end
    initial begin
        repeat (3) @(negedge sys_clk);
        rst_n = 1;
        loops = 0;
        while ((dut.instrument.detector.cal_count[0] < 2 ||
                dut.instrument.detector.cal_count[1] < 2) && loops < 10000) begin
            @(negedge sys_clk); loops = loops + 1;
        end
        if (loops == 10000 || strikes != 0)
            $fatal(1, "real scanner baseline calibration failed");
        slider = 12'd4095;
        repeat (3000) @(negedge sys_clk);
        if (strikes != 0 || dut.instrument.slider_bend != 8'd255)
            $fatal(1, "scanner CH7 must update bend without a strike");
        hit = 1;
        loops = 0;
        while ((strikes < 2 || nonzero < 2) && loops < 160000) begin
            @(negedge sys_clk); loops = loops + 1;
        end
        if (strikes != 2 || nonzero < 2 ||
            dut.instrument.allocator.active_note[0] != 5'd0 ||
            dut.instrument.allocator.active_note[1] != 5'd2 ||
            dut.instrument.synth.steps[31:0] <= 32'd23409859)
            $fatal(1, "full SPI-to-strike-to-audio path failed: strikes=%0d audio=%0d",
                   strikes, nonzero);
        $display("PASS: mock MCP3208 SPI to two pressure strikes to headphone samples");
        $finish;
    end
endmodule
