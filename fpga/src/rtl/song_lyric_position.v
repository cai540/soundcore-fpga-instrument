// Timed lyric cursor for autoplay, event-linked cursor for strict guidance.
// ROMs contain words/timing only. Audio is still synthesized note by note.
module song_lyric_position #(
    parameter integer WORD_COUNT0=1,WORD_COUNT1=1,
    parameter integer EVENT_COUNT0=1,EVENT_COUNT1=1,
    parameter WORD0="@FPGA_ROOT@/src/assets/c30088c9_lyric_words_0.mem",
    parameter WORD1="@FPGA_ROOT@/src/assets/f0e05512_lyric_words_1.mem",
    parameter START0="@FPGA_ROOT@/src/assets/fc0eb70e_lyric_starts_0.mem",
    parameter START1="@FPGA_ROOT@/src/assets/cbde3099_lyric_starts_1.mem",
    parameter GUIDE0="@FPGA_ROOT@/src/assets/045d5c8c_lyric_guide_0.mem",
    parameter GUIDE1="@FPGA_ROOT@/src/assets/87b249b2_lyric_guide_1.mem"
)(
    input wire clk,rst_n,song,autoplay,
    input wire [17:0] playback_ms,
    input wire [10:0] autoplay_event,
    input wire [10:0] guide_event,
    output wire [6:0] phrase,
    output wire [4:0] character,
    output wire [7:0] progress
);
    reg [71:0] word0[0:1023],word1[0:1023];
    // Match hex-file widths and keep only ONE read port on each wide ROM.
    // The look-ahead timestamp has its own narrow ROM; it must not share a
    // 72-bit memory read/feedback path with the displayed word.
    reg [19:0] starts0[0:1023],starts1[0:1023];
    reg [11:0] guide0[0:1023],guide1[0:1023];
    initial begin
        $readmemh(WORD0,word0);$readmemh(WORD1,word1);
        $readmemh(START0,starts0);$readmemh(START1,starts1);
        $readmemh(GUIDE0,guide0);$readmemh(GUIDE1,guide1);
    end
    reg [9:0] cursor,read_cursor,read_selected_word;
    reg [11:0] mapped_word;
    reg [10:0] read_event,anchored_event;
    reg read_song,read_autoplay,read_valid;
    reg song_last;
    reg [71:0] current_word,display_word;
    reg [19:0] next_start;
    wire [10:0] word_count=song ? WORD_COUNT1:WORD_COUNT0;
    wire [10:0] event_count=song ? EVENT_COUNT1:EVENT_COUNT0;
    wire [10:0] selected_event=autoplay ? autoplay_event:guide_event;
    wire [9:0] guide_word=mapped_word[9:0];
    wire [9:0] selected_word=autoplay ? cursor:guide_word;
    wire [9:0] next_cursor=cursor+11'd1<word_count ? cursor+10'd1:cursor;
    wire map_ready=read_valid && read_song==song && read_autoplay==autoplay &&
                   read_event==selected_event;
    always @(posedge clk)begin
        mapped_word<=song ? guide1[selected_event[9:0]]:guide0[selected_event[9:0]];
        current_word<=song ? word1[selected_word]:word0[selected_word];
        next_start<=song ? starts1[next_cursor]:starts0[next_cursor];
        read_cursor<=cursor;
        read_selected_word<=selected_word;
        read_event<=selected_event;read_song<=song;read_autoplay<=autoplay;
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin cursor<=0;song_last<=0;anchored_event<=11'h7ff;read_valid<=0;end
        else begin
            read_valid<=1;
            song_last<=song;
            if(!autoplay || song!=song_last || playback_ms==0)begin
                cursor<=0;anchored_event<=11'h7ff;
            end else if(map_ready && autoplay_event!=anchored_event)begin
                // Re-anchor on EVERY real audio event. A stalled timing
                // comparison can never leave all following words at word 0.
                cursor<=guide_word<word_count ? guide_word:word_count-1'b1;
                anchored_event<=autoplay_event;
            end else if(map_ready && read_cursor==cursor && read_selected_word==cursor)begin
                // A guide target can cover several lyric syllables, or its
                // 50-ms annotation probe can belong to the following word.
                // Resolve BOTH directions using the actual playback clock.
                if(cursor!=0 && playback_ms<current_word[17:0])cursor<=cursor-1'b1;
                else if(cursor+11'd1<word_count && playback_ms>=next_start[17:0])cursor<=cursor+1'b1;
            end
        end
    end
    // Publish only a settled word. OLED frame snapshots must never observe
    // a transient future anchor while the synchronous ROM is catching up.
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)display_word<=0;
        else if(map_ready && read_selected_word==selected_word)begin
            if(!autoplay)display_word<=current_word;
            else if(anchored_event==autoplay_event && read_cursor==cursor &&
                playback_ms>=current_word[17:0] &&
                (cursor+11'd1>=word_count || playback_ms<next_start[17:0]))
                display_word<=current_word;
        end
    end
    wire [17:0] elapsed=playback_ms>display_word[17:0] ? playback_ms-display_word[17:0]:18'd0;
    wire [41:0] position_product=elapsed*display_word[59:36];
    wire [25:0] scaled=position_product>>16;
    assign phrase=display_word[66:60];
    assign character=display_word[71:67];
    assign progress=autoplay ? ((playback_ms>=display_word[35:18] || scaled>255) ? 8'd255:scaled[7:0]):
                    guide_event>=event_count ? 8'd255:8'd16;
endmodule
