`timescale 1ns/1ps
module tb_natural_expression;
    reg clk=0,rst_n=0,gate=0;
    always #5 clk=~clk;
    wire signed [15:0] h,e;
    localparam [31:0] STEP=32'd23409859; // C4 at 48 kHz
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) harmonica
        (clk,rst_n,1'b1,gate,STEP,8'd176,1'b1,h);
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) erhu
        (clk,rst_n,1'b1,gate,STEP,8'd176,1'b0,e);
    integer n,fd,min_h,max_h,min_e,max_e,dh,de;
    reg [31:0] ph,pe;
    initial begin
        fd=$fopen("build/fx_review/timbres.hex","w");
        min_h=STEP;max_h=STEP;min_e=STEP;max_e=STEP;
        repeat(3)@(negedge clk);rst_n=1;gate=1;
        for(n=0;n<120000;n=n+1)begin
            ph=harmonica.phase;pe=erhu.phase;
            @(negedge clk);
            if((^h)===1'bx || (^e)===1'bx)$fatal(1,"unknown timbre output");
            if(n>2 && n<4500 && (harmonica.phase-ph!=STEP || erhu.phase-pe!=STEP))
                $fatal(1,"vibrato must wait for note onset to settle");
            if(n>22000)begin
                dh=harmonica.phase-ph;de=erhu.phase-pe;
                if(dh<min_h)min_h=dh;if(dh>max_h)max_h=dh;
                if(de<min_e)min_e=de;if(de>max_e)max_e=de;
            end
            $fdisplay(fd,"%04x %04x",h,e);
        end
        if(min_e>STEP*0.989 || max_e<STEP*1.011)$fatal(1,"erhu long-note expression too shallow");
        if(min_e<STEP*0.98 || max_e>STEP*1.02)$fatal(1,"erhu expression changes melody pitch too far");
        if(max_h-min_h<10000 || (max_h-min_h)*3>max_e-min_e)
            $fatal(1,"harmonica vibrato should be present and milder");
        gate=0;repeat(100)@(negedge clk);gate=1;@(negedge clk);
        if(erhu.note_age!=0 || erhu.expression_strength!=0)$fatal(1,"new note inherited long-note vibrato");
        $fclose(fd);
        $display("PASS natural expression h=%0d..%0d e=%0d..%0d",min_h,max_h,min_e,max_e);
        $finish;
    end
endmodule
