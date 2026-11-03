`timescale 1ns/1ps
module tb_pt8211_tx_12m288;
    reg clk=0,rst_n=0;
    reg signed [15:0] sample_in=0;
    wire tick,bclk,ws,sd;
    integer clocks=0,last_tick=0,frames=0,bits=0,words=0;
    reg ready=0;
    reg [15:0] expected=0,decoded=0;
    always #5 clk=~clk;
    pt8211_tx_12m288 #(.OUTPUT_SHIFT(2)) dut(.clk_audio(clk),.rst_n(rst_n),
        .sample_in(sample_in),.sample_tick(tick),.audio_bclk(bclk),.audio_ws(ws),.audio_din(sd));
    function [15:0] pattern;
        input integer n;
        begin case(n%8)
            0:pattern=16'h7fff;1:pattern=16'h8000;2:pattern=16'hffff;
            3:pattern=16'h1234;4:pattern=16'h8001;5:pattern=16'h00ff;
            6:pattern=16'hff00;default:pattern=0;
        endcase end
    endfunction
    always @(posedge clk)if(rst_n)clocks=clocks+1;
    always @(negedge clk)if(rst_n && tick)begin
        if(frames>0 && clocks-last_tick!=256)$fatal(1,"wrong frame period");
        if(ready && bits!=32)$fatal(1,"stereo frame does not contain 32 bits");
        last_tick=clocks;frames=frames+1;bits=0;ready=1;
        expected=sample_in>>>2;
        sample_in=pattern(frames);
    end
    always @(posedge bclk)if(rst_n && ready)begin
        decoded={decoded[14:0],sd};
        if(ws!==(bits>=16))$fatal(1,"PT8211 WS polarity/word length mismatch");
        if(bits%16==15)begin
            if(decoded!==expected)$fatal(1,"PT8211 signed word mismatch %h vs %h",decoded,expected);
            words=words+1;
        end
        bits=bits+1;
    end
    always @(sd or ws)if(rst_n && ready && bclk)$fatal(1,"PT8211 data changed on receiver's high clock");
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        wait(words>=32);@(negedge clk);rst_n=0;ready=0;
        #1;if(bclk!==0 || sd!==0 || tick!==0)$fatal(1,"reset leaves stale audio");
        $display("PASS: PT8211 32 stereo words, signed scaling, left/right coherence, 256-clock cadence and reset");$finish;
    end
    initial begin #2000000;$fatal(1,"PT8211 timeout");end
endmodule
