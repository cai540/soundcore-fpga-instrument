`timescale 1ns/1ps
module tb_expression_synth;
    reg clk=0,rst_n=0,tick=0;always #5 clk=~clk;
    reg [31:0] gate=0;reg [191:0] notes=0;reg [255:0] velocity=0,expression=0;
    wire signed [15:0] sample;wire valid;
    integer i,frame,cycle,latency,nonzero=0;
    playable_synth32 #(.EXPRESSION_TEXTURE(1)) dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(gate),.note_index(notes),.velocity(velocity),.expression(expression),.bend(8'd128),
        .timbre(1'b1),.sample_out(sample),.sample_valid(valid));
    initial begin
        for(i=0;i<32;i=i+1)begin notes[i*6 +: 6]=i;velocity[i*8 +: 8]=32;expression[i*8 +: 8]=i*8;end
        repeat(3)@(negedge clk);rst_n=1;
        for(frame=0;frame<700;frame=frame+1)begin
            gate=frame<8 ? 0 : 32'hffffffff;tick=1;@(negedge clk);tick=0;latency=0;
            for(cycle=1;cycle<256;cycle=cycle+1)begin
                @(negedge clk);
                if(valid)begin
                    if(latency!=0)$fatal(1,"multiple outputs per sample");latency=cycle;
                    if(frame<8 && sample!==0)$fatal(1,"idle leak");
                    if(sample!=0)nonzero=nonzero+1;
                end
            end
            if(latency!=225 || dut.synth.completed_voice_count!=32)$fatal(1,"32voice deadline differs: %0d",latency);
        end
        if(nonzero<100)$fatal(1,"32 voices did not sound");
        if(dut.synth.note_age[31]<500)$fatal(1,"voice31 not serviced");
        $display("PASS:700 frames, all32voices serviced,225/256 clocks, idle silence and nonzero audio");$finish;
    end
endmodule
