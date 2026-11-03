`timescale 1ns/1ps
module tb_synth_timbre_latch;
    reg clk = 0, rst_n = 0, gate = 0, timbre = 1;
    wire signed [15:0] soft_legacy, legacy_reference, preset_sample;
    integer i, differences = 0;
    always #5 clk = ~clk;

    synth_voice #(.RELEASE_SHIFT(12)) legacy (
        .clk(clk), .rst_n(rst_n), .sample_tick(1'b1), .gate(gate),
        .phase_step(32'h10000000), .velocity(8'd180),
        .timbre(1'b1), .sample_out(soft_legacy)
    );
    synth_voice #(.RELEASE_SHIFT(12)) legacy_copy (
        .clk(clk), .rst_n(rst_n), .sample_tick(1'b1), .gate(gate),
        .phase_step(32'h10000000), .velocity(8'd180),
        .timbre(1'b1), .sample_out(legacy_reference)
    );
    synth_voice #(.RELEASE_SHIFT(12), .INSTRUMENT_PRESETS(1)) dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(1'b1), .gate(gate),
        .phase_step(32'h10000000), .velocity(8'd180),
        .timbre(timbre), .sample_out(preset_sample)
    );

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        gate = 1;
        for (i = 0; i < 350; i = i + 1) begin
            @(negedge clk);
            if (legacy_reference !== soft_legacy)
                $fatal(1, "legacy voice changed unexpectedly");
        end
        timbre = 0;
        for (i = 0; i < 100; i = i + 1) begin
            @(negedge clk);
            if (dut.timbre_latched !== 1'b1 || legacy_reference !== soft_legacy)
                $fatal(1, "live note changed when preset switch moved");
        end
        gate = 0;
        repeat (10) @(negedge clk);
        gate = 1;
        for (i = 0; i < 100; i = i + 1) begin
            @(negedge clk);
            if (dut.timbre_latched !== 1'b0)
                $fatal(1, "new note did not latch bright preset");
            if (preset_sample !== soft_legacy)
                differences = differences + 1;
        end
        if (differences < 20)
            $fatal(1, "bright preset is not audibly distinct in samples");
        $display("PASS: legacy voice stable; live note latched; new instrument differs");
        $finish;
    end
endmodule
