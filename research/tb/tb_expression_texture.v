`timescale 1ns/1ps
module tb_expression_texture;
    reg clk=0,rst_n=0,step=0,active=1,timbre=0;always #5 clk=~clk;
    reg [31:0] phase=0;reg [5:0] note=63;reg [7:0] expression=0;
    wire [31:0] pitch;wire signed [15:0] normalized,raw;
    wire signed [7:0] drift;
    integer kind,n,a,j,file,count=0,peak,rawpeak,start_case=0,case_index;real sum,rawsum,rms,rawrms;
    note_step_table35 lookup(.note_index(note),.phase_step(pitch));
    expressive_texture #(.VOICES(1)) norm(.clk(clk),.rst_n(rst_n),.step_en(step),.active(active),
        .prepare_en(1'b1),
        .slot(5'd0),.phase(phase),.note_index(note),.note_age(16'd12000),.expression(expression),
        .timbre(timbre),.wave_out(normalized),.pitch_drift(drift));
    expressive_texture #(.VOICES(1),.NORMALIZE_LEVEL(0)) uncompensated(.clk(clk),.rst_n(rst_n),.step_en(step),.active(active),
        .prepare_en(1'b1),
        .slot(5'd0),.phase(phase),.note_index(note),.note_age(16'd12000),.expression(expression),
        .timbre(timbre),.wave_out(raw));
    initial begin
        if($value$plusargs("START=%d",start_case))begin end
        count=start_case;
        file=$fopen("build/expression_20261028/texture_levels_rom.csv",start_case==0?"w":"a");
        if(start_case==0)$fwrite(file,"timbre,note,expression,rms,raw_rms,peak\n");
        repeat(3)@(negedge clk);rst_n=1;
        for(kind=0;kind<2;kind=kind+1)for(n=0;n<35;n=n+1)for(a=0;a<9;a=a+1)begin
            case_index=(kind*35+n)*9+a;
            if(case_index>=start_case)begin
            timbre=kind;note=n;expression=a==8?255:a*32;phase=0;sum=0;rawsum=0;peak=0;
            for(j=0;j<2112;j=j+1)begin
                @(negedge clk);step=1;@(negedge clk);step=0;
                if((^pitch)===1'bx || (^normalized)===1'bx || (^raw)===1'bx)$fatal(1,"unknown pitch/source sample");
                if(j>=64)begin
                    sum=sum+$signed(normalized)*1.0*$signed(normalized);
                    rawsum=rawsum+$signed(raw)*1.0*$signed(raw);
                    if($signed(normalized)>peak)peak=$signed(normalized);
                    if(-$signed(normalized)>peak)peak=-$signed(normalized);
                end
                if(normalized===16'sh7fff || normalized===16'sh8000)$fatal(1,"source clipped");
                phase=phase+pitch;
            end
            rms=$sqrt(sum/2048.0);rawrms=$sqrt(rawsum/2048.0);
            if(rms<2500 || rms>2900)$fatal(1,"level constraint failed: %d %d %d %f",kind,n,a,rms);
            $fwrite(file,"%0d,%0d,%0d,%f,%f,%0d\n",kind,n,expression,rms,rawrms,peak);count=count+1;
            end
        end
        active=0;#1;if(normalized!==0)$fatal(1,"inactive noise leakage");
        $fclose(file);$display("PASS:%0d actual-RTL tone/pressure/pitch cases bounded level and source headroom, idle silence",count);$finish;
    end
endmodule
