`timescale 1ns/1ps
module tb_banked32_headroom;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, sample_tick=0;
    reg [191:0] notes=0;
    reg [255:0] velocity=0;
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer i, cycle=0, frame=0, checks=0, peak=0, abs_sample;
    integer saturated=0, late=0;
    playable_synth32 dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(32'hffffffff), .note_index(notes),
        .velocity(velocity), .bend(8'd128), .timbre(1'b1),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );
    initial begin
        for(i=0;i<32;i=i+1) begin
            notes[i*6 +: 6]=i;
            velocity[i*8 +: 8]=8'd255;
        end
        repeat(3) @(negedge clk); rst_n=1;
    end
    always @(negedge clk) if(rst_n) begin
        sample_tick=(cycle==0);
        cycle=(cycle+1)%256;
        if(sample_tick) frame=frame+1;
    end
    always @(posedge clk) if(rst_n && sample_valid) begin
        if(cycle>72) late=late+1;
        if(frame>500) begin
            checks=checks+1;
            abs_sample=sample_out<0 ? -sample_out : sample_out;
            if(abs_sample>peak) peak=abs_sample;
            if(sample_out==16'sh7fff || sample_out==16'sh8000)
                saturated=saturated+1;
        end
        if(frame==4096) begin
            if(late!=0 || saturated!=0 || peak==0 || checks<3000)
                $fatal(1,"32-note high-velocity headroom failed peak=%0d clips=%0d late=%0d checks=%0d",
                       peak,saturated,late,checks);
            $display("PASS: 32 notes at velocity 255; raw peak=%0d, clips=0, render<72/256 clocks",
                     peak);
            $finish;
        end
    end
endmodule
