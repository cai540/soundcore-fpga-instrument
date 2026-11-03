`timescale 1ns/1ps
module tb_song_autoplay_control;
    reg clk=0,rst_n=0,valid=0,finished=0;
    reg [7:0] typ=0,value=0,song=0;
    wire active,paused,restart;
    wire [1:0] state;
    always #5 clk=~clk;
    song_autoplay_control dut (
        .clk(clk),.rst_n(rst_n),.command_valid(valid),
        .command_type(typ),.command_value(value),.song_index(song),
        .player_finished(finished),.active(active),.paused(paused),
        .restart_pulse(restart),.playback_state(state)
    );
    task command;
        input [7:0] v;
        begin
            @(negedge clk);typ=8'h23;value=v;valid=1;
            @(negedge clk);valid=0;
        end
    endtask
    initial begin
        repeat(2) @(negedge clk);rst_n=1;
        command(1);
        if(!active || paused || state!=1 || !restart)
            $fatal(1,"start failed");
        command(2);
        if(!active || !paused || state!=2) $fatal(1,"pause failed");
        command(3);
        if(!active || paused || state!=1) $fatal(1,"resume failed");
        finished=1;#1;
        if(state!=3) $fatal(1,"finished state failed");
        command(0);
        if(active || state!=0) $fatal(1,"stop failed");
        command(1);
        song=1;@(negedge clk);
        if(active) $fatal(1,"song change did not stop old song");
        $display("PASS: offline autoplay command lifecycle");
        $finish;
    end
endmodule
