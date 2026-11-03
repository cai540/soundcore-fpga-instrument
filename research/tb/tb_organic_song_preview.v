`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
module tb_organic_song_preview;
    reg clk=0,rst_n=0,run=0,song=0;
    wire gate;
    wire [5:0] note;
    wire [31:0] step;
    wire signed [15:0] sound;
    integer n,fd,which,unused;
    reg [2047:0] output_path;
    always #5 clk=~clk;
    song_event_player #(.CLK_HZ(48000),.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ARTICULATION_GAP_MS(2),.ARTICULATION0_GAP_MS(12),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) player(
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),.restart(1'b0),
        .song_select(song),.note_index(note),.note_gate(gate));
    note_step_table35 lookup(.note_index(note),.phase_step(step));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(1'b1),.gate(gate),.phase_step(step),
        .velocity(8'd176),.timbre(!song),.sample_out(sound));
    initial begin
        output_path="build/organic_20261027/song.hex";which=0;
        unused=$value$plusargs("SONG=%d",which);unused=$value$plusargs("OUT=%s",output_path);
        song=which!=0;fd=$fopen(output_path,"w");if(!fd)$fatal(1,"song output cannot open");
        repeat(3)@(negedge clk);rst_n=1;run=1;
        for(n=0;n<960000;n=n+1)begin
            @(negedge clk);if((^sound)===1'bx)$fatal(1,"unknown song sample");
            $fdisplay(fd,"%04x",sound);
        end
        $fclose(fd);$display("PASS: song %0d 20-second actual player/instrument preview",which);$finish;
    end
endmodule
