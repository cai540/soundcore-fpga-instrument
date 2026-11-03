`timescale 1ns/1ps
module tb_expression_bitexact;
    reg clk=0,rst_n=0,tick=0;always #5 clk=~clk;
    reg [31:0] gate=0;reg [191:0] notes=0;reg [255:0] velocity=0,expression=0;
    reg [7:0] bend=128;reg timbre=1;
    wire signed [15:0] current,legacy;wire cv,lv;
    integer frame,i,cycle,checked=0;reg [31:0] random_state=32'h12345678;
    playable_synth32 dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.note_index(notes),
        .velocity(velocity),.expression(expression),.bend(bend),.timbre(timbre),.sample_out(current),.sample_valid(cv));
    expression_legacy_playable_synth32 reference(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.note_index(notes),
        .velocity(velocity),.bend(bend),.timbre(timbre),.sample_out(legacy),.sample_valid(lv));
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        for(frame=0;frame<1400;frame=frame+1)begin
            if(frame==700)begin rst_n=0;@(negedge clk);rst_n=1;end
            for(i=0;i<32;i=i+1)begin
                random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
                notes[i*6 +: 6]=random_state%37;velocity[i*8 +: 8]=random_state[15:8];
                expression[i*8 +: 8]=~random_state[15:8];gate[i]=frame<20 ? 0 : random_state[17];
            end
            bend=frame%256;timbre=frame%2;tick=1;@(negedge clk);tick=0;
            for(cycle=1;cycle<256;cycle=cycle+1)begin
                if(cycle==120)begin expression=~expression;bend=~bend;end
                @(negedge clk);
                if(cv!==lv || current!==legacy)$fatal(1,"disabled PCM mismatch frame=%0d cycle=%0d",frame,cycle);
                if(cv)checked=checked+1;
            end
        end
        if(checked!=1400)$fatal(1,"did not check every completed frame");
        $display("PASS:1400 disabled-path PCM frames bit-exact against frozen1C8A, all32slots, invalid notes, bend, frame boundaries and reset");$finish;
    end
endmodule
