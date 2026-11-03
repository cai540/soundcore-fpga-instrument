`timescale 1ns/1ps
module tb_audio_effects;
    reg clk=0,rst_n=0,tick=1;
    reg signed [15:0] dry=0;
    reg [2:0] enable=0;
    wire signed [15:0] sound;
    integer frame,echo_seen,chorus_seen,room_seen;
    always #5 clk=~clk;
    audio_effects dut (.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .dry_in(dry),.enable(enable),.sample_out(sound));
    initial begin
        repeat(2) @(negedge clk);rst_n=1;
        // The effect RAM is primed with silent samples after reset.
        repeat(8195) @(negedge clk);
        dry=16'sd8000;
        #1;if(sound!==16'sd8000)$fatal(1,"dry bypass changed");
        @(negedge clk);dry=0;
        enable=3'b111;
        echo_seen=0;chorus_seen=0;room_seen=0;
        for(frame=0;frame<8500;frame=frame+1)begin
            @(negedge clk);
            if(frame>8100 && sound!=0)echo_seen=1;
            if(frame>60 && frame<270 && sound!=0)chorus_seen=1;
            if(frame>750 && frame<1100 && sound!=0)room_seen=1;
        end
        if(!echo_seen || !chorus_seen || !room_seen)
            $fatal(1,"missing tail echo=%0d chorus=%0d reverb=%0d",
                echo_seen,chorus_seen,room_seen);
        enable=0;
        #1;if(sound!==0)$fatal(1,"bypass retained wet tail");
        $display("PASS: dry bypass, echo, chorus, reverb tails");
        $finish;
    end
endmodule
