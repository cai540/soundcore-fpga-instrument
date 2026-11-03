`timescale 1ns/1ps
module tb_song_event_player;
    reg clk=0,rst_n=0,run=0,pause=0,restart=0;
    wire [10:0] index,length;
    wire [2:0] bank,pad;
    wire [5:0] note;
    wire gate,finished;
    wire [17:0] playback_ms;
    reg [17:0] paused_ms;
    always #5 clk=~clk;
    song_event_player #(.CLK_HZ(1000),.LENGTH0(3),
        .ROM0_FILE("tb/song_event_fixture.mem")) dut (
        .clk(clk),.rst_n(rst_n),.run(run),.pause(pause),
        .restart(restart),.song_select(1'b0),
        .event_index(index),.song_length(length),
        .event_bank(bank),.event_pad(pad),.note_index(note),
        .note_gate(gate),.finished(finished),.playback_ms(playback_ms)
    );
    initial begin
        repeat(2) @(negedge clk);rst_n=1;run=1;
        repeat(2) @(negedge clk);
        if(index!=0 || !gate || note!=0 || length!=3)
            $fatal(1,"first note failed");
        pause=1;
        paused_ms=playback_ms;
        repeat(25) @(negedge clk);
        if(index!=0 || gate || playback_ms!=paused_ms) $fatal(1,"pause/lyric clock failed");
        pause=0;
        repeat(20) @(negedge clk);
        if(index!=1 || gate || pad!=7) $fatal(1,"rest failed");
        repeat(10) @(negedge clk);
        if(index!=2 || !gate || note!=7) $fatal(1,"next note failed");
        repeat(30) @(negedge clk);
        if(!finished || gate || index!=3 || playback_ms!=60) $fatal(1,"finish/lyric clock failed");
        restart=1;@(negedge clk);restart=0;
        @(negedge clk);
        if(finished || index!=0 || playback_ms>1) $fatal(1,"restart failed");
        run=0;repeat(2)@(negedge clk);
        if(playback_ms!=0)$fatal(1,"stop did not reset lyric clock");
        $display("PASS: offline player pause/rest/restart/end, lyric clock freeze and reset");
        $finish;
    end
endmodule
