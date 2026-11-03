`timescale 1ns/1ps
module tb_pressure_bench_controls;
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
    integer k;

    always #10 clk = ~clk;
    pressure_instrument #(
        .CAL_SAMPLES(2), .PEAK_SAMPLES(2), .REARM_SAMPLES(3),
        .ON_THRESHOLD(12'd200), .OFF_THRESHOLD(12'd50),
        .SLIDER_ENABLE(0), .VIBRATO_ENABLE(0)
    ) dut (
        .clk_50m(clk), .rst_n(rst_n), .adc_valid(adc_valid),
        .adc_channel(adc_channel), .adc_value(adc_value),
        .enc_s1_n(enc_s1_n), .enc_s2_n(enc_s2_n), .enc_key_n(enc_key_n),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .HP_BCK(HP_BCK),
        .HP_WS(HP_WS), .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );

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
        for (k=0; k<5; k=k+1) begin
            put(7, k[0] ? 12'd4095 : 12'd0);
            if (dut.effective_bend_q !== 8'd128)
                $fatal(1, "unconnected slider changed bench pitch");
        end
        put(0, 12'd1400); put(0, 12'd1500); put(0, 12'd1600);
        repeat (5) @(negedge clk);
        if (!strike_valid && dut.allocator.pending == 0)
            $fatal(1, "bench pressure never struck");
        put(0, 12'd2800);
        repeat (5) @(negedge clk);
        if (!dut.level_valid && dut.level_velocity < 8'd150)
            $fatal(1, "high force did not yield high velocity");
        if (dut.effective_bend_q !== 8'd128)
            $fatal(1, "bench pitch moved after force change");
        $display("PASS: one-pad bench ignores floating CH7/EC11 and tracks force");
        $finish;
    end
endmodule
