`timescale 1ns/1ps

// Synthesized steady-state audio only. The output text is for offline FFT,
// never for playback by FPGA hardware.
module tb_render_spectrum32;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg sample_tick = 1'b0;
    reg [191:0] note_index = {192{1'bx}};
    reg [255:0] velocity = 256'b0;
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer i;
    integer clocks = 0;
    integer frames = 0;
    integer written = 0;
    integer out_file;

    playable_synth32 dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(32'hffffffff), .note_index(note_index),
        .velocity(velocity), .bend(8'd128), .timbre(1'b1),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );

    initial begin
        for (i = 0; i < 32; i = i + 1) begin
            note_index[i*6 +: 6] = i;
            velocity[i*8 +: 8] = 8'd120;
        end
        out_file = $fopen("build/spectrum32_samples.txt", "w");
        if (out_file == 0)
            $fatal(1, "Cannot create spectrum32 output");
        #20 rst_n = 1'b1;
    end

    always @(negedge clk) begin
        if (rst_n) begin
            sample_tick = (clocks == 0);
            clocks = (clocks + 1) % 80;
            if (sample_tick)
                frames = frames + 1;
        end
    end

    always @(posedge clk) begin
        if (rst_n && sample_valid && frames > 1000) begin
            $fwrite(out_file, "%0d\n", sample_out);
            written = written + 1;
            if (written == 8192) begin
                $fclose(out_file);
                $display("PASS: rendered %0d 32-voice samples", written);
                $finish;
            end
        end
    end
endmodule
