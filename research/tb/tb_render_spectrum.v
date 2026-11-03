`timescale 1ns/1ps

// Produces only synthesized HDL samples, never a prerecorded PCM source.
// Frequencies C4/E4/G4/B4 are separated so each fundamental can be checked.
module tb_render_spectrum;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg sample_tick = 1'b0;
    reg [3:0] gate = 4'b1111;
    reg [127:0] phase_step = {32'd44191930, 32'd35075158,
                              32'd29494575, 32'd23409859};
    reg [31:0] velocity = 32'h40_40_40_40;
    reg timbre = 1'b1; // triangle: fundamentals are easy to identify
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer clock_count = 0;
    integer sample_count = 0;
    integer written = 0;
    integer out_file;

    poly_synth4 dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(gate), .phase_step(phase_step),
        .velocity(velocity), .timbre(timbre),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );

    initial begin
        out_file = $fopen("build/spectrum_samples.txt", "w");
        if (out_file == 0)
            $fatal(1, "Cannot create spectrum output");
        #20 rst_n = 1'b1;
    end

    // Four fast simulation clocks represent one 48 kHz audio sample.
    always @(negedge clk) begin
        if (rst_n) begin
            sample_tick <= (clock_count % 4 == 0);
            clock_count = clock_count + 1;
        end
    end

    always @(negedge clk) begin
        if (rst_n && sample_valid) begin
            sample_count = sample_count + 1;
            // Let the attack/decay settle before measuring steady-state audio.
            if (sample_count > 3000) begin
                $fwrite(out_file, "%0d\n", sample_out);
                written = written + 1;
            end
            if (written == 8192) begin
                $fclose(out_file);
                $display("PASS: rendered %0d four-voice samples", written);
                $finish;
            end
        end
    end
endmodule
