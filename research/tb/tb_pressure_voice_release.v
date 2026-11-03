`timescale 1ns/1ps
module tb_pressure_voice_release;
    reg clk = 0;
    reg rst_n = 0;
    reg gate = 0;
    wire signed [15:0] sample_out;
    integer held_nonzero = 0;
    integer i;

    always #5 clk = ~clk;
    synth_voice #(.RELEASE_SHIFT(12)) dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(1'b1),
        .gate(gate), .phase_step(32'd23409898),
        .velocity(8'd100), .timbre(1'b1), .sample_out(sample_out)
    );

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        gate = 1;
        repeat (2500) begin
            @(negedge clk);
            if (sample_out != 0) held_nonzero = held_nonzero + 1;
        end
        if (held_nonzero < 1000 || dut.envelope != 16'd20000)
            $fatal(1, "held pressure must sustain audible output");

        gate = 0;
        repeat (1000) @(negedge clk);
        if (dut.envelope == 0 || dut.envelope >= 16'd20000)
            $fatal(1, "release must fade gradually, not cut immediately");
        // The shorter release should finish by 15k audio samples; the old
        // setting lasted more than 18k samples from this sustain level.
        for (i = 0; i < 14000; i = i + 1) @(negedge clk);
        if (dut.envelope != 0 || dut.state != 2'd0 || sample_out != 0)
            $fatal(1, "release tail must eventually reach silence");
        $display("PASS: held sustain and gradual release to silence");
        $finish;
    end
endmodule
