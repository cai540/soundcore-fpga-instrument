`timescale 1ns/1ps
module tb_key_tap_top;
    reg sys_clk = 0;
    reg rst_n = 0;
    reg key0 = 1;
    reg key1 = 1;
    wire [7:0] led_o;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    integer nonzero_samples = 0;
    integer timeout;

    always #10 sys_clk = ~sys_clk;
    key_tap_top #(.DEBOUNCE_CYCLES(4), .HOLD_SAMPLES(240)) dut (
        .sys_clk(sys_clk), .rst_n(rst_n), .key0(key0), .key1(key1),
        .led_o(led_o), .HP_BCK(HP_BCK), .HP_WS(HP_WS),
        .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );
    always @(posedge sys_clk)
        if (rst_n && dut.sample_valid && dut.audio_sample != 0)
            nonzero_samples = nonzero_samples + 1;

    initial begin
        repeat (5) @(negedge sys_clk);
        rst_n = 1;
        repeat (2000) @(negedge sys_clk);
        if (dut.strike_gate !== 2'b00 || nonzero_samples != 0)
            $fatal(1, "idle must be silent");

        key0 = 0;
        repeat (10) @(negedge sys_clk);
        key0 = 1;
        if (dut.strike_gate[0] !== 1'b1 || dut.strike_gate[1] !== 1'b0)
            $fatal(1, "KEY0 tap did not trigger its own zone");
        timeout = 0;
        while (nonzero_samples < 2 && timeout < 150000) begin
            @(negedge sys_clk);
            timeout = timeout + 1;
        end
        if (nonzero_samples < 2)
            $fatal(1, "KEY0 tap did not produce synthesized audio");

        key1 = 0;
        repeat (10) @(negedge sys_clk);
        key1 = 1;
        if (dut.strike_gate[1] !== 1'b1)
            $fatal(1, "KEY1 tap did not trigger its own zone");
        if (dut.synth.note_index[4:0] !== 5'd0 ||
            dut.synth.note_index[9:5] !== 5'd7)
            $fatal(1, "two keys did not map to C4/G4");

        timeout = 0;
        while (dut.strike_gate != 2'b00 && timeout < 350000) begin
            @(negedge sys_clk);
            timeout = timeout + 1;
        end
        if (dut.strike_gate != 2'b00)
            $fatal(1, "tap gates did not expire");
        $display("PASS: two KEY taps independently trigger finite synthesized notes");
        $finish;
    end
endmodule
