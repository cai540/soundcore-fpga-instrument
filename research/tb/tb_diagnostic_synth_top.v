`timescale 1ns/1ps

module tb_diagnostic_synth_top;
    reg sys_clk = 1'b0;
    always #10 sys_clk = ~sys_clk;
    reg rst_n = 1'b0;
    reg key0 = 1'b1;
    reg key1 = 1'b1;
    wire [7:0] led_o;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    integer ticks = 0;
    integer active_nonzero = 0;
    integer rest_zero = 0;

    diagnostic_synth_top #(.BEAT_SAMPLES(1024)) dut (
        .sys_clk(sys_clk), .rst_n(rst_n), .key0(key0), .key1(key1),
        .led_o(led_o), .HP_BCK(HP_BCK), .HP_WS(HP_WS),
        .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );

    initial begin
        #40 rst_n = 1'b1;
        #25000000;
        $fatal(1, "Auto-synth test timed out");
    end

    always @(posedge sys_clk) begin
        if (rst_n && dut.sample_tick) begin
            ticks = ticks + 1;
            if (ticks > 8 && ticks < 768 && dut.audio_sample != 0)
                active_nonzero = active_nonzero + 1;
            if (ticks > 900 && ticks < 1024 && dut.audio_sample == 0)
                rest_zero = rest_zero + 1;
            if (ticks == 1030) begin
                if (active_nonzero < 500 || rest_zero < 50 || PA_EN !== 1'b0)
                    $fatal(1, "Synth gate or audio not behaving: %0d %0d",
                           active_nonzero, rest_zero);
                $display("PASS: auto four-voice synth, active=%0d rest=%0d",
                         active_nonzero, rest_zero);
                $finish;
            end
        end
    end
endmodule
