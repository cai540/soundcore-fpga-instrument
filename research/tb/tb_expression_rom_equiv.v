`timescale 1ns/1ps
module tb_expression_rom_equiv;
    reg clk=0,rst_n=0,prepare=0,step=0,timbre=0;always #5 clk=~clk;
    reg [31:0] phase=0;reg [5:0] note=63;reg [7:0] expression=0;reg [4:0] slot=0;
    wire signed [15:0] rom_wave,lut_wave;wire signed [7:0] rom_drift,lut_drift;
    integer k,i,n,e,checks=0;
    expressive_texture rom(.clk(clk),.rst_n(rst_n),.prepare_en(prepare),.step_en(step),.active(1'b1),
        .slot(slot),.phase(phase),.note_index(note),.note_age(16'd12000),.expression(expression),
        .timbre(timbre),.wave_out(rom_wave),.pitch_drift(rom_drift));
    lut_expression_texture reference(.clk(clk),.rst_n(rst_n),.step_en(step),.active(1'b1),
        .slot(slot),.phase(phase),.note_index(note),.note_age(16'd12000),.expression(expression),
        .timbre(timbre),.wave_out(lut_wave),.pitch_drift(lut_drift));
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        for(k=0;k<2;k=k+1)for(n=0;n<35;n=n+1)for(e=0;e<256;e=e+1)begin
            timbre=k;note=n;expression=e;slot=checks%32;phase=32'h9e3779b9*checks;
            prepare=1;@(negedge clk);prepare=0;step=1;@(negedge clk);step=0;#1;
            for(i=0;i<6;i=i+1)if(rom.weight[i]!==reference.weight[i])$fatal(1,"ROM coefficient mismatch");
            if(rom_wave!==lut_wave || rom_drift!==lut_drift)$fatal(1,"ROM waveform/context mismatch %d",checks);
            checks=checks+1;@(negedge clk);
        end
        $display("PASS:%0d pitch/timbre/expression cases ROM vs previous LUT bit-exact, all32 contexts, spectrum and independent noise states",checks);$finish;
    end
endmodule
