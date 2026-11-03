`timescale 1ns/1ps
module tb_additive32_tm;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, sample_tick=0, gate=0;
    reg [31:0] base_step=32'd23409859;
    reg [7:0] velocity=8'd160;
    reg [31:0] component_mask=32'hffffffff;
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer cycle=0, frames=0, valid_frames=0, i;
    reg saw_audio=0;
    reg [31:0] phase31_before;
    reg [15:0] env31_before;
    additive32_tm dut(
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .gate(gate),.base_step(base_step),.velocity(velocity),
        .component_mask(component_mask),
        .sample_out(sample_out),.sample_valid(sample_valid));
    always @(negedge clk) begin
        if (!rst_n) begin cycle=0; sample_tick=0; end
        else begin
            sample_tick=(cycle==0);
            cycle=(cycle+1)%256;
            if (sample_tick) frames=frames+1;
            if (sample_valid) begin
                valid_frames=valid_frames+1;
                if (sample_out!=0) saw_audio=1;
            end
        end
    end
    initial begin
        repeat (4) @(negedge clk);
        rst_n=1; gate=1;
        wait(frames==100);
        repeat(80) @(negedge clk);
        if (valid_frames!=frames || !saw_audio)
            $fatal(1,"missing additive samples");
        for(i=0;i<32;i=i+1) begin
            if(dut.phase[i]==0 || dut.envelope[i]==0)
                $fatal(1,"component %0d inactive",i);
            if(i>0 && dut.phase[i]==dut.phase[i-1])
                $fatal(1,"component %0d lacks independent phase",i);
        end
        phase31_before=dut.phase[31];
        env31_before=dut.envelope[31];
        component_mask[31]=0;
        wait(frames==105);
        repeat(80) @(negedge clk);
        if(dut.envelope[31]!=0 || dut.envelope[30]==0 ||
           dut.phase[31]!=phase31_before || dut.phase[30]==dut.phase[29])
            $fatal(1,"component 32 isolation failed");
        component_mask[31]=1;
        gate=0;
        wait(frames==900);
        repeat(80) @(negedge clk);
        for(i=0;i<32;i=i+1)
            if(dut.envelope[i]!=0)
                $fatal(1,"component %0d failed to release",i);
        if(sample_out!=0)
            $fatal(1,"output not silent after release");
        $display("PASS: 32 independent additive phases, envelopes, frame timing and release");
        $finish;
    end
endmodule
