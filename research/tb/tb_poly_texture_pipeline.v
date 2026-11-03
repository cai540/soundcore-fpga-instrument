`timescale 1ns/1ps
module tb_poly_texture_pipeline;
    reg clk=0,rst_n=0,tick=0,timbre=1;
    reg [31:0] gate=0;
    reg [1023:0] steps=0;
    reg [255:0] velocity=0;
    wire signed [15:0] actual,reference;
    wire actual_valid,reference_valid;
    integer n,i,checks=0;
    always #5 clk=~clk;
    poly_synth32_tm dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),
        .phase_step(steps),.velocity(velocity),.timbre(timbre),.sample_out(actual),.sample_valid(actual_valid));
    poly_synth32_reference ref_voice(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),
        .phase_step(steps),.velocity(velocity),.timbre(timbre),.sample_out(reference),.sample_valid(reference_valid));
    initial begin
        for(i=0;i<32;i=i+1)begin steps[i*32+:32]=23409859+i*613319;velocity[i*8+:8]=40+i;end
        repeat(3)@(negedge clk);rst_n=1;
        for(n=0;n<900;n=n+1)begin
            if(n==0)gate=32'h11;
            if(n==80)gate=32'h2211;
            if(n==150)gate[0]=0;
            if(n==180)gate[0]=1;
            if(n==250)timbre=0;
            if(n==270)gate=32'h80002231;
            if(n==350)begin
                // Also compare fully grown vibrato and nonzero drift inputs,
                // without spending seconds simulating every preceding sample.
                for(i=0;i<32;i=i+1)begin
                    dut.note_age[i]=24000;ref_voice.note_age[i]=24000;
                    dut.expression_phase[i]=i*315271+4123456;
                    ref_voice.expression_phase[i]=i*315271+4123456;
                end
            end
            if(n==500)gate=32'h80809251;
            if(n==700)gate=0;
            @(negedge clk);tick=1;@(negedge clk);tick=0;
            repeat(200)@(negedge clk);
            if(dut.busy || dut.completed_voice_count!=32)$fatal(1,"pipeline missed frame deadline");
            if(actual!==reference)$fatal(1,"pipelining changed audio frame %0d: %0d != %0d",n,actual,reference);
            for(i=0;i<32;i=i+1)begin
                if(dut.phase[i]!==ref_voice.phase[i] || dut.envelope[i]!==ref_voice.envelope[i])
                    $fatal(1,"pipeline changed per-voice state");
            end
            checks=checks+1;
            repeat(54)@(negedge clk);
        end
        $display("PASS: %0d bit-exact frames vs original texture engine; 128 clocks fits 256-clock frame",checks);$finish;
    end
endmodule
