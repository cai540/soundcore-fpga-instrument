`timescale 1ns/1ps

module tb_playable_demo_top;
    reg sys_clk = 1'b0;
    always #10 sys_clk = ~sys_clk;
    reg rst_n = 1'b0;
    reg key0 = 1'b1;
    reg key1 = 1'b1;
    wire [7:0] led_o;
    wire HP_BCK, HP_WS, HP_DIN, PA_EN;
    integer nonzero = 0;
    integer ticks = 0;

    playable_demo_top #(.BEAT_SAMPLES(512)) dut (
        .sys_clk(sys_clk), .rst_n(rst_n),
        .key0(key0), .key1(key1), .led_o(led_o),
        .HP_BCK(HP_BCK), .HP_WS(HP_WS),
        .HP_DIN(HP_DIN), .PA_EN(PA_EN)
    );

    initial begin
        #40 rst_n = 1'b1;
        #12000000;
        $fatal(1, "Playable board demo timed out");
    end

    always @(posedge sys_clk) begin
        if (rst_n && dut.sample_tick) begin
            ticks = ticks + 1;
            if (dut.audio_sample != 0)
                nonzero = nonzero + 1;
            if (ticks == 20) begin
                if (dut.demo_gate !== 4'b0001)
                    $fatal(1, "Default should be a single solo voice");
                key0 = 1'b0;
            end
            if (ticks == 22 && dut.demo_gate !== 4'b1111)
                $fatal(1, "KEY0 did not enable four voices");
            if (ticks == 24)
                key1 = 1'b0;
            if (ticks == 26 && dut.synth.timbre !== 1'b1)
                $fatal(1, "KEY1 did not change timbre");
            if (ticks == 400) begin
                if (dut.demo_gate !== 4'b0000)
                    $fatal(1, "Rest window was not silent");
                key0 = 1'b1;
                key1 = 1'b1;
            end
            if (ticks == 515) begin
                if (dut.root_semitone !== 4'd1 || nonzero < 100)
                    $fatal(1, "New note did not start after one cycle");
                $display("PASS: board demo changes note, gate and timbre");
                $finish;
            end
        end
    end
endmodule
