`timescale 1ns/1ps
module tb_poly_erhu_expression;
    reg clk=0,rst_n=0,tick=0;
    always #5 clk=~clk;
    reg [31:0] gate=3;
    wire signed [15:0] sound;
    wire valid;
    localparam [31:0] STEP=32'd23409859;
    poly_synth32_tm dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(gate),.phase_step({960'd0,32'd26276000,STEP}),
        .velocity({240'd0,8'd176,8'd176}),.timbre(1'b0),
        .sample_out(sound),.sample_valid(valid));
    integer n,delta,minimum,maximum;
    reg [31:0] previous;
    reg [15:0] other_age;
    task frame;
        begin
            @(negedge clk);tick=1;@(negedge clk);tick=0;
            repeat(200)@(negedge clk);
            if(dut.completed_voice_count!=32)$fatal(1,"shared voice scan missed deadline");
            if((^sound)===1'bx)$fatal(1,"unknown polyphonic audio");
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        minimum=STEP;maximum=STEP;
        frame();
        for(n=0;n<32000;n=n+1)begin
            previous=dut.phase[0];frame();delta=dut.phase[0]-previous;
            if(n<4400 && delta!=STEP)$fatal(1,"manual erhu vibrato starts too early");
            if(n>22000)begin
                if(delta<minimum)minimum=delta;if(delta>maximum)maximum=delta;
                if(delta<STEP*0.98 || delta>STEP*1.02)$fatal(1,"manual pitch modulation out of range");
            end
        end
        if(maximum-minimum<STEP*0.02)$fatal(1,"manual erhu has no audible long-note modulation");
        gate[0]=0;frame();other_age=dut.note_age[1];gate[0]=1;frame();
        if(dut.note_age[0]!=0 || dut.note_age[1]<=other_age)$fatal(1,"note-on expression state not isolated");
        $display("PASS: held erhu vibrato, voice deadline and isolated new-note reset %0d..%0d",minimum,maximum);
        $finish;
    end
endmodule
