`timescale 1ns/1ps
// Exhaustive external pitch contract. The oracle is computed independently
// from MIDI frequencies by Python, including invalid note encodings.
module tb_shared_pitch_snapshot;
    reg clk=0,rst_n=0,tick=0,timbre=1;
    always #5 clk=~clk;
    reg [31:0] gate=0;
    reg [191:0] notes=0;
    reg [255:0] velocity=0;
    reg [7:0] bend=128;
    wire signed [15:0] audio;
    wire valid;
    reg [31:0] oracle[0:16383];
    reg [31:0] expected_gate;
    integer bend_i,group_i,i,k,note_i,checks=0,valids=0,age=0,max_age=0;
    playable_synth32 dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(gate),.note_index(notes),.velocity(velocity),.bend(bend),
        .timbre(timbre),.sample_out(audio),.sample_valid(valid));
    always @(posedge clk) begin
        if(!rst_n)begin age=0;valids=0;end
        else if(tick)begin
            age=0;valids=0;
        end else begin
            age=age+1;
            // Observe post-edge values, so the deadline includes every cycle.
            #1;
            if(valid)begin
                valids=valids+1;
                if(age>max_age)max_age=age;
                if(age>200)$fatal(1,"sample deadline exceeded at %0d",age);
            end
        end
    end
    initial begin
        $readmemh("build/shared_pitch_20261028/pitch_oracle.mem",oracle);
        repeat(4)@(negedge clk);rst_n=1;
        for(bend_i=0;bend_i<256;bend_i=bend_i+1)begin
            for(group_i=0;group_i<2;group_i=group_i+1)begin
                for(i=0;i<32;i=i+1)begin
                    note_i=group_i*32+i;
                    notes[i*6+:6]=note_i;
                    velocity[i*8+:8]=16+i*5;
                    gate[i]=((i+bend_i)%3!=0);
                    expected_gate[i]=gate[i] && note_i<35;
                end
                bend=bend_i;timbre=group_i==0;
                tick=1;@(negedge clk);tick=0;
                // All live controls change after the boundary. This must
                // not tear one audio frame into multiple parameter versions.
                gate=~gate;notes=~notes;velocity=~velocity;bend=~bend;timbre=~timbre;
                repeat(219)@(negedge clk);
                if(valids!=1)$fatal(1,"expected one completed frame, got %0d",valids);
                if(dut.synth.completed_voice_count!==6'd32)$fatal(1,"not all voices completed");
                if(dut.effective_gate!==expected_gate)$fatal(1,"frame gate snapshot mismatch");
                for(i=0;i<32;i=i+1)begin
                    note_i=group_i*32+i;
                    if(dut.steps[i*32+:32]!==oracle[bend_i*64+note_i])
                        $fatal(1,"pitch snapshot mismatch bend=%0d note=%0d got=%0d expected=%0d",
                            bend_i,note_i,dut.steps[i*32+:32],oracle[bend_i*64+note_i]);
                    if(dut.synth.gate_last[i]!==expected_gate[i])$fatal(1,"voice gate torn at %0d",i);
                    checks=checks+1;
                end
                repeat(36)@(negedge clk);
            end
        end
        $display("PASS: %0d pitch cases; all note encodings x bends, atomic frames, max completion=%0d/256 clocks",checks,max_age);
        $finish;
    end
    initial begin #2000000;$fatal(1,"shared pitch snapshot timeout");end
endmodule
