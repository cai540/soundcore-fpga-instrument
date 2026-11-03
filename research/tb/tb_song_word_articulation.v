`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
module tb_song_word_articulation;
    reg clk=0,rst_n=0,run=0;
    always #5 clk=~clk;
    wire [10:0] index;
    wire gate;
    wire [5:0] note_index;
    wire signed [15:0] audio;
    integer before_level,after_level;
    song_event_player #(.CLK_HZ(48000),.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ARTICULATION_GAP_MS(2),.ARTICULATION0_GAP_MS(12),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) player(
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),.restart(1'b0),.song_select(1'b0),
        .event_index(index),.note_gate(gate),.note_index(note_index));
    synth_voice #(.INSTRUMENT_PRESETS(1)) voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(1'b1),.gate(gate),
        .phase_step(note_index==12 ? 32'd46819718 : 32'd23409859),
        .velocity(8'd100),.timbre(1'b1),.sample_out(audio));
    initial begin
        repeat(3)@(negedge clk);rst_n=1;run=1;
        // Real score events 28/29: '出' C4 -> '一' C5. Keep the lyric
        // event boundary and soft articulation while correcting its octave.
        wait(index==28 && player.elapsed_ms==player.duration_ms-13);
        @(negedge clk);before_level=voice.envelope;
        if(note_index!=0) $fatal(1,"'出' must retain its valid low C4");
        wait(index==29);@(negedge clk);after_level=voice.envelope;
        if(note_index!=12) $fatal(1,"'一' lost its score-required C5 octave rise");
        if(before_level<29000 || after_level<7000 || after_level>13000)
            $fatal(1,"word articulation not soft/audible: before=%0d after=%0d",before_level,after_level);
        // The instrument now has a smooth 256-frame (5.33 ms) reed onset.
        // It starts immediately; allow its actual envelope time to settle.
        repeat(400)@(negedge clk);
        if(voice.envelope<29000 || !gate)
            $fatal(1,"next syllable failed to re-attack without a delayed event");
        $display("PASS: actual song/synth C4 -> C5 lyric transition, envelope %0d -> %0d -> %0d; no full silence",before_level,after_level,voice.envelope);
        $finish;
    end
    initial begin #30000000;$fatal(1,"word articulation timeout");end
endmodule
