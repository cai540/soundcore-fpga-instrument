`timescale 1ns/1ps
module tb_vocal_trimmed_rom;
    reg clk=0,rst_n=0,select=0;
    reg [1:0] state=0;
    reg run=0;
    wire [10:0] step,length,play_step,play_length;
    wire [2:0] bank,pad,play_bank,play_pad;
    wire [15:0] duration;
    wire completed,correct,wrong,gate,finished;
    wire [6:0] led;
    wire [5:0] note_index;
    always #5 clk=~clk;
    song_guide_long #(.LENGTH0(474),.LENGTH1(667),
        .ROM0_FILE("songs/rom_vocal_trimmed_experiment/song_0.mem"),
        .ROM1_FILE("songs/rom_vocal_trimmed_experiment/song_1.mem")) guide (
        .clk(clk),.rst_n(rst_n),.ui_state(state),.song_select(select),
        .strike_valid(1'b0),.strike_bank(3'd0),.strike_pad(3'd0),
        .step_index(step),.song_length(length),.target_bank(bank),
        .target_pad(pad),.target_duration_ms(duration),
        .completed(completed),.correct_pulse(correct),
        .wrong_pulse(wrong),.target_led(led));
    song_event_player #(.CLK_HZ(1000),.LENGTH0(474),.LENGTH1(667),
        .ROM0_FILE("songs/rom_vocal_trimmed_experiment/song_0.mem"),
        .ROM1_FILE("songs/rom_vocal_trimmed_experiment/song_1.mem")) player (
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),
        .restart(1'b0),.song_select(select),.event_index(play_step),
        .song_length(play_length),.event_bank(play_bank),
        .event_pad(play_pad),.note_index(note_index),
        .note_gate(gate),.finished(finished));
    initial begin
        repeat(2) @(negedge clk); rst_n=1;state=2;run=1;
        repeat(2) @(negedge clk);
        if (length!=474 || play_length!=474 || bank!=1 || pad!=4 ||
            play_bank!=bank || play_pad!=pad || !gate)
            $fatal(1,"Lantingxu must start at first vocal note");
        state=1;select=1;run=0;
        repeat(3) @(negedge clk);state=2;run=1;
        repeat(3) @(negedge clk);
        if (length!=667 || play_length!=667 || bank!=2 || pad!=0 ||
            play_bank!=bank || play_pad!=pad || !gate)
            $fatal(1,"Qian Si Xi must start at first vocal note");
        $display("PASS: both vocal ROMs start on the first guide/playback note");
        $finish;
    end
endmodule
