`timescale 1ns/1ps
module tb_song_guide_long_boundary;
    reg clk=0,rst_n=0,hit=0;
    reg [1:0] state=0;
    wire [10:0] step,length;
    wire done;
    integer i;
    always #5 clk=~clk;
    song_guide_long #(.LENGTH0(1024),
        .ROM0_FILE("tmp/long_song_1024.mem")) dut (
        .clk(clk),.rst_n(rst_n),.ui_state(state),.song_select(1'b0),
        .strike_valid(hit),.strike_bank(3'd0),.strike_pad(3'd0),
        .step_index(step),.song_length(length),.completed(done)
    );
    initial begin
        repeat(2)@(negedge clk);rst_n=1;state=2;
        repeat(2)@(negedge clk);
        for(i=0;i<1024;i=i+1)begin
            @(negedge clk);hit=1;
            @(negedge clk);hit=0;
        end
        if(!done || step!=11'd1024 || length!=11'd1024)
            $fatal(1,"1024-note completion wrapped: step=%0d",step);
        $display("PASS: 1024-note guide completion does not wrap");
        $finish;
    end
endmodule
