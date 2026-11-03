`timescale 1ns/1ps
module tb_song_event_tempo;
    reg clk=0,rst_n=0,run=0,song=0;
    wire [10:0] index0,index1;
    always #5 clk=~clk;
    song_event_player #(.CLK_HZ(1000),.LENGTH0(3),.LENGTH1(3),
        .TEMPO0_NUM(4),.TEMPO1_NUM(5),.TEMPO_DEN(3),
        .ROM0_FILE("tb/song_event_fixture.mem"),
        .ROM1_FILE("tb/song_event_fixture.mem")) dut (
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),.restart(1'b0),
        .song_select(song),.event_index(index0),.song_length(),
        .event_bank(),.event_pad(),.note_index(),.note_gate(),.finished()
    );
    // A second player at default speed proves the tempo parameters actually
    // change the event boundary instead of merely changing the UI counter.
    song_event_player #(.CLK_HZ(1000),.LENGTH0(3),
        .ROM0_FILE("tb/song_event_fixture.mem")) normal (
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),.restart(1'b0),
        .song_select(1'b0),.event_index(index1),.song_length(),
        .event_bank(),.event_pad(),.note_index(),.note_gate(),.finished()
    );
    initial begin
        repeat(2) @(negedge clk); rst_n=1; run=1;
        repeat(22) @(negedge clk);
        if (index1!=1 || index0!=0) $fatal(1,"song 0 was not slowed");
        repeat(6) @(negedge clk);
        if (index0!=1) $fatal(1,"song 0 failed to advance");
        song=1;
        repeat(2) @(negedge clk);
        repeat(30) @(negedge clk);
        if (index0!=0) $fatal(1,"song 1 duration too short");
        repeat(5) @(negedge clk);
        if (index0!=1) $fatal(1,"song 1 failed to advance");
        $display("PASS: song-specific slower timing");
        $finish;
    end
endmodule
