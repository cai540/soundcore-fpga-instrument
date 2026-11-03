`timescale 1ns/1ps
module tb_audio_effects_capture;
    reg clk=0,rst_n=0;
    reg signed [15:0] dry=0;
    reg [2:0] mask=0;
    wire signed [15:0] sound;
    reg [15:0] input_samples[0:239999];
    integer n,mode,fd,unused;
    reg [2047:0] output_path;
    always #5 clk=~clk;
`ifdef PRODUCT_EFFECTS
    audio_effects_product dut(.clk(clk),.rst_n(rst_n),.sample_tick(1'b1),
`else
    audio_effects dut(.clk(clk),.rst_n(rst_n),.sample_tick(1'b1),
`endif
        .dry_in(dry),.enable(mask),.sample_out(sound));
    initial begin
        mode=0;output_path="build/fx_review/capture.hex";
        unused=$value$plusargs("MASK=%d",mode);
        unused=$value$plusargs("OUT=%s",output_path);
        $readmemh("build/fx_review/input.hex",input_samples);
        fd=$fopen(output_path,"w");
        if(fd==0)$fatal(1,"cannot open capture output");
        repeat(2)@(negedge clk);rst_n=1;mask=mode[2:0];
        for(n=0;n<240000;n=n+1)begin
            dry=input_samples[n];
            @(negedge clk);
            if((^sound)===1'bx)$fatal(1,"unknown effect sample at %0d",n);
            $fdisplay(fd,"%04x",sound);
        end
        $fclose(fd);$display("Captured effect mask %0d",mode);$finish;
    end
endmodule
