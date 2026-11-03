`timescale 1ns/1ps

module tb_diagnostic_audio_top;
    reg sys_clk = 1'b0;
    always #10 sys_clk = ~sys_clk;
    reg rst_n = 1'b0;
    reg key0 = 1'b1;
    reg key1 = 1'b1;
    wire [7:0] led_o;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    integer ticks = 0;
    integer audible = 0;
    integer quiet = 0;

    diagnostic_audio_top #(.BEAT_SAMPLES(8)) dut (
        .sys_clk(sys_clk), .rst_n(rst_n), .key0(key0), .key1(key1),
        .led_o(led_o), .HP_BCK(HP_BCK), .HP_WS(HP_WS),
        .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );

    initial begin
        #40 rst_n = 1'b1;
        #300000;
        $fatal(1, "Diagnostic did not complete");
    end

    always @(posedge sys_clk) begin
        if (rst_n && dut.sample_tick) begin
            ticks = ticks + 1;
            if (!dut.tone_on && dut.test_sample !== 16'sd0)
                $fatal(1, "Rest window must be silent");
            if (dut.tone_on && dut.test_sample != 16'sd0)
                audible = audible + 1;
            if (!dut.tone_on)
                quiet = quiet + 1;
            if (ticks == 3) begin
                key0 = 1'b0;
                #1;
                if (led_o[1] !== 1'b0)
                    $fatal(1, "KEY0 LED did not light");
            end
            if (ticks == 5) begin
                key0 = 1'b1;
                key1 = 1'b0;
                #1;
                if (led_o[2] !== 1'b0)
                    $fatal(1, "KEY1 LED did not light");
            end
            if (ticks == 7) begin
                if (dut.test_sample !== 16'sd0)
                    $fatal(1, "KEY1 mute failed");
                key1 = 1'b1;
            end
            if (ticks == 12) begin
                if (audible < 3 || quiet < 1 || PA_EN !== 1'b0)
                    $fatal(1, "Unexpected diagnostic outputs");
                $display("PASS: auto tone, silence gap, KEY0/KEY1 LED, mute");
                $finish;
            end
        end
    end
endmodule
