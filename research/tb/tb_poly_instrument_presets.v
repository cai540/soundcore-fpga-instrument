`timescale 1ns/1ps
module tb_poly_instrument_presets;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, sample_tick=0, gate=0;
    reg timbre_h=1, timbre_e=0;
    wire signed [15:0] harmonica, erhu;
    wire valid_h, valid_e;
    integer cycle=0, frames=0, differences=0;
    reg [15:0] h_early, e_early;
    poly_synth32_tm h (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate({31'd0,gate}), .phase_step({992'd0,32'd46819719}),
        .velocity({248'd0,8'd180}), .timbre(timbre_h),
        .sample_out(harmonica), .sample_valid(valid_h)
    );
    poly_synth32_tm e (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate({31'd0,gate}), .phase_step({992'd0,32'd46819719}),
        .velocity({248'd0,8'd180}), .timbre(timbre_e),
        .sample_out(erhu), .sample_valid(valid_e)
    );
    always @(negedge clk) if (rst_n) begin
        sample_tick=(cycle==0);
        cycle=(cycle+1)%256;
        if(sample_tick) frames=frames+1;
    end
    always @(posedge clk) if (rst_n && valid_h && valid_e &&
                             harmonica != erhu) differences=differences+1;
    initial begin
        repeat(3) @(negedge clk); rst_n=1; gate=1;
        wait(frames==150); repeat(200) @(negedge clk);
        h_early=h.envelope[0]; e_early=e.envelope[0];
        if(h_early<=e_early) $fatal(1,"harmonica attack not faster");
        timbre_h=0; timbre_e=1;
        wait(frames==700); repeat(200) @(negedge clk);
        if(h.timbre_latched[0]!==1 || e.timbre_latched[0]!==0)
            $fatal(1,"preset changed during a held note");
        if(h.envelope[0]!==16'd30000 || e.envelope[0]!==16'd28000)
            $fatal(1,"instrument sustain levels missing");
        if(differences<200) $fatal(1,"preset waveforms indistinguishable");
        gate=0;
        wait(frames==900); repeat(200) @(negedge clk);
        if(h.envelope[0]>=16'd30000 || e.envelope[0]>=16'd28000)
            $fatal(1,"instrument release missing");
        $display("PASS: 32-slot harmonica/erhu attack, spectra, timbre latch, sustain and release");
        $finish;
    end
endmodule
