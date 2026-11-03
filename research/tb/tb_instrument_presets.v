`timescale 1ns/1ps
module tb_instrument_presets;
    reg clk = 0, rst_n = 0, gate = 0;
    wire signed [15:0] harmonica_soft, harmonica_hard, erhu_soft, erhu_hard;
    integer i;
    integer h_early = 0, h_late = 0, e_early = 0, e_late = 0;
    integer h_soft_late = 0, e_soft_late = 0;
    integer h_release = 0, e_release = 0;

    always #5 clk = ~clk;
    synth_voice #(.RELEASE_SHIFT(12), .INSTRUMENT_PRESETS(1)) h_soft
        (clk, rst_n, 1'b1, gate, 32'h10000000, 8'd60, 1'b1, harmonica_soft);
    synth_voice #(.RELEASE_SHIFT(12), .INSTRUMENT_PRESETS(1)) h_hard
        (clk, rst_n, 1'b1, gate, 32'h10000000, 8'd200, 1'b1, harmonica_hard);
    synth_voice #(.RELEASE_SHIFT(12), .INSTRUMENT_PRESETS(1)) e_soft
        (clk, rst_n, 1'b1, gate, 32'h10000000, 8'd60, 1'b0, erhu_soft);
    synth_voice #(.RELEASE_SHIFT(12), .INSTRUMENT_PRESETS(1)) e_hard
        (clk, rst_n, 1'b1, gate, 32'h10000000, 8'd200, 1'b0, erhu_hard);

    function integer magnitude;
        input signed [15:0] value;
        begin
            magnitude = value < 0 ? -value : value;
        end
    endfunction

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        gate = 1;
        for (i = 0; i < 2400; i = i + 1) begin
            @(negedge clk);
            if ((^harmonica_soft === 1'bx) || (^harmonica_hard === 1'bx) ||
                (^erhu_soft === 1'bx) || (^erhu_hard === 1'bx))
                $fatal(1, "unknown sample");
            if (i >= 80 && i < 160) begin
                h_early = h_early + magnitude(harmonica_hard);
                e_early = e_early + magnitude(erhu_hard);
            end
            if (i >= 2200 && i < 2360) begin
                h_late = h_late + magnitude(harmonica_hard);
                e_late = e_late + magnitude(erhu_hard);
                h_soft_late = h_soft_late + magnitude(harmonica_soft);
                e_soft_late = e_soft_late + magnitude(erhu_soft);
            end
        end
        if (h_late < 100 || e_late < 100)
            $fatal(1, "held note died in one of the presets");
        if (h_late <= h_soft_late * 2 || e_late <= e_soft_late * 2)
            $fatal(1, "both instruments must respond to strike force");
        if (h_early * 2 >= h_late || e_early * 2 >= e_late)
            $fatal(1, "harmonica/erhu should bloom, not have a hammer transient");
        gate = 0;
        for (i = 0; i < 1600; i = i + 1) begin
            @(negedge clk);
            if (i >= 1440) begin
                h_release = h_release + magnitude(harmonica_hard);
                e_release = e_release + magnitude(erhu_hard);
            end
        end
        if (h_release >= h_late || e_release >= e_late)
            $fatal(1, "release did not fade");
        $display("PASS: harmonica/erhu attacks, force, sustain and release");
        $finish;
    end
endmodule
