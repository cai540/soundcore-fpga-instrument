`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
// Use the actual audio player and actual lyric ROMs, not hand-jumped times.
module tb_song_lyric_continuous;
    reg clk=0,rst_n=0,song=0,command_valid=0;
    reg [7:0] command_value=0;
    always #5 clk=~clk;
    wire active,paused,restart,finished;
    wire [10:0] event_index;
    wire [17:0] ms;
    wire [6:0] phrase;
    wire [4:0] character;
    wire [7:0] progress;
    reg [71:0] words0[0:1023],words1[0:1023];
    reg [71:0] expected,next_expected;
    integer s,count,word_id,checked=0,held_ms,held_event;
    reg [6:0] held_phrase;
    reg [4:0] held_character;
    reg [7:0] held_progress;
    reg did_pause;
    song_autoplay_control control(.clk(clk),.rst_n(rst_n),.command_valid(command_valid),
        .command_type(8'h23),.command_value(command_value),.song_index({7'd0,song}),
        .player_finished(finished),.active(active),.paused(paused),.restart_pulse(restart));
    song_event_player #(.CLK_HZ(32000),.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ARTICULATION_GAP_MS(2),.ARTICULATION0_GAP_MS(12),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) player(
        .clk(clk),.rst_n(rst_n),.run(active),.pause(paused),.restart(restart),.song_select(song),
        .event_index(event_index),.finished(finished),.playback_ms(ms));
    song_lyric_position #(.WORD_COUNT0(`PRODUCT_SONG0_WORDS),.WORD_COUNT1(`PRODUCT_SONG1_WORDS),
        .EVENT_COUNT0(`PRODUCT_SONG0_EVENTS),.EVENT_COUNT1(`PRODUCT_SONG1_EVENTS)) lyrics(
        .clk(clk),.rst_n(rst_n),.song(song),.autoplay(active),.playback_ms(ms),
        .autoplay_event(event_index),.guide_event(11'd0),.phrase(phrase),.character(character),.progress(progress));
    task command;
        input [7:0] value;
        begin
            @(negedge clk);command_value=value;command_valid=1;
            @(negedge clk);command_valid=0;
            repeat(8)@(negedge clk);
        end
    endtask
    initial begin
        $readmemh("songs/rom_product_songs/lyric_words_0.mem",words0);
        $readmemh("songs/rom_product_songs/lyric_words_1.mem",words1);
        repeat(4)@(negedge clk);rst_n=1;
        for(s=0;s<2;s=s+1)begin
            command(0);song=s;repeat(12)@(negedge clk);command(1);
            // Replay from an already advanced position, without resetting
            // either the OLED or lyric ROM pipeline.
            wait(ms==1100);command(1);wait(ms==0);repeat(12)@(negedge clk);
            word_id=0;did_pause=0;
            count=s ? `PRODUCT_SONG1_WORDS:`PRODUCT_SONG0_WORDS;
            while(!finished)begin
                @(negedge clk);
                if(ms>1 && player.cycle_count==24 && !paused)begin
                    next_expected=s ? words1[word_id+1]:words0[word_id+1];
                    while(word_id+1<count && ms>=next_expected[17:0])begin
                        word_id=word_id+1;
                        next_expected=s ? words1[word_id+1]:words0[word_id+1];
                    end
                    expected=s ? words1[word_id]:words0[word_id];
                    if(phrase!==expected[66:60] || character!==expected[71:67])
                        $fatal(1,"continuous lyric stalled/misaligned song=%0d ms=%0d event=%0d expectedword=%0d got=%0d/%0d",s,ms,event_index,word_id,phrase,character);
                    if(ms>=expected[35:18] && progress!=255)
                        $fatal(1,"completed syllable did not remain highlighted");
                    checked=checked+1;
                    if(ms==1800 && !did_pause)begin
                        command(2);did_pause=1;
                        held_ms=ms;held_event=event_index;held_phrase=phrase;
                        held_character=character;held_progress=progress;
                        repeat(400)@(negedge clk);
                        if(ms!=held_ms || event_index!=held_event || phrase!=held_phrase ||
                            character!=held_character || progress!=held_progress)
                            $fatal(1,"pause moved audio or lyric position");
                        command(3);
                    end
                end
            end
            repeat(16)@(negedge clk);
            expected=s ? words1[count-1]:words0[count-1];
            if(phrase!=expected[66:60] || character!=expected[71:67] || progress!=255)
                $fatal(1,"song end lost final word");
            $display("PASS: song %0d actual-player lyric flow: %0d words, pause/resume/restart and final highlight",s,count);
        end
        $display("PASS: %0d continuously clocked lyric checkpoints across both songs",checked);$finish;
    end
    initial begin #150000000;$fatal(1,"continuous lyric timeout");end
endmodule
