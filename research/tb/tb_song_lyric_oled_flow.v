`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
// End-to-end first eleven seconds: audio index -> lyric cursor -> actual
// complete I2C frames. No manually supplied phrase/character/progress values.
module tb_song_lyric_oled_flow;
    reg clk=0,rst_n=0,run=0;
    always #5 clk=~clk;
    wire [10:0] event_index;
    wire [17:0] ms;
    wire [6:0] phrase;
    wire [4:0] character;
    wire [7:0] progress;
    tri1 scl,sda;
    integer frames=0,changed_frames=0,bytes=0,fd;
    integer max_character=0,max_phrase=0;
    reg [7:0] previous_pixels[0:511];
    integer changed_bytes=0;
    reg capturing=0;
    reg [1023:0] path;
    song_event_player #(.CLK_HZ(192000),.LENGTH0(`PRODUCT_SONG0_EVENTS),
        .ARTICULATION0_GAP_MS(12),.ROM0_FILE(`PRODUCT_SONG0_ROM)) player(
        .clk(clk),.rst_n(rst_n),.run(run),.pause(1'b0),.restart(1'b0),.song_select(1'b0),
        .event_index(event_index),.playback_ms(ms));
    song_lyric_position #(.WORD_COUNT0(`PRODUCT_SONG0_WORDS),.WORD_COUNT1(`PRODUCT_SONG1_WORDS),
        .EVENT_COUNT0(`PRODUCT_SONG0_EVENTS),.EVENT_COUNT1(`PRODUCT_SONG1_EVENTS)) lyrics(
        .clk(clk),.rst_n(rst_n),.song(1'b0),.autoplay(run),.playback_ms(ms),
        .autoplay_event(event_index),.guide_event(11'd0),.phrase(phrase),.character(character),.progress(progress));
    oled_status_ssd1315 #(.I2C_DIV(1),.REFRESH_CYCLES(1920000),.LYRIC_OVERLAY(1)) oled(
        .clk(clk),.rst_n(rst_n),.bank(3'd0),.timbre(1'b1),.volume(5'd16),.vibrato(1'b0),
        .ui_state(2'd0),.guide_step(event_index),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd1),.auth_pending(1'b0),.remote_write_allowed(1'b1),.ble_frame_seen(1'b1),
        .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),
        .lyric_mode(run),.lyric_phrase(phrase),.lyric_character(character),.lyric_progress(progress),
        .oled_scl(scl),.oled_sda(sda));
    assign sda=(oled.writer.state==4 || oled.writer.state==5 || oled.writer.state==9) ? 1'b0:1'bz;
    initial begin
        repeat(4)@(negedge clk);rst_n=1;run=1;
        while(ms<11000)begin
            @(negedge clk);
            if(oled.tx_start && oled.phase==2)begin
                if(oled.page_index==0 && oled.column==0)begin
                    bytes=0;changed_bytes=0;capturing=oled.shown_lyric_mode;
                    if(capturing)begin
                        $sformat(path,"build/lyric_flow_frame_%0d.hex",frames);fd=$fopen(path,"w");
                        if(oled.shown_lyric_character>max_character)max_character=oled.shown_lyric_character;
                        if(oled.shown_lyric_phrase>max_phrase)max_phrase=oled.shown_lyric_phrase;
                    end
                end
                if(capturing)begin
                    if(oled.page_index*128+oled.column!=bytes)$fatal(1,"I2C frame skipped a byte");
                    $fdisplay(fd,"%02x",oled.tx_payload);
                    if(^oled.tx_payload===1'bx)$fatal(1,"unknown I2C pixel byte");
                    if(bytes<512)begin
                        // Compare exact bytes: a rotate/XOR checksum can
                        // cancel identical highlight masks on two pages.
                        if(frames!=0 && previous_pixels[bytes]!==oled.tx_payload)
                            changed_bytes=changed_bytes+1;
                        previous_pixels[bytes]=oled.tx_payload;
                    end
                    bytes=bytes+1;
                    if(bytes==1024)begin
                        $fclose(fd);capturing=0;
                        if(frames!=0 && changed_bytes!=0)changed_frames=changed_frames+1;
                        frames=frames+1;
                    end
                end
            end
        end
        if(capturing)$fclose(fd);
        if(frames<10 || changed_frames<8 || max_character<6 || max_phrase<1)
            $fatal(1,"OLED froze at first lyric: frames=%0d changed=%0d char=%0d phrase=%0d",frames,changed_frames,max_character,max_phrase);
        $display("PASS: actual-player/OLED I2C flow: %0d complete frames, %0d changed, reached char %0d phrase %0d",frames,changed_frames,max_character,max_phrase);$finish;
    end
    initial begin #30000000;$fatal(1,"OLED lyric flow timeout");end
endmodule
