`timescale 1ns/1ps

module tb_poly_synth4;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg sample_tick = 1'b0;
    reg [3:0] gate = 4'b0000;
    reg [127:0] phase_step = {32'd46819707, 32'd35075119,
                              32'd29494614, 32'd23409898};
    reg [31:0] velocity = 32'hd0_d0_d0_d0;
    reg timbre = 1'b0;
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer sample_number = 0;
    integer active_nonzero = 0;
    integer quiet_nonzero = 0;

    poly_synth4 dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(gate), .phase_step(phase_step),
        .velocity(velocity), .timbre(timbre),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );

    initial begin
        $dumpfile("build/poly_synth4.vcd");
        $dumpvars(0, tb_poly_synth4);
        #20 rst_n = 1'b1;
    end

    // Four fast simulation clocks represent one 48 kHz audio sample period.
    always @(negedge clk) begin
        if (rst_n) begin
            sample_tick <= (sample_number % 4 == 0);
            sample_number = sample_number + 1;
            if (sample_number == 12) gate <= 4'b1111;
            if (sample_number == 1600) timbre <= 1'b1;
            if (sample_number == 3200) gate <= 4'b0000;
        end
    end

    always @(negedge clk) begin
        if (rst_n && sample_valid) begin
            if (sample_number > 100 && sample_number < 3200 && sample_out != 0)
                active_nonzero = active_nonzero + 1;
            if (sample_number > 5200 && sample_out != 0)
                quiet_nonzero = quiet_nonzero + 1;
        end
        if (sample_number >= 6000) begin
            if (active_nonzero < 100)
                $fatal(1, "Four-voice engine did not generate audio");
            if (quiet_nonzero != 0)
                $fatal(1, "Release did not reach silence");
            $display("PASS: active samples=%0d, late nonzero samples=%0d",
                     active_nonzero, quiet_nonzero);
            $finish;
        end
    end
endmodule
