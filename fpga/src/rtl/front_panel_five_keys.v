// Five external active-low momentary buttons plus the passive EC11.
// This controller is intentionally separate from the accepted audio top.
// All inputs require verified 3.3 V pull-ups; do not use the Dock's 1.5 V KEY pins.
module front_panel_five_keys #(
    parameter integer DEBOUNCE_CYCLES = 245760, // 20 ms at 12.288 MHz
    parameter integer LONG_PRESS_CYCLES = 8601600, // 0.7 s
    parameter integer DEPTH_EDIT_TIMEOUT_CYCLES = 61440000, // 5 s
    parameter integer AUTH_CONFIRM_CYCLES = 122880000, // 10 s
    parameter integer AUTH_WINDOW_CYCLES = 36864000, // 3 s without BLE heartbeat
    parameter integer NUM_SONGS = 2,
    parameter integer REMOTE_CONTROL = 0,
    parameter integer PANEL_AUTH_REQUIRED = 1
) (
    input wire clk,
    input wire rst_n,
    input wire bank_down_n,
    input wire bank_up_n,
    input wire timbre_n,
    input wire song_back_n,
    input wire play_pause_n,
    input wire enc_s1_n,
    input wire enc_s2_n,
    input wire enc_key_n,
    input wire remote_valid,
    input wire [7:0] remote_type,
    input wire [7:0] remote_value,
    input wire [55:0] remote_payload,
    output reg [2:0] bank,
    output reg timbre_select, // 1=harmonica, 0=erhu
    output reg [1:0] ui_state, // 0=play, 1=song list, 2=guide running, 3=paused
    output reg [7:0] song_index,
    output reg song_selected, // K5 in PLAY opens the list until a song was chosen
    output reg [4:0] volume_level, // 0..31; audio gain ramp is integrated later
    output reg vibrato_enabled,
    output reg [3:0] vibrato_depth,
    output reg depth_edit,
    output reg auth_pending,
    output reg remote_write_allowed,
    output wire guide_led_on,
    output wire guide_led_blink // external LED driver supplies blink timing
);
    localparam [1:0] PLAY = 2'd0, SONG_LIST = 2'd1,
                     GUIDE_RUN = 2'd2, GUIDE_PAUSE = 2'd3;
    localparam integer DB_BITS = DEBOUNCE_CYCLES < 2 ? 1 :
                                 $clog2(DEBOUNCE_CYCLES);
    localparam integer HOLD_BITS = LONG_PRESS_CYCLES < 2 ? 1 :
                                   $clog2(LONG_PRESS_CYCLES + 1);
    localparam integer IDLE_BITS = DEPTH_EDIT_TIMEOUT_CYCLES < 2 ? 1 :
                                   $clog2(DEPTH_EDIT_TIMEOUT_CYCLES + 1);
    localparam integer AUTH_CONFIRM_BITS = AUTH_CONFIRM_CYCLES < 2 ? 1 :
                                           $clog2(AUTH_CONFIRM_CYCLES + 1);
    localparam integer AUTH_WINDOW_BITS = AUTH_WINDOW_CYCLES < 2 ? 1 :
                                          $clog2(AUTH_WINDOW_CYCLES + 1);
    reg [7:0] sync1, sync2, stable, stable_last;
    reg [DB_BITS-1:0] db_count [0:7];
    reg [HOLD_BITS-1:0] hold_count;
    reg [HOLD_BITS-1:0] song_hold_count;
    reg song_long_fired;
    reg [AUTH_CONFIRM_BITS-1:0] auth_confirm_count;
    reg [AUTH_WINDOW_BITS-1:0] auth_window_count;
    reg [IDLE_BITS-1:0] depth_idle_count;
    reg long_fired, multi_button_seen;
    integer i;

    wire [7:0] contacts_n = {enc_key_n, enc_s2_n, enc_s1_n,
                            play_pause_n, song_back_n, timbre_n,
                            bank_up_n, bank_down_n};
    wire btn_dn_release = !stable_last[0] && stable[0];
    wire btn_up_release = !stable_last[1] && stable[1];
    wire btn_timbre_release = !stable_last[2] && stable[2];
    wire btn_song_release = !stable_last[3] && stable[3];
    wire btn_play_release = !stable_last[4] && stable[4];
    wire only_one_button = stable[4:0] == 5'b11111;
    wire [4:0] buttons_down = ~stable[4:0];
    wire multiple_buttons = |(buttons_down & (buttons_down - 5'd1));
    wire enc_step = stable_last[5] && !stable[5];
    wire enc_press = stable_last[7] && !stable[7];
    wire enc_release = !stable_last[7] && stable[7];
    wire song_press = stable_last[3] && !stable[3];

    assign guide_led_on = ui_state == GUIDE_RUN;
    assign guide_led_blink = ui_state == GUIDE_PAUSE;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync1 <= 8'hff;
            sync2 <= 8'hff;
            stable <= 8'hff;
            stable_last <= 8'hff;
            bank <= 3'd0;
            timbre_select <= 1'b1;
            ui_state <= PLAY;
            song_index <= 8'd0;
            song_selected <= 1'b0;
            volume_level <= 5'd6;
            vibrato_enabled <= 1'b0;
            vibrato_depth <= 4'd4;
            depth_edit <= 1'b0;
            auth_pending <= 1'b0;
            remote_write_allowed <= 1'b0;
            auth_confirm_count <= 0;
            auth_window_count <= 0;
            song_hold_count <= 0;
            song_long_fired <= 1'b0;
            depth_idle_count <= {IDLE_BITS{1'b0}};
            hold_count <= {HOLD_BITS{1'b0}};
            long_fired <= 1'b0;
            multi_button_seen <= 1'b0;
            for (i = 0; i < 8; i = i + 1)
                db_count[i] <= {DB_BITS{1'b0}};
        end else begin
            sync1 <= contacts_n;
            sync2 <= sync1;
            stable_last <= stable;
            for (i = 0; i < 8; i = i + 1) begin
                if (sync2[i] == stable[i])
                    db_count[i] <= {DB_BITS{1'b0}};
                else if (db_count[i] == DEBOUNCE_CYCLES - 1) begin
                    stable[i] <= sync2[i];
                    db_count[i] <= {DB_BITS{1'b0}};
                end else
                    db_count[i] <= db_count[i] + 1'b1;
            end

            if (multiple_buttons)
                multi_button_seen <= 1'b1;
            else if (only_one_button)
                multi_button_seen <= 1'b0;

            // Explicit local consent: from the song list, hold K4 to open
            // the OLED prompt; release K4 and press K5 to grant this BLE session.
            // A long K4 is never also interpreted as the short Back action.
            if (REMOTE_CONTROL && PANEL_AUTH_REQUIRED) begin
                if (auth_pending) begin
                    if (auth_confirm_count == 1) begin
                        auth_pending <= 0;
                        auth_confirm_count <= 0;
                    end else
                        auth_confirm_count <= auth_confirm_count - 1'b1;
                end
                if (remote_write_allowed) begin
                    if (remote_valid && remote_type == 8'h19)
                        auth_window_count <= AUTH_WINDOW_CYCLES;
                    else if (auth_window_count == 1) begin
                        remote_write_allowed <= 0;
                        auth_window_count <= 0;
                    end else
                        auth_window_count <= auth_window_count - 1'b1;
                end
                if (song_press) begin
                    song_hold_count <= 0;
                    song_long_fired <= 0;
                end else if (!stable[3] && ui_state == SONG_LIST &&
                             !song_long_fired && !auth_pending &&
                             !multiple_buttons) begin
                    if (song_hold_count == LONG_PRESS_CYCLES - 1) begin
                        auth_pending <= 1;
                        auth_confirm_count <= AUTH_CONFIRM_CYCLES;
                        song_long_fired <= 1;
                    end else
                        song_hold_count <= song_hold_count + 1'b1;
                end
            end
            if (only_one_button && !multi_button_seen) begin
                if (auth_pending && btn_song_release && !song_long_fired) begin
                    auth_pending <= 0;
                    auth_confirm_count <= 0;
                end else if (auth_pending && btn_play_release) begin
                    auth_pending <= 0;
                    auth_confirm_count <= 0;
                    remote_write_allowed <= 1;
                    auth_window_count <= AUTH_WINDOW_CYCLES;
                end else if (auth_pending) begin
                    // No normal panel action while confirmation is visible.
                end else if (btn_dn_release) begin
                    if (ui_state == SONG_LIST) begin
                        if (song_index == 0)
                            song_index <= NUM_SONGS - 1;
                        else
                            song_index <= song_index - 1'b1;
                    end else if (ui_state == PLAY && bank != 0)
                        bank <= bank - 1'b1;
                end else if (btn_up_release) begin
                    if (ui_state == SONG_LIST) begin
                        if (song_index == NUM_SONGS - 1)
                            song_index <= 8'd0;
                        else
                            song_index <= song_index + 1'b1;
                    end else if (ui_state == PLAY && bank != 3'd4)
                        bank <= bank + 1'b1;
                end else if (btn_timbre_release)
                    timbre_select <= ~timbre_select;
                else if (btn_song_release && !song_long_fired) begin
                    if (ui_state == PLAY)
                        ui_state <= SONG_LIST;
                    else
                        ui_state <= PLAY;
                end else if (btn_play_release) begin
                    if (ui_state == GUIDE_RUN)
                        ui_state <= GUIDE_PAUSE;
                    else if (ui_state == GUIDE_PAUSE || ui_state == SONG_LIST)
                        ui_state <= GUIDE_RUN;
                    else if (song_selected)
                        ui_state <= GUIDE_RUN;
                    else
                        ui_state <= SONG_LIST;
                    if (ui_state == SONG_LIST && NUM_SONGS > 0)
                        song_selected <= 1'b1;
                end
            end

            // Rotation is always master volume except inside the visible
            // short-lived depth-edit overlay. No auto-repeat on a held contact.
            if (enc_step) begin
                depth_idle_count <= {IDLE_BITS{1'b0}};
                if (depth_edit) begin
                    if (stable[6] && vibrato_depth != 4'd15)
                        vibrato_depth <= vibrato_depth + 1'b1;
                    else if (!stable[6] && vibrato_depth != 4'd0)
                        vibrato_depth <= vibrato_depth - 1'b1;
                end else begin
                    if (stable[6] && volume_level != 5'd31)
                        volume_level <= volume_level + 1'b1;
                    else if (!stable[6] && volume_level != 5'd0)
                        volume_level <= volume_level - 1'b1;
                end
            end else if (depth_edit) begin
                if (depth_idle_count == DEPTH_EDIT_TIMEOUT_CYCLES - 1) begin
                    depth_edit <= 1'b0;
                    depth_idle_count <= {IDLE_BITS{1'b0}};
                end else
                    depth_idle_count <= depth_idle_count + 1'b1;
            end else
                depth_idle_count <= {IDLE_BITS{1'b0}};

            if (enc_press) begin
                hold_count <= {HOLD_BITS{1'b0}};
                long_fired <= 1'b0;
            end else if (!stable[7] && !long_fired) begin
                if (hold_count == LONG_PRESS_CYCLES - 1) begin
                    depth_edit <= ~depth_edit;
                    depth_idle_count <= {IDLE_BITS{1'b0}};
                    long_fired <= 1'b1;
                end else
                    hold_count <= hold_count + 1'b1;
            end
            if (enc_release && !long_fired) begin
                if (depth_edit)
                    depth_edit <= 1'b0;
                else
                    vibrato_enabled <= ~vibrato_enabled;
            end

            // Accepted SET commands are absolute/idempotent, not simulated
            // button taps. When both arrive on one clock the remote value wins.
            if (REMOTE_CONTROL && remote_valid) begin
                case (remote_type)
                    8'h10: if (remote_value <= 31)
                        volume_level <= remote_value[4:0];
                    8'h11: if (remote_value <= 4)
                        bank <= remote_value[2:0];
                    8'h12: if (remote_value <= 1)
                        timbre_select <= remote_value[0];
                    8'h13: if (remote_value <= 1)
                        vibrato_enabled <= remote_value[0];
                    8'h1a: if (remote_value <= 15)
                        vibrato_depth <= remote_value[3:0];
                    8'h1f: begin // all scene fields arrive in one accepted frame
                        bank <= remote_payload[2:0];
                        timbre_select <= remote_payload[8];
                        volume_level <= remote_payload[20:16];
                        vibrato_enabled <= remote_payload[24];
                        vibrato_depth <= remote_payload[35:32];
                    end
                    8'h14: if (remote_value < NUM_SONGS) begin
                        song_index <= remote_value;
                        song_selected <= 1;
                        ui_state <= SONG_LIST;
                    end
                    8'h15: case (remote_value)
                        0: ui_state <= PLAY;
                        1: begin ui_state <= GUIDE_RUN; song_selected <= 1; end
                        2: if (ui_state == GUIDE_RUN) ui_state <= GUIDE_PAUSE;
                        3: if (ui_state == GUIDE_PAUSE) ui_state <= GUIDE_RUN;
                        default: ;
                    endcase
                    default: ;
                endcase
            end
        end
    end
endmodule
