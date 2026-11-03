`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
module tb_audio_song_full_playback;
    reg clk=0,rst_n=0,run=0,select=0;
    wire [10:0] index,length;
    wire [2:0] bank,pad;
    wire [5:0] note;
    wire gate,finished;
    reg [23:0] rom0[0:`PRODUCT_SONG0_EVENTS-1];
    reg [23:0] rom1[0:`PRODUCT_SONG1_EVENTS-1];
    integer i,expected,ticks,checked;
    always #5 clk=~clk;
    song_event_player #(.CLK_HZ(1000),.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),.ARTICULATION_GAP_MS(2),.ARTICULATION0_GAP_MS(12),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) dut (
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),.restart(1'b0),
        .song_select(select),.event_index(index),.song_length(length),
        .event_bank(bank),.event_pad(pad),.note_index(note),
        .note_gate(gate),.finished(finished));
    task play_complete;
        input which;
        begin
            run=0;select=which;
            repeat(3) @(negedge clk);
            expected=0;
            if(which) begin
                for(i=0;i<`PRODUCT_SONG1_EVENTS;i=i+1) expected=expected+((rom1[i]>>6)&16'hffff);
            end else begin
                for(i=0;i<`PRODUCT_SONG0_EVENTS;i=i+1) expected=expected+((rom0[i]>>6)&16'hffff);
            end
            run=1;
            @(negedge clk);
            ticks=0;checked=0;
            while(!finished && ticks<300000) begin
                if(pad==7 && gate) $fatal(1,"rest emitted a sounding note");
                if(pad<7 && gate!=(dut.elapsed_ms+(which ? 2:12)<dut.duration_ms))
                    $fatal(1,"unexpected articulation gap inside a note");
                if(index>length) $fatal(1,"player read beyond the new song length");
                checked=checked+1;
                @(negedge clk);ticks=ticks+1;
            end
            if(!finished || gate || index!=length || ticks!=expected)
                $fatal(1,"song %0d ended at %0d ticks; expected %0d",which,ticks,expected);
            $display("PASS: song %0d full duration %0d ms, %0d events",which,ticks,length);
        end
    endtask
    initial begin
        $readmemh(`PRODUCT_SONG0_ROM,rom0);
        $readmemh(`PRODUCT_SONG1_ROM,rom1);
        repeat(2) @(negedge clk);rst_n=1;
        play_complete(0);
        play_complete(1);
        $finish;
    end
endmodule
