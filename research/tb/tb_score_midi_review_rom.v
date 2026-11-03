`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
module tb_score_midi_review_rom;
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
    song_guide_long #(.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) guide (
        .clk(clk),.rst_n(rst_n),.ui_state(state),.song_select(select),
        .strike_valid(1'b0),.strike_bank(3'd0),.strike_pad(3'd0),
        .step_index(step),.song_length(length),.target_bank(bank),
        .target_pad(pad),.target_duration_ms(duration),
        .completed(completed),.correct_pulse(correct),
        .wrong_pulse(wrong),.target_led(led));
    song_event_player #(.CLK_HZ(1000),.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) player (
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),
        .restart(1'b0),.song_select(select),.event_index(play_step),
        .song_length(play_length),.event_bank(play_bank),
        .event_pad(play_pad),.note_index(note_index),
        .note_gate(gate),.finished(finished));
    initial begin
        repeat(2) @(negedge clk); rst_n=1;state=2;run=1;
        repeat(3) @(negedge clk);
        if (length!=`PRODUCT_SONG0_EVENTS || play_length!=`PRODUCT_SONG0_EVENTS || bank!=1 || pad!=5 ||
            play_bank!=bank || play_pad!=pad || !gate)
            $fatal(1,"Zuguo review ROM first note or length");
        state=1;select=1;run=0;
        repeat(3) @(negedge clk);state=2;run=1;
        repeat(3) @(negedge clk);
        if (length!=`PRODUCT_SONG1_EVENTS || play_length!=`PRODUCT_SONG1_EVENTS || bank!=2 || pad!=2 ||
            play_bank!=bank || play_pad!=pad || !gate)
            $fatal(1,"Chi Le Ge review ROM first note or length");
        $display("PASS: score/MIDI review ROMs load for guide and autoplay");
        $finish;
    end
endmodule
