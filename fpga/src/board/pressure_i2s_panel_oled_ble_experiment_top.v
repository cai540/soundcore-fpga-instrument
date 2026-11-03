// OLED/JDY-23 experiment top. The current build has passed timing and SRAM
// download; musical accuracy and the latest phone/OLED behavior await hearing
// and visual checks before any Flash update.
`include "@FPGA_ROOT@/src/assets/76e8ed11_product_song_catalog.vh"
module pressure_i2s_panel_oled_ble_experiment_top #(
    parameter integer HEADPHONE_OUTPUT = 0,
    parameter integer HEADPHONE_SHIFT = 2,
    parameter integer EARLY_FORCE_ENABLE = 0,
    parameter integer CONTINUOUS_EXPRESSION = 0,
    parameter integer UPLOADED_SCORE_ENABLE = 0,
    parameter integer HANDPAN_ENABLE = 0,
    parameter integer PRODUCT_TOOLS = 0
) (
    input wire sys_clk,
    input wire rst_n,
    output wire adc_cs_n,
    output wire adc_sclk,
    output wire adc_mosi,
    input wire adc_miso,
    input wire enc_s1_n,
    input wire enc_s2_n,
    input wire enc_key_n,
    input wire panel_bank_down_n,
    input wire panel_bank_up_n,
    input wire panel_timbre_n,
    input wire panel_song_back_n,
    input wire panel_play_pause_n,
    input wire ble_uart_rx,
    output wire ble_uart_tx,
    inout wire oled_scl,
    inout wire oled_sda,
    output wire dac_bclk,
    output wire dac_lrclk,
    output wire dac_din,
    output wire [6:0] pad_led_o,
    output wire guide_button_led_o
);
    wire clk_audio,pll_locked;
    wire run_n=rst_n && pll_locked;
    wire strike_event;
    wire [2:0] strike_channel;
    wire [6:0] performance_led,guide_target_led,guide_rhythm_led;
    wire [15:0] guide_target_duration;
    wire [10:0] guide_length,guide_step;
    wire [7:0] song_index,menu_song_index;
    wire demo_mode,mode_menu,mode_cursor,local_player_valid,guide_restart;
    wire [7:0] local_player_value,player_command_value;
    wire player_command_valid;
    wire [2:0] ui_bank,guide_target,guide_target_bank,guide_bank;
    wire [1:0] ui_state;
    wire song_selected,vibrato_enabled,depth_edit;
    wire [1:0] timbre_select;
    wire manual_handpan;
    wire [4:0] volume_level;
    wire [3:0] vibrato_depth;
    wire guide_complete,guide_correct,guide_wrong;
    wire oled_ready,oled_nack;
    wire uart_rx_valid,uart_tx_ready,uart_tx_valid;
    wire tools_request_valid,tools_response_valid;
    wire tools_response_bulk;wire[6:0] tools_bulk_index;wire[7:0] tools_bulk_byte;
    wire[7:0] tools_request_type,tools_request_length;
    wire[111:0] tools_request_payload,tools_response_payload;
    wire tool_diag_enabled,tool_map_enabled,tool_clear;
    wire[31:0] tool_diag_gate;wire[223:0] tool_diag_notes;wire[48:0] tool_pad_map;
    wire[1:0] tool_view_mode;wire[5:0] actual_active_voices;wire synth_deadline_fault;
    wire[8:0] synth_max_cycles;wire signed[15:0] final_pcm;wire final_pcm_tick;
    wire[511:0] analysis_wave;wire[255:0] analysis_spectrum;
    wire analysis_phase_bank,shown_analysis_bank,analysis_frame_latch;
    wire analysis_valid;
    wire[9:0] analysis_phase_address;wire[7:0] analysis_phase_pixels;
    wire [7:0] uart_rx_byte,uart_tx_byte;
    wire remote_valid;
    wire ble_link_activity;
    wire auth_pending,panel_write_allowed;
    wire remote_write_allowed;
    reg [26:0] ble_link_left;
    wire ble_link_active = ble_link_left != 0;
    // JDY-23 STAT is not wired. A CRC-checked request establishes the
    // connection session; continued App polling keeps it alive.
    assign remote_write_allowed = ble_link_active || ble_link_activity;
    always @(posedge clk_audio or negedge run_n) begin
        if (!run_n) ble_link_left <= 0;
        else if (ble_link_activity) ble_link_left <= 27'd73728000;
        else if (ble_link_left != 0) ble_link_left <= ble_link_left-1'b1;
    end
    wire [7:0] remote_type,remote_value,remote_value2;
    generate if(PRODUCT_TOOLS!=0)begin: product_lab
        product_tools_subsystem tools(.clk(clk_audio),.rst_n(run_n),.link_active(remote_write_allowed),
          .interrupt(!panel_song_back_n || !panel_play_pause_n ||
             (remote_valid && (remote_type==8'h14 || remote_type==8'h15 || remote_type==8'h23 || remote_type==8'h34))),
          .request_valid(tools_request_valid),.request_type(tools_request_type),.request_length(tools_request_length),
          .request_payload(tools_request_payload),.response_valid(tools_response_valid),.response_payload(tools_response_payload),
          .response_bulk(tools_response_bulk),.bulk_index(tools_bulk_index),.bulk_byte(tools_bulk_byte),
          .sample_tick(final_pcm_tick),.sample_in(final_pcm),.active_voices(actual_active_voices),.deadline_fault(synth_deadline_fault),
          .diag_enabled(tool_diag_enabled),.diag_gate(tool_diag_gate),.diag_notes(tool_diag_notes),
          .view_mode(tool_view_mode),.map_enabled(tool_map_enabled),.pad_map(tool_pad_map),.clear_voices(tool_clear),
          .oled_frame_latch(analysis_frame_latch),.oled_ready(oled_ready),.display_phase_bank(shown_analysis_bank),
          .phase_address(analysis_phase_address),.phase_bank(analysis_phase_bank),.phase_pixels(analysis_phase_pixels),
          .wave_data(analysis_wave),.spectrum_data(analysis_spectrum),.frame_pending(analysis_valid));
    end else begin:no_product_lab
        assign tools_response_valid=0;assign tools_response_payload=0;assign tool_diag_enabled=0;
        assign tools_response_bulk=0;assign tools_bulk_byte=0;assign analysis_valid=0;
        assign tool_diag_gate=0;assign tool_diag_notes=0;assign tool_view_mode=0;
        assign tool_map_enabled=0;assign tool_pad_map=0;assign tool_clear=0;
        assign analysis_wave=0;assign analysis_spectrum=0;assign analysis_phase_bank=0;assign analysis_phase_pixels=0;
    end endgenerate
    wire [111:0] remote_payload;
    reg [3:0] manual_key;
    wire [3:0] score_key;
    wire [3:0] builtin_key=song_index[0] ? 4'd2 : 4'd5;
    wire native_guidance_active=!demo_mode && !guide_complete && (ui_state==2 || ui_state==3);
    wire [3:0] effective_key=score_engaged && !score_finished ? score_key :
        (autoplay_active || native_guidance_active) ? builtin_key : manual_key;
    wire [63:0] telemetry;
    wire [55:0] physical_force_levels;
    wire [6:0] pad_pressed;
    wire [7:0] current_bend;
    reg [1:0] led_mode;
    reg native_guide_last;
    reg [1:0] led_before_guide;
    reg [2:0] effect_mask;
    reg [7:0] oled_contrast;
    always @(posedge clk_audio or negedge run_n) begin
        if (!run_n) begin
            led_mode <= 0;
            native_guide_last<=0;led_before_guide<=0;
            manual_key<=0;
            effect_mask <= 0;
            oled_contrast <= 8'h7f;
        end else begin
            native_guide_last<=native_guidance_active;
            if(native_guidance_active && !native_guide_last)begin
                led_before_guide<=led_mode;led_mode<=1;
            end else if(!native_guidance_active && native_guide_last)led_mode<=led_before_guide;
            // A deliberate App change during guidance still takes priority.
            if (remote_valid) begin
            if (remote_type == 8'h27 && remote_value<12)manual_key<=remote_value[3:0];
            if (remote_type == 8'h1d) led_mode <= remote_value[1:0];
            if (remote_type == 8'h22) effect_mask <= remote_value[2:0];
            if (remote_type == 8'h1e) oled_contrast <= remote_value;
            if (remote_type == 8'h1f) begin
                led_mode <= remote_payload[41:40];
                oled_contrast <= remote_payload[55:48];
            end
            end
        end
    end
    wire [6:0] remote_pressed;
    wire [2:0] remote_pending_channel;
    wire [7:0] remote_pending_velocity;
    wire remote_voice_ready;
    wire remote_fire;
    wire remote_absolute;
    wire [6:0] remote_note,guide_note_exact;
    wire [48:0] remote_notes_exact;
    wire [6:0] native_guide_note;
    wire guide_override=score_guiding ? !score_paused && !score_finished && score_pad<7 :
        !demo_mode && ui_state==2 && !guide_complete && guide_target<7;
    assign guide_note_exact=score_guiding ? score_note : native_guide_note;
    wire [2:0] exact_guide_pad=score_guiding ? score_pad : guide_target;
    wire judge_remote=remote_fire && (!remote_absolute || guide_override && remote_note==guide_note_exact);
    wire [2:0] judge_pad=remote_fire ? (remote_absolute ? exact_guide_pad : remote_pending_channel) : strike_channel;
    wire [6:0] remote_visual_mask;
    wire [2:0] remote_visual_pad[0:6];
    genvar remote_i;
    generate for(remote_i=0;remote_i<7;remote_i=remote_i+1)begin: phone_projection
        pitch_projection project(.note_index(remote_notes_exact[remote_i*7 +: 7]),.key(effective_key),
            .bank(),.pad(remote_visual_pad[remote_i]),.sharp(),.valid());
    end endgenerate
    reg [6:0] remote_mask_comb;
    integer remote_p;
    always @* begin
        remote_mask_comb=0;
        for(remote_p=0;remote_p<7;remote_p=remote_p+1)
            if(remote_pressed[remote_p])remote_mask_comb[remote_absolute ? remote_visual_pad[remote_p] : remote_p]=1;
    end
    assign remote_visual_mask=remote_mask_comb;
    wire score_request_valid,score_response_valid;
    wire [7:0] score_request_type,score_request_seq,score_request_length;
    wire [111:0] score_request_payload,score_response_payload;
    wire score_playing,score_paused,score_guiding,score_finished,score_timbre,score_ready,score_start;
    wire [9:0] score_step;
    wire [2:0] score_bank,score_pad;
    wire [6:0] score_note;
    wire score_gate;
    wire [6:0] score_guide_led;
    wire score_engaged=score_playing || score_guiding;
    wire capture_display_valid,score_receiving;
    wire [87:0] capture_display_payload,capture_oled_payload;
    wire [9:0] score_count,score_received,score_expected;
    capture_display_state capture_ui(
        .clk(clk_audio),.rst_n(run_n),.link_active(ble_link_active),
        .summary_valid(capture_display_valid),.summary_payload(capture_display_payload),
        .score_receiving(score_receiving),.score_playing(score_playing),.score_guiding(score_guiding),
        .score_paused(score_paused),.score_finished(score_finished),.score_step(score_step),.score_count(score_count),
        .score_received(score_received),.score_expected(score_expected),.score_bank(score_bank),.score_pad(score_pad),
        .display_payload(capture_oled_payload));
    generate if(UPLOADED_SCORE_ENABLE!=0)begin:runtime_score
        uploaded_song_engine engine(
            .clk(clk_audio),.rst_n(run_n),.link_active(ble_link_active),
            .request_valid(score_request_valid),.request_type(score_request_type),
            .request_seq(score_request_seq),.request_length(score_request_length),
            .request_payload(score_request_payload),.response_valid(score_response_valid),
            .response_payload(score_response_payload),
            .stop_external((remote_valid && (remote_type==8'h14 || remote_type==8'h15 || remote_type==8'h23)) ||
                !panel_song_back_n || !panel_play_pause_n),
            .strike_valid(strike_event | judge_remote),
            .strike_pad(judge_pad),
            .playing(score_playing),.paused(score_paused),.guiding(score_guiding),.finished(score_finished),
            .key(score_key),.step(score_step),.bank(score_bank),.pad(score_pad),.note(score_note),.gate(score_gate),
            .timbre(score_timbre),.ready(score_ready),.guide_led(score_guide_led),.start_pulse(score_start),
            .display_receiving(score_receiving),.display_count(score_count),.display_received(score_received),.display_expected(score_expected));
    end else begin:no_runtime_score
        assign score_response_valid=0;assign score_response_payload=0;
        assign score_playing=0;assign score_paused=0;assign score_guiding=0;assign score_finished=0;
        assign score_timbre=0;assign score_ready=0;assign score_start=0;assign score_step=0;
        assign score_key=0;assign score_bank=0;assign score_pad=7;assign score_note=0;assign score_gate=0;assign score_guide_led=0;
        assign score_receiving=0;assign score_count=0;assign score_received=0;assign score_expected=0;
    end endgenerate
    wire autoplay_active,autoplay_paused,autoplay_restart,autoplay_finished;
    wire [1:0] playback_state;
    wire [10:0] autoplay_index,autoplay_length;
    wire [2:0] autoplay_bank,autoplay_pad;
    wire [6:0] autoplay_note;
    wire autoplay_gate;
    wire [17:0] autoplay_ms;
    song_transport_router transport_router(
        .local_valid(local_player_valid),.local_value(local_player_value),
        .remote_valid(remote_valid),.remote_type(remote_type),.remote_value(remote_value),
        .score_start(score_start),.command_valid(player_command_valid),.command_value(player_command_value));
    song_autoplay_control autoplay_control (
        .clk(clk_audio),.rst_n(run_n),.command_valid(player_command_valid),
        .command_type(8'h23),.command_value(player_command_value),
        .song_index(song_index),.player_finished(autoplay_finished),
        .active(autoplay_active),.paused(autoplay_paused),
        .restart_pulse(autoplay_restart),.playback_state(playback_state)
    );
    song_event_player #(.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .TEMPO0_NUM(1),.TEMPO1_NUM(1),.TEMPO_DEN(1),
        .ARTICULATION_GAP_MS(2),
        .ARTICULATION0_GAP_MS(12),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) offline_player (
        .clk(clk_audio),.rst_n(run_n),.run(autoplay_active),
        .pause(autoplay_paused),.restart(autoplay_restart),
        .song_select(song_index[0]),.key(builtin_key),.event_index(autoplay_index),
        .song_length(autoplay_length),.event_bank(autoplay_bank),
        .event_pad(autoplay_pad),.note_index(autoplay_note),
        .note_gate(autoplay_gate),.finished(autoplay_finished),.playback_ms(autoplay_ms)
    );
    wire [6:0] lyric_phrase;
    wire [4:0] lyric_character;
    wire [7:0] lyric_progress;
    wire lyric_mode=!score_engaged && (autoplay_active || ui_state==2 || ui_state==3);
    song_lyric_position #(.WORD_COUNT0(`PRODUCT_SONG0_WORDS),.WORD_COUNT1(`PRODUCT_SONG1_WORDS),
        .EVENT_COUNT0(`PRODUCT_SONG0_EVENTS),.EVENT_COUNT1(`PRODUCT_SONG1_EVENTS)) lyric_position(
        .clk(clk_audio),.rst_n(run_n),.song(song_index[0]),.autoplay(autoplay_active),
        .playback_ms(autoplay_ms),.autoplay_event(autoplay_index),.guide_event(guide_step),
        .phrase(lyric_phrase),.character(lyric_character),.progress(lyric_progress));
    remote_note_bridge #(.REALTIME_ENABLED(1)) remote_notes (
        .clk(clk_audio),.rst_n(run_n),
        .write_allowed(remote_write_allowed),
        .command_valid(remote_valid),.command_type(remote_type),
        .command_value(remote_value),.command_value2(remote_value2),
        .command_payload(remote_payload),
        .physical_strike(strike_event),.voice_ready(remote_voice_ready),
        .remote_pressed(remote_pressed),.remote_strike_valid(remote_fire),
        .remote_strike_channel(remote_pending_channel),
        .remote_strike_velocity(remote_pending_velocity),.remote_absolute(remote_absolute),
        .remote_strike_note(remote_note),.remote_notes(remote_notes_exact)
    );

    audio_pll_12m288 pll (
        .clkin(sys_clk),.clk_audio(clk_audio),.locked(pll_locked)
    );
    pressure_i2s_additive32_core #(
        .BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),.REMOTE_ENABLE(1),.PRODUCT_TOOLS(PRODUCT_TOOLS),
        .EFFECTS_AVAILABLE(1),.OFFLINE_PLAYER(1),
        .HEADPHONE_OUTPUT(HEADPHONE_OUTPUT),.HEADPHONE_SHIFT(HEADPHONE_SHIFT),
        .EARLY_FORCE_ENABLE(EARLY_FORCE_ENABLE),.CONTINUOUS_EXPRESSION(CONTINUOUS_EXPRESSION),
        .HANDPAN_AVAILABLE(HANDPAN_ENABLE)
    ) audio_core (
        .clk_audio(clk_audio),.rst_n(run_n),
        .adc_cs_n(adc_cs_n),.adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi),.adc_miso(adc_miso),
        .enc_s1_n(enc_s1_n),.enc_s2_n(enc_s2_n),
        .enc_key_n(enc_key_n),.key_up_n(1'b1),.key_down_n(1'b1),
        .panel_bank(guide_bank),.panel_key(effective_key),
        .guide_override(guide_override),.guide_pad(exact_guide_pad),.guide_note(guide_note_exact),
        .remote_absolute(remote_absolute),.remote_note(remote_note),
        .panel_timbre(score_guiding && !score_finished ? score_timbre :
            native_guidance_active ? ~song_index[0] : timbre_select[0]),
        .panel_handpan_style(manual_handpan ? (timbre_select==3 ? 2'd2:2'd1):2'd0),
        .panel_vibrato_enabled(vibrato_enabled),
        .panel_vibrato_depth(vibrato_depth),
        .panel_volume_level(volume_level),
        .panel_effect_mask(effect_mask),
        .remote_command_valid(remote_valid),
        .remote_command_type(remote_type),
        .remote_command_value(remote_value),
        .remote_session_active(remote_write_allowed),
        .remote_strike_valid(remote_fire),
        .remote_strike_channel(remote_pending_channel),
        .remote_strike_velocity(remote_pending_velocity),
        .remote_pressed(remote_pressed),
        .autoplay_note_gate(score_playing ? score_gate : autoplay_gate),
        .autoplay_note_index(score_playing ? score_note : autoplay_note),
        .autoplay_timbre(score_playing ? score_timbre : ~song_index[0]),
        .remote_voice_ready(remote_voice_ready),
        .dac_bclk(dac_bclk),.dac_lrclk(dac_lrclk),.dac_din(dac_din),
        .pad_led_on(performance_led),.strike_event(strike_event),
        .strike_channel_o(strike_channel),
        .pad_pressed_o(pad_pressed),.telemetry_o(telemetry),
        .force_visual_o(physical_force_levels),
        .bend_o(current_bend),.tool_diag_enabled(tool_diag_enabled),.tool_diag_gate(tool_diag_gate),
        .tool_diag_notes(tool_diag_notes),.tool_map_enabled(tool_map_enabled),.tool_pad_map(tool_pad_map),.tool_clear(tool_clear),
        .output_pcm(final_pcm),.output_pcm_tick(final_pcm_tick),.synth_active_voices(actual_active_voices),
        .synth_deadline_fault(synth_deadline_fault),.synth_max_cycles(synth_max_cycles)
    );
    front_panel_product #(.HANDPAN_ENABLE(HANDPAN_ENABLE)) panel_guide (
        .clk(clk_audio),.rst_n(run_n),
        .bank_down_n(panel_bank_down_n),.bank_up_n(panel_bank_up_n),
        .timbre_n(panel_timbre_n),.song_back_n(panel_song_back_n),.play_pause_n(panel_play_pause_n),
        .enc_s1_n(enc_s1_n),.enc_s2_n(enc_s2_n),.enc_key_n(enc_key_n),
        .remote_valid(remote_valid || score_start),.remote_type(score_start ? 8'h15 : remote_type),
        .remote_value(score_start ? 8'd0 : remote_value),.remote_payload(remote_payload[55:0]),
        .player_finished(autoplay_finished),.guide_finished(guide_complete),.bank(ui_bank),.timbre_select(timbre_select),
        .ui_state(ui_state),.song_index(song_index),.menu_song_index(menu_song_index),
        .song_selected(song_selected),.demo_mode(demo_mode),.mode_menu(mode_menu),.mode_cursor(mode_cursor),
        .volume_level(volume_level),.vibrato_enabled(vibrato_enabled),.vibrato_depth(vibrato_depth),
        .depth_edit(depth_edit),.auth_pending(auth_pending),.remote_write_allowed(panel_write_allowed),
        .guide_button_led(guide_button_led_o),.player_command_valid(local_player_valid),
        .player_command(local_player_value),.guide_restart(guide_restart)
    );
    song_guide_long #(.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) long_guide (
        .clk(clk_audio),.rst_n(run_n),.restart(guide_restart),.ui_state(demo_mode ? 2'd0 : ui_state),
        .song_select(song_index[0]),.key(builtin_key),.target_note(native_guide_note),
        .strike_valid(strike_event | judge_remote),
        .strike_bank(guide_bank),
        .strike_pad(judge_pad),
        .step_index(guide_step),.song_length(guide_length),
        .target_bank(guide_target_bank),.target_pad(guide_target),
        .target_duration_ms(guide_target_duration),.completed(guide_complete),
        .correct_pulse(guide_correct),.wrong_pulse(guide_wrong),
        .target_led(guide_target_led)
    );
    guide_rhythm_cue rhythm_hint(.clk(clk_audio),.rst_n(run_n),
        .active(native_guidance_active),.paused(ui_state==3),.correct(guide_correct),
        .step_index(guide_step),.target_duration_ms(guide_target_duration),
        .target_led(guide_target_led),.led(guide_rhythm_led));
    // During guided play each target selects its own pitch bank. A physical
    // pad or a phone pad only needs to supply the seven-key pad index.
    assign guide_bank = score_guiding && !score_finished ? score_bank : !demo_mode && (ui_state == 2'd2 || ui_state == 2'd3) && !guide_complete ?
                        guide_target_bank : ui_bank;
    wire [6:0] autoplay_led = score_playing ? (score_gate ? (7'b1<<score_pad) : 7'd0) : autoplay_active && !autoplay_paused &&
                              !autoplay_finished && autoplay_pad < 3'd7 ?
                              (7'b1 << autoplay_pad) : 7'd0;
    wire playback_visual_active = score_playing ? !score_finished : playback_state==2'd1 || playback_state==2'd2;
    // Match the displayed instrument after natural song completion as well as Stop.
    assign manual_handpan=HANDPAN_ENABLE && timbre_select[1] && !(score_engaged && !score_finished) &&
        !playback_visual_active && !native_guidance_active;
    reg [2:0] last_play_bank;
    always @(posedge clk_audio or negedge run_n) begin
        if (!run_n) last_play_bank <= 3'd0;
        else if (score_playing ? score_gate : autoplay_gate) last_play_bank <= score_playing ? score_bank : autoplay_bank;
    end
    // Rest events have no pitch bank; keep the previous note's display bank.
    wire [2:0] visual_bank = playback_visual_active ?
        (score_playing ? (score_gate ? score_bank : last_play_bank) : (autoplay_gate ? autoplay_bank : last_play_bank)) : guide_bank;
    wire [1:0] visual_timbre = score_engaged && !score_finished ? {1'b0,score_timbre} :
        playback_visual_active || native_guidance_active ? {1'b0,~song_index[0]} : timbre_select;
    wire [6:0] visual_pad_mask = pad_pressed | remote_visual_mask | autoplay_led;
    wire [55:0] visual_force_levels;
    genvar visual_i;
    generate for (visual_i=0; visual_i<7; visual_i=visual_i+1) begin: visual_meter
        assign visual_force_levels[visual_i*8 +: 8] = playback_visual_active ?
            (((score_playing ? score_gate : autoplay_gate) &&
                (score_playing ? score_pad : autoplay_pad)==visual_i) ? 8'd224 : 8'd0) :
            physical_force_levels[visual_i*8 +: 8];
    end endgenerate
    wire [10:0] displayed_song_step = score_engaged ? {1'b0,score_step} : autoplay_active ? autoplay_index : guide_step;
    wire [2:0] displayed_target_pad = score_engaged ? score_pad : autoplay_active ?
        (autoplay_finished || autoplay_pad == 3'd7 ? 3'd0 : autoplay_pad) :
        (guide_target == 3'd7 ? 3'd0 : guide_target);
    wire [2:0] displayed_target_bank = score_engaged ? score_bank : autoplay_active ?
        (autoplay_finished ? 3'd0 : autoplay_bank) : guide_target_bank;
    led_mode_controller led_modes (
        .clk(clk_audio),.rst_n(run_n),.mode(led_mode),
        .guide_running(score_engaged || ui_state==2'd2 || autoplay_active),
        .performance_led(performance_led | remote_visual_mask),
        .guide_led(score_engaged ? (score_playing ? autoplay_led : score_guide_led) : autoplay_active ? autoplay_led : guide_rhythm_led),
        .led_out(pad_led_o)
    );

    oled_status_ssd1315 #(.PRODUCT_TOOLS(PRODUCT_TOOLS),.LONG_SONG_UI(1),.LYRIC_OVERLAY(1),.CAPTURE_OVERLAY(UPLOADED_SCORE_ENABLE),.PANEL_MENU(1),.PRODUCT_PANEL(1)) display (
        .clk(clk_audio),.rst_n(run_n),.key(effective_key),.bank(visual_bank),
        .timbre(visual_timbre),.volume(volume_level),
        .tone_edit(depth_edit),.tone_drive(vibrato_depth),
        .vibrato(vibrato_enabled),.menu_song(menu_song_index),.menu_mode_select(mode_menu),.menu_mode_cursor(mode_cursor),.demo_mode(demo_mode),.ui_state(score_guiding && !score_finished ? (score_paused ? 2'd3 : 2'd2) : ui_state),
        .guide_step(displayed_song_step),.guide_target(displayed_target_pad),
        .guide_target_bank(displayed_target_bank),
        .playback_state(playback_state),
        .auth_pending(auth_pending),
        .remote_write_allowed(remote_write_allowed),
        .ble_frame_seen(ble_link_activity),
        .pad_active(visual_pad_mask),
        .force_levels(visual_force_levels),
        .contrast(oled_contrast),
        .lyric_mode(lyric_mode),.lyric_phrase(lyric_phrase),
        .lyric_character(lyric_character),.lyric_progress(lyric_progress),
        .capture_payload(lyric_mode ? 88'd0 : capture_oled_payload),
        .analysis_mode(tool_view_mode),.analysis_valid(analysis_valid),.analysis_wave(analysis_wave),.analysis_spectrum(analysis_spectrum),
        .analysis_phase_bank(analysis_phase_bank),.analysis_phase_pixels(analysis_phase_pixels),
        .analysis_phase_address(analysis_phase_address),.shown_analysis_bank(shown_analysis_bank),.analysis_frame_latch(analysis_frame_latch),
        .oled_scl(oled_scl),.oled_sda(oled_sda),
        .ready(oled_ready),.nack_seen(oled_nack)
    );
    uart_8n1_9600 uart (
        .clk(clk_audio),.rst_n(run_n),.rx(ble_uart_rx),
        .rx_valid(uart_rx_valid),.rx_byte(uart_rx_byte),
        .tx(ble_uart_tx),.tx_valid(uart_tx_valid),
        .tx_byte(uart_tx_byte),.tx_ready(uart_tx_ready)
    );
    ble_control_endpoint #(.PRODUCT_TOOLS(PRODUCT_TOOLS),.EXTENDED_STATE(1),.SONG_EXTENSIONS(1),.REALTIME_NOTES(1),.SCORE_UPLOAD(UPLOADED_SCORE_ENABLE),.CAPTURE_UI(UPLOADED_SCORE_ENABLE),.OMR_ENABLE(1),.HANDPAN_ENABLE(HANDPAN_ENABLE)) control_endpoint (
        .clk(clk_audio),.rst_n(run_n),
        .rx_valid(uart_rx_valid),.rx_byte(uart_rx_byte),
        .write_enable(remote_write_allowed),
        .key(effective_key),.bank(visual_bank),.timbre(visual_timbre),.volume(volume_level),
        .vibrato(vibrato_enabled),.ui_state(ui_state),
        .song_index(menu_song_index),.guide_step(displayed_song_step),
        .guide_target(displayed_target_pad),.guide_target_bank(displayed_target_bank),
        .playback_state(playback_state),
        .vibrato_depth(vibrato_depth),.bend(current_bend),
        .led_mode(led_mode),.effect_mask(effect_mask),
        .oled_contrast(oled_contrast),
        .pad_mask(visual_pad_mask),
        .telemetry({1'b0,visual_pad_mask,telemetry[63:56],visual_force_levels}),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.remote_value2(remote_value2),
        .remote_payload(remote_payload),
        .link_activity(ble_link_activity),
        .tx_valid(uart_tx_valid),
        .tx_byte(uart_tx_byte),.tx_ready(uart_tx_ready),
        .score_request_valid(score_request_valid),.score_request_type(score_request_type),
        .score_request_seq(score_request_seq),.score_request_length(score_request_length),
        .score_request_payload(score_request_payload),.score_response_valid(score_response_valid),
        .score_response_payload(score_response_payload),
        .capture_display_valid(capture_display_valid),.capture_display_payload(capture_display_payload),
        .tools_request_valid(tools_request_valid),.tools_request_type(tools_request_type),.tools_request_length(tools_request_length),
        .tools_request_payload(tools_request_payload),.tools_response_valid(tools_response_valid),.tools_response_payload(tools_response_payload),.tools_response_bulk(tools_response_bulk),.tools_bulk_index(tools_bulk_index),.tools_bulk_byte(tools_bulk_byte)
    );
endmodule
