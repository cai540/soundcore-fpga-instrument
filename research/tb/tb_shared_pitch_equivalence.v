`timescale 1ns/1ps
// A legacy spatial pitch implementation receives frame-frozen controls.
// Compare PCM and every independent oscillator with the shared implementation.
module tb_shared_pitch_equivalence;
    reg clk=0,rst_n=0,tick=0,timbre=1;
    always #5 clk=~clk;
    reg [31:0] gate=0,ref_gate=0;
    // Force the legacy combinational case tables to evaluate even when
    // note zero is the first value (the original wrapper test does this too).
    reg [191:0] notes=0,ref_notes={192{1'bx}};
    reg [255:0] velocity=0,ref_velocity=0;
    reg [7:0] bend=128,ref_bend=128;
    reg ref_timbre=1;
    wire signed [15:0] actual,expected;
    wire valid,ref_valid;
    integer frame,i,k,checked=0,actual_valids=0,reference_valids=0,age=0,max_age=0,nonzero=0;
    reg [31:0] random_state=32'h17054123;
    function [31:0] advance;
        input [31:0] q;
        begin advance={q[30:0],q[31]^q[21]^q[1]^q[0]};end
    endfunction
    playable_synth32 dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(gate),.note_index(notes),.velocity(velocity),.bend(bend),
        .timbre(timbre),.sample_out(actual),.sample_valid(valid));
    playable_synth32_legacy reference(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate(ref_gate),.note_index(ref_notes),.velocity(ref_velocity),.bend(ref_bend),
        .timbre(ref_timbre),.sample_out(expected),.sample_valid(ref_valid));
    always @(posedge clk)begin
        if(!rst_n)begin actual_valids=0;reference_valids=0;age=0;end
        else if(tick)begin
            ref_gate<=gate;ref_notes<=notes;ref_velocity<=velocity;
            ref_bend<=bend;ref_timbre<=timbre;
            actual_valids=0;reference_valids=0;age=0;
        end else begin
            age=age+1;#1;
            if(valid)begin actual_valids=actual_valids+1;if(age>max_age)max_age=age;end
            if(ref_valid)reference_valids=reference_valids+1;
        end
    end
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        for(frame=0;frame<1200;frame=frame+1)begin
            if(frame==600)begin
                // Abort one in-flight pitch/core frame, then recover cleanly.
                tick=1;@(negedge clk);tick=0;repeat(17)@(negedge clk);
                rst_n=0;repeat(4)@(negedge clk);
                if(valid || ref_valid)$fatal(1,"reset did not cancel in-flight work");
                rst_n=1;
            end
            for(i=0;i<32;i=i+1)begin
                random_state=advance(random_state);
                notes[i*6+:6]=frame<800 ? i : random_state[5:0];
                velocity[i*8+:8]=frame<300 ? 50+i : frame<600 ? 255 : random_state[7:0];
                gate[i]=frame<200 ? (i%4==0) : frame<500 ? 1 : frame<560 ? (i!=5) : random_state[8];
            end
            bend=frame<120 ? 128 : frame<200 ? 200 : random_state[23:16];
            timbre=(frame<600);
            if(frame==350 || frame==700)begin
                // Exercise mature vibrato/drift without simulating thousands
                // of additional warm-up frames. Both reference states match.
                for(i=0;i<32;i=i+1)begin
                    dut.synth.note_age[i]=24000;reference.synth.note_age[i]=24000;
                    dut.synth.expression_phase[i]=4123456+i*315271;
                    reference.synth.expression_phase[i]=4123456+i*315271;
                end
            end
            tick=1;@(negedge clk);tick=0;
            repeat(67)@(negedge clk);
            gate=~gate;notes=~notes;bend=~bend;velocity=~velocity;timbre=~timbre;
            repeat(152)@(negedge clk);
            if(actual_valids!=1 || reference_valids!=1 || max_age>200)
                $fatal(1,"missing/duplicate/late result frame=%0d",frame);
            if(actual!==expected)begin
                $display("reference gate=%h steps0=%h phase0=%h env0=%h accumulator=%h slot=%d wave=%h",
                    reference.effective_gate,reference.steps[31:0],reference.synth.phase[0],
                    reference.synth.envelope[0],reference.synth.accumulator,reference.synth.slot,reference.synth.wave_reg);
                $fatal(1,"PCM mismatch frame=%0d actual=%0d expected=%0d",frame,actual,expected);
            end
            if(actual!=0)nonzero=nonzero+1;
            for(i=0;i<32;i=i+1)begin
                if(dut.synth.phase[i]!==reference.synth.phase[i] ||
                   dut.synth.envelope[i]!==reference.synth.envelope[i] ||
                   dut.synth.gate_last[i]!==reference.synth.gate_last[i] ||
                   dut.synth.colour.random_state[i]!==reference.synth.colour.random_state[i])
                    $fatal(1,"voice state mismatch frame=%0d voice=%0d",frame,i);
            end
            checked=checked+1;
            repeat(36)@(negedge clk);
        end
        if(nonzero<100)$fatal(1,"comparison never rendered enough nonzero PCM");
        $display("PASS: %0d bit-exact PCM frames, 32 states, in-flight reset/release, grown vibrato, both timbres and frame mutations; max=%0d/256 clocks",checked,max_age);
        $finish;
    end
    initial begin #4000000;$fatal(1,"shared pitch equivalence timeout");end
endmodule
