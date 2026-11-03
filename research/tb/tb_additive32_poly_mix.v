`timescale 1ns/1ps
// Exercises both real synthesizers simultaneously without the Windows Icarus
// elaboration bug in the complete ADC/board top.
module tb_additive32_poly_mix;
    reg clk=0;
    always #41 clk=~clk;
    reg rst_n=0, sample_tick=0, additive_gate=0;
    reg [31:0] ordinary_gate=32'd0;
    reg [191:0] notes=192'd0;
    reg [255:0] velocities=256'd0;
    wire signed [15:0] ordinary_sample, additive_sample;
    wire ordinary_valid, additive_valid;
    integer frame=0, simultaneous=0, ordinary_after=0;
    playable_synth32 ordinary (
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .gate(ordinary_gate),.note_index(notes),.velocity(velocities),
        .bend(8'd128),.timbre(1'b0),
        .sample_out(ordinary_sample),.sample_valid(ordinary_valid)
    );
    additive32_tm additive (
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .gate(additive_gate),.base_step(32'd23409859),
        .velocity(8'd140),.component_mask(32'hffffffff),
        .sample_out(additive_sample),.sample_valid(additive_valid)
    );
    always @(posedge clk) begin
        if (!rst_n) begin
            frame <= 0;
            sample_tick <= 0;
        end else begin
            sample_tick <= frame == 255;
            frame <= frame == 255 ? 0 : frame+1;
            if (ordinary_valid && additive_valid) begin
                if (additive_gate && ordinary_sample != 0 &&
                    additive_sample != 0) simultaneous=simultaneous+1;
                if (!additive_gate && ordinary_gate[1] &&
                    ordinary_sample != 0 && additive_sample == 0)
                    ordinary_after=ordinary_after+1;
            end
        end
    end
    initial begin
        velocities[1*8 +: 8]=8'd140;
        notes[1*6 +: 6]=6'd4;
        repeat(4) @(negedge clk); rst_n=1;
        ordinary_gate[1]=1;
        additive_gate=1;
        repeat(80*256) @(negedge clk);
        if (simultaneous<10)
            $fatal(1,"both real synthesizers did not run together");
        additive_gate=0;
        repeat(800*256) @(negedge clk);
        if (ordinary_after<10)
            $fatal(1,"releasing additive voice disturbed ordinary voice");
        $display("PASS: real 32-partial and ordinary poly engines mix independently");
        $finish;
    end
endmodule
