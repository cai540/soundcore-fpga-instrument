// UI and offline song-guidance chain. Its outputs are status signals for a
// future audio-control/OLED integration; this module does not alter sound.
module front_panel_guide_bridge #(
    parameter integer DEBOUNCE_CYCLES = 245760,
    parameter integer LONG_PRESS_CYCLES = 8601600,
    parameter integer DEPTH_EDIT_TIMEOUT_CYCLES = 61440000,
    parameter integer AUTH_CONFIRM_CYCLES = 122880000,
    parameter integer AUTH_WINDOW_CYCLES = 36864000,
    parameter integer BLINK_HALF_CYCLES = 3072000,
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
    input wire strike_valid,
    input wire [2:0] strike_channel,
    output wire [2:0] bank,
    output wire timbre_select,
    output wire [1:0] ui_state,
    output wire [7:0] song_index,
    output wire song_selected,
    output wire [4:0] volume_level,
    output wire vibrato_enabled,
    output wire [3:0] vibrato_depth,
    output wire depth_edit,
    output wire auth_pending,
    output wire remote_write_allowed,
    output wire [3:0] guide_step,
    output wire [3:0] guide_length,
    output wire [2:0] guide_target_pad,
    output wire guide_complete,
    output wire guide_correct_pulse,
    output wire guide_wrong_pulse,
    output wire [6:0] guide_target_led,
    output wire guide_button_led
);
    wire guide_led_on, guide_led_blink;
    front_panel_five_keys #(
        .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES),
        .LONG_PRESS_CYCLES(LONG_PRESS_CYCLES),
        .DEPTH_EDIT_TIMEOUT_CYCLES(DEPTH_EDIT_TIMEOUT_CYCLES),
        .AUTH_CONFIRM_CYCLES(AUTH_CONFIRM_CYCLES),
        .AUTH_WINDOW_CYCLES(AUTH_WINDOW_CYCLES),
        .REMOTE_CONTROL(REMOTE_CONTROL),
        .PANEL_AUTH_REQUIRED(PANEL_AUTH_REQUIRED)
    ) panel (
        .clk(clk), .rst_n(rst_n),
        .bank_down_n(bank_down_n), .bank_up_n(bank_up_n),
        .timbre_n(timbre_n), .song_back_n(song_back_n),
        .play_pause_n(play_pause_n),
        .enc_s1_n(enc_s1_n), .enc_s2_n(enc_s2_n),
        .enc_key_n(enc_key_n),
        .remote_valid(remote_valid),
        .remote_type(remote_type),
        .remote_value(remote_value),
        .remote_payload(remote_payload),
        .bank(bank), .timbre_select(timbre_select),
        .ui_state(ui_state), .song_index(song_index),
        .song_selected(song_selected), .volume_level(volume_level),
        .vibrato_enabled(vibrato_enabled),
        .vibrato_depth(vibrato_depth), .depth_edit(depth_edit),
        .auth_pending(auth_pending),
        .remote_write_allowed(remote_write_allowed),
        .guide_led_on(guide_led_on),
        .guide_led_blink(guide_led_blink)
    );
    song_guide_rom guide (
        .clk(clk), .rst_n(rst_n), .ui_state(ui_state),
        .song_index(song_index), .strike_valid(strike_valid),
        .strike_channel(strike_channel), .step_index(guide_step),
        .target_pad(guide_target_pad), .song_length(guide_length),
        .completed(guide_complete),
        .correct_pulse(guide_correct_pulse),
        .wrong_pulse(guide_wrong_pulse),
        .target_led(guide_target_led)
    );

    localparam integer BLINK_BITS = BLINK_HALF_CYCLES < 2 ? 1 :
                                    $clog2(BLINK_HALF_CYCLES);
    reg [BLINK_BITS-1:0] blink_count;
    reg blink_phase;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            blink_count <= {BLINK_BITS{1'b0}};
            blink_phase <= 1'b0;
        end else if (blink_count == BLINK_HALF_CYCLES - 1) begin
            blink_count <= {BLINK_BITS{1'b0}};
            blink_phase <= ~blink_phase;
        end else
            blink_count <= blink_count + 1'b1;
    end
    assign guide_button_led = guide_led_on ||
                              (guide_led_blink && blink_phase);
endmodule
