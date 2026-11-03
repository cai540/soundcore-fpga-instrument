`timescale 1ns/1ps
module tb_expression_isolation;
    reg clk=0,rst_n=0,tick=0;always #5 clk=~clk;
    reg [31:0] gate=32'hffffffff;reg [191:0] notes=0;
    reg [255:0] velocity=0,ea=0,eb=0;
    integer i,frame,cycle,checked=0;
    playable_synth32 #(.EXPRESSION_TEXTURE(1)) a(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(gate),.note_index(notes),.velocity(velocity),.expression(ea),.bend(8'd128),.timbre(1'b0));
    playable_synth32 #(.EXPRESSION_TEXTURE(1)) b(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(gate),.note_index(notes),.velocity(velocity),.expression(eb),.bend(8'd128),.timbre(1'b0));
    initial begin
        for(i=0;i<32;i=i+1)begin notes[i*6 +: 6]=i;velocity[i*8 +: 8]=64;ea[i*8 +: 8]=170;eb[i*8 +: 8]=170;end
        ea[7:0]=24;eb[7:0]=240;
        repeat(3)@(negedge clk);rst_n=1;
        for(frame=0;frame<180;frame=frame+1)begin
            tick=1;@(negedge clk);tick=0;
            for(cycle=1;cycle<256;cycle=cycle+1)begin
                @(negedge clk);
                if(a.synth.busy && a.synth.service_stage==4 && a.synth.slot!=0)begin
                    if(a.synth.wave_reg!==b.synth.wave_reg || a.synth.amp_reg!==b.synth.amp_reg)
                        $fatal(1,"expression crossed into another slot: %0d",a.synth.slot);
                    checked=checked+1;
                end
            end
        end
        if(checked!=180*31)$fatal(1,"not all unrelated slots compared");
        $display("PASS:5580 unrelated voice contributions unchanged while slot0 expression24vs240; per-slot spectrum/noise/envelope isolation");$finish;
    end
endmodule
