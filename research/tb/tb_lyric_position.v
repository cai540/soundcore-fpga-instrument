`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
module tb_lyric_position;
    reg clk=0,rst_n=0,song=0,autoplay=1;
    reg [17:0] ms=0;
    reg [10:0] event_index=0,autoplay_event=0;
    wire [6:0] phrase;
    wire [4:0] character;
    wire [7:0] progress;
    reg [71:0] words0[0:1023],words1[0:1023];
    reg [9:0] guide0[0:1023],guide1[0:1023];
    reg [71:0] expected;
    reg [23:0] notes0[0:1023],notes1[0:1023];
    integer i,s,count,events,word_id,n,clock_ms,duration;
    always #5 clk=~clk;
    song_lyric_position #(.WORD_COUNT0(`PRODUCT_SONG0_WORDS),.WORD_COUNT1(`PRODUCT_SONG1_WORDS),
        .EVENT_COUNT0(`PRODUCT_SONG0_EVENTS),.EVENT_COUNT1(`PRODUCT_SONG1_EVENTS)) dut(
        .clk(clk),.rst_n(rst_n),.song(song),.autoplay(autoplay),.playback_ms(ms),.guide_event(event_index),
        .autoplay_event(autoplay_event),.phrase(phrase),.character(character),.progress(progress));
    initial begin
        $readmemh("songs/rom_product_songs/lyric_words_0.mem",words0);$readmemh("songs/rom_product_songs/lyric_words_1.mem",words1);
        $readmemh("songs/rom_product_songs/lyric_guide_0.mem",guide0);$readmemh("songs/rom_product_songs/lyric_guide_1.mem",guide1);
        $readmemh(`PRODUCT_SONG0_ROM,notes0,0,`PRODUCT_SONG0_EVENTS-1);
        $readmemh(`PRODUCT_SONG1_ROM,notes1,0,`PRODUCT_SONG1_EVENTS-1);
        repeat(4)@(negedge clk);rst_n=1;
        for(s=0;s<2;s=s+1)begin
            song=s;autoplay=1;ms=0;autoplay_event=0;repeat(12)@(negedge clk);
            count=s ? `PRODUCT_SONG1_WORDS:`PRODUCT_SONG0_WORDS;
            for(i=0;i<count;i=i+1)begin
                expected=s ? words1[i]:words0[i];
                ms=(expected[17:0]+expected[35:18])/2;
                clock_ms=0;autoplay_event=0;
                events=s ? `PRODUCT_SONG1_EVENTS:`PRODUCT_SONG0_EVENTS;
                for(n=0;n<events;n=n+1)begin
                    duration=s ? ((notes1[n]>>6)&16'hffff):((notes0[n]>>6)&16'hffff);
                    if(clock_ms<=ms)autoplay_event=n;
                    clock_ms=clock_ms+duration;
                end
                repeat(24)@(negedge clk);
                if(phrase!=expected[66:60] || character!=expected[71:67] || progress<100 || progress>155)
                    $fatal(1,"autoplay lyric mismatch song=%0d word=%0d phrase=%0d char=%0d progress=%0d",s,i,phrase,character,progress);
            end
            autoplay=0;events=s ? `PRODUCT_SONG1_EVENTS:`PRODUCT_SONG0_EVENTS;
            for(i=0;i<=events;i=i+1)begin
                event_index=i;word_id=s ? guide1[i]:guide0[i];expected=s ? words1[word_id]:words0[word_id];
                repeat(6)@(negedge clk);
                if(phrase!=expected[66:60] || character!=expected[71:67] || progress!=(i==events ? 255:16))
                    $fatal(1,"guided lyric target mismatch song=%0d event=%0d",s,i);
            end
        end
        $display("PASS: all %0d timed lyric syllables and %0d guide events; completed target stable",`PRODUCT_SONG0_WORDS+`PRODUCT_SONG1_WORDS,`PRODUCT_SONG0_EVENTS+`PRODUCT_SONG1_EVENTS);$finish;
    end
endmodule
