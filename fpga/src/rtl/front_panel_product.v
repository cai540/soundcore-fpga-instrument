// Product front panel. Song/mode cursors are separate from committed settings.
// Local playback commands feed the same player as accepted App commands.
module front_panel_product #(
    parameter integer DEBOUNCE_CYCLES=245760,
    parameter integer LONG_PRESS_CYCLES=8601600,
    parameter integer DEPTH_TIMEOUT_CYCLES=61440000,
    parameter integer BLINK_CYCLES=3072000,
    parameter integer NUM_SONGS=2,
    parameter integer HANDPAN_ENABLE=0
) (
    input wire clk,rst_n,
    input wire bank_down_n,bank_up_n,timbre_n,song_back_n,play_pause_n,
    input wire enc_s1_n,enc_s2_n,enc_key_n,
    input wire remote_valid,
    input wire [7:0] remote_type,remote_value,
    input wire [55:0] remote_payload,
    input wire player_finished,
    input wire guide_finished,
    output reg [2:0] bank,
    output reg [1:0] timbre_select,
    output reg [1:0] ui_state,
    output reg [7:0] song_index,
    output wire [7:0] menu_song_index,
    output reg song_selected,
    output reg demo_mode,mode_menu,mode_cursor,
    output reg [4:0] volume_level,
    output reg vibrato_enabled,
    output reg [3:0] vibrato_depth,
    output reg depth_edit,
    output wire auth_pending,remote_write_allowed,guide_button_led,
    output reg player_command_valid,
    output reg [7:0] player_command,
    output reg guide_restart
);
    localparam [1:0] HOME=0,SELECT=1,RUN=2,PAUSE=3;
    localparam integer DBW=DEBOUNCE_CYCLES<2 ? 1:$clog2(DEBOUNCE_CYCLES+1);
    localparam integer LW=LONG_PRESS_CYCLES<2 ? 1:$clog2(LONG_PRESS_CYCLES+1);
    localparam integer TW=DEPTH_TIMEOUT_CYCLES<2 ? 1:$clog2(DEPTH_TIMEOUT_CYCLES+1);
    localparam integer BW=BLINK_CYCLES<2 ? 1:$clog2(BLINK_CYCLES+1);
    reg [7:0] sync1,sync2,stable,last;
    reg [DBW-1:0] debounce[0:7];
    reg [LW-1:0] song_hold,play_hold,enc_hold;
    reg song_long,play_long,enc_long,chord_seen;
    reg [TW-1:0] depth_idle;
    reg [BW-1:0] blink_count;
    reg blink;
    reg [7:0] song_cursor;
    reg return_to_list;
    integer i;
    wire [7:0] contacts={enc_key_n,enc_s2_n,enc_s1_n,
        play_pause_n,song_back_n,timbre_n,bank_up_n,bank_down_n};
    wire [4:0] down=~stable[4:0];
    wire multiple=|(down & (down-5'd1));
    wire released_all=&stable[4:0];
    wire [4:0] release_event=~last[4:0] & stable[4:0];
    wire encoder_step=last[5] && !stable[5];
    wire encoder_press=last[7] && !stable[7];
    wire encoder_release=!last[7] && stable[7];
    assign menu_song_index=ui_state==SELECT ? song_cursor:song_index;
    assign auth_pending=0;
    assign remote_write_allowed=0; // The top-level BLE session owns authorization.
    assign guide_button_led=!(demo_mode ? player_finished : guide_finished) &&
        (ui_state==RUN || (ui_state==PAUSE && blink));

    function [7:0] previous_song;
        input [7:0] current;
        begin previous_song=current==0 ? NUM_SONGS-1:current-1'b1;end
    endfunction
    function [7:0] next_song;
        input [7:0] current;
        begin next_song=current>=NUM_SONGS-1 ? 0:current+1'b1;end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            sync1<=8'hff;sync2<=8'hff;stable<=8'hff;last<=8'hff;
            for(i=0;i<8;i=i+1)debounce[i]<=0;
            bank<=2;timbre_select<=1;volume_level<=6;
            vibrato_enabled<=0;vibrato_depth<=4;depth_edit<=0;depth_idle<=0;
            ui_state<=HOME;song_index<=0;song_cursor<=0;song_selected<=0;
            demo_mode<=1;mode_menu<=0;mode_cursor<=1;return_to_list<=0;
            song_hold<=0;play_hold<=0;enc_hold<=0;
            song_long<=0;play_long<=0;enc_long<=0;chord_seen<=0;
            blink_count<=0;blink<=0;
            player_command_valid<=0;player_command<=0;guide_restart<=0;
        end else begin
            sync1<=contacts;sync2<=sync1;last<=stable;
            player_command_valid<=0;guide_restart<=0;
            for(i=0;i<8;i=i+1)begin
                if(sync2[i]==stable[i])debounce[i]<=0;
                else if(debounce[i]==DEBOUNCE_CYCLES-1)begin
                    stable[i]<=sync2[i];debounce[i]<=0;
                end else debounce[i]<=debounce[i]+1'b1;
            end
            if(multiple)chord_seen<=1;else if(released_all)chord_seen<=0;
            if(blink_count==BLINK_CYCLES-1)begin blink_count<=0;blink<=~blink;end
            else blink_count<=blink_count+1'b1;

            // Long K4 opens a cancellable mode selector; releasing it is not Back.
            if(last[3] && !stable[3])begin song_hold<=0;song_long<=0;end
            else if(!stable[3] && !song_long && !multiple && !chord_seen)begin
                if(song_hold==LONG_PRESS_CYCLES-1)begin
                    song_long<=1;mode_menu<=1;mode_cursor<=demo_mode;
                    return_to_list<=ui_state!=HOME;
                    if(ui_state!=SELECT)song_cursor<=song_index;
                    ui_state<=SELECT;depth_edit<=0;
                    player_command_valid<=1;player_command<=0;
                end else song_hold<=song_hold+1'b1;
            end
            // Long K5 returns both native modes to their beginning and pauses.
            if(last[4] && !stable[4])begin play_hold<=0;play_long<=0;end
            else if(!stable[4] && !play_long && !multiple && !chord_seen && (ui_state==RUN || ui_state==PAUSE))begin
                if(play_hold==LONG_PRESS_CYCLES-1)begin
                    play_long<=1;ui_state<=PAUSE;
                    if(demo_mode)begin player_command_valid<=1;player_command<=4;end
                    else guide_restart<=1;
                end else play_hold<=play_hold+1'b1;
            end

            if(released_all && !chord_seen)begin
                if(release_event[0])begin
                    if(ui_state==SELECT)begin
                        if(mode_menu)mode_cursor<=0;else song_cursor<=previous_song(song_cursor);
                    end else if(ui_state==HOME && bank!=0)bank<=bank-1'b1;
                end else if(release_event[1])begin
                    if(ui_state==SELECT)begin
                        if(mode_menu)mode_cursor<=1;else song_cursor<=next_song(song_cursor);
                    end else if(ui_state==HOME && bank!=4)bank<=bank+1'b1;
                end else if(release_event[2])begin
                    if(HANDPAN_ENABLE)case(timbre_select)
                        1:timbre_select<=0;0:timbre_select<=2;2:timbre_select<=3;default:timbre_select<=1;
                    endcase
                    else timbre_select<=timbre_select==0 ? 1:0;
                end
                else if(release_event[3] && !song_long)begin
                    if(mode_menu)begin mode_menu<=0;ui_state<=return_to_list ? SELECT:HOME;end
                    else if(ui_state==HOME)begin ui_state<=SELECT;song_cursor<=song_index;depth_edit<=0;end
                    else begin ui_state<=HOME;player_command_valid<=1;player_command<=0;end
                end else if(release_event[4] && !play_long)begin
                    if(mode_menu)begin
                        demo_mode<=mode_cursor;mode_menu<=0;ui_state<=SELECT;
                    end else if(ui_state==RUN)begin
                        if(demo_mode && player_finished)begin
                            player_command_valid<=1;player_command<=1;
                        end else begin
                            ui_state<=PAUSE;
                            if(demo_mode)begin player_command_valid<=1;player_command<=2;end
                        end
                    end else if(ui_state==PAUSE)begin
                        ui_state<=RUN;
                        if(demo_mode)begin player_command_valid<=1;player_command<=player_finished ? 1:3;end
                    end else if(ui_state==SELECT || song_selected)begin
                        if(ui_state==SELECT)song_index<=song_cursor;
                        song_selected<=1;ui_state<=RUN;
                        player_command_valid<=1;player_command<=demo_mode ? 1:0;
                    end else begin ui_state<=SELECT;song_cursor<=song_index;end
                end
            end

            // Selection-page encoder events never alter volume or vibrato.
            if(encoder_step)begin
                depth_idle<=0;
                if(ui_state==SELECT)begin
                    if(mode_menu)mode_cursor<=stable[6];
                    else song_cursor<=stable[6] ? next_song(song_cursor):previous_song(song_cursor);
                end else if(depth_edit)begin
                    if(stable[6] && vibrato_depth!=15)vibrato_depth<=vibrato_depth+1'b1;
                    else if(!stable[6] && vibrato_depth!=0)vibrato_depth<=vibrato_depth-1'b1;
                end else begin
                    if(stable[6] && volume_level!=31)volume_level<=volume_level+1'b1;
                    else if(!stable[6] && volume_level!=0)volume_level<=volume_level-1'b1;
                end
            end else if(depth_edit)begin
                if(depth_idle==DEPTH_TIMEOUT_CYCLES-1)begin depth_edit<=0;depth_idle<=0;end
                else depth_idle<=depth_idle+1'b1;
            end else depth_idle<=0;
            if(encoder_press)begin enc_hold<=0;enc_long<=0;end
            else if(!stable[7] && !enc_long && ui_state!=SELECT)begin
                if(enc_hold==LONG_PRESS_CYCLES-1)begin
                    enc_long<=1;depth_edit<=~depth_edit;depth_idle<=0;
                end else enc_hold<=enc_hold+1'b1;
            end
            if(encoder_release && !enc_long)begin
                if(ui_state==SELECT)begin
                    if(mode_menu)begin demo_mode<=mode_cursor;mode_menu<=0;end
                    else begin song_index<=song_cursor;song_selected<=1;ui_state<=HOME;end
                end else if(depth_edit)depth_edit<=0;
                else vibrato_enabled<=~vibrato_enabled;
            end

            // Remote commands remain authoritative on an exact same-clock conflict.
            if(remote_valid)begin
                case(remote_type)
                    8'h10:if(remote_value<=31)volume_level<=remote_value[4:0];
                    8'h11:if(remote_value<=4)bank<=remote_value[2:0];
                    8'h12:if(remote_value<=(HANDPAN_ENABLE ? 3:1))timbre_select<=remote_value[1:0];
                    8'h13:if(remote_value<=1)vibrato_enabled<=remote_value[0];
                    8'h1a:if(remote_value<=15)vibrato_depth<=remote_value[3:0];
                    8'h1f:begin bank<=remote_payload[2:0];timbre_select<=remote_payload[9:8];
                        volume_level<=remote_payload[20:16];vibrato_enabled<=remote_payload[24];vibrato_depth<=remote_payload[35:32];end
                    8'h14:if(remote_value<NUM_SONGS)begin
                        song_index<=remote_value;song_cursor<=remote_value;song_selected<=1;
                        ui_state<=SELECT;mode_menu<=0;player_command_valid<=0;
                    end
                    8'h15,8'h23:begin
                        if(remote_value<=3)begin
                            demo_mode<=remote_type==8'h23;mode_menu<=0;player_command_valid<=0;
                            case(remote_value)
                                0:ui_state<=HOME;
                                1:begin ui_state<=RUN;song_selected<=1;end
                                2:if(ui_state==RUN)ui_state<=PAUSE;
                                3:if(ui_state==PAUSE)ui_state<=RUN;
                            endcase
                        end
                    end
                    default:;
                endcase
            end
        end
    end
endmodule
