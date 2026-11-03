// Experimental seven-pad instrument with one playable 32-component AI0 voice.
// The legacy four-voice project and its accepted Flash bitstream are separate.
module pressure_i2s_additive32_core #(
    parameter integer SCAN_HALF_CYCLES = 6,
    parameter integer SCAN_GAP_CYCLES = 12,
    parameter integer CAL_SAMPLES = 16,
    parameter integer PEAK_SAMPLES = 4,
    // Experimental early peak estimate; normal product builds keep legacy timing.
    parameter integer EARLY_FORCE_ENABLE = 0,
    parameter integer CONTINUOUS_EXPRESSION = 0,
    parameter integer HANDPAN_AVAILABLE = 0,
    parameter integer PRODUCT_TOOLS = 0,
    parameter integer REARM_SAMPLES = 32,
    parameter integer HOLD_SAMPLES = 480,
    parameter integer ENC_DEBOUNCE_CYCLES = 12288,
    parameter integer ENC_LONG_PRESS_CYCLES = 8601600,
    parameter integer VOLUME_DEBOUNCE_CYCLES = 122880,
    parameter integer DEMO_HOLD_CYCLES = 6144000,
    parameter integer LED_FLASH_CYCLES = 1228800,
    parameter integer BANKED32_AVAILABLE = 0,
    parameter integer REMOTE_ENABLE = 0,
    // New panel path is opt-in. The accepted board top leaves it at zero.
    parameter integer PANEL_CONTROL = 0,
    parameter integer EFFECTS_AVAILABLE = 0,
    parameter integer OFFLINE_PLAYER = 0,
    parameter integer PANEL_GAIN_RAMP_FRAMES = 64,
    // Opt-in board monitor only; the external MAX path remains standard I2S.
    parameter integer HEADPHONE_OUTPUT = 0,
    parameter integer HEADPHONE_SHIFT = 2,
    parameter [11:0] ON_THRESHOLD = 12'd280,
    parameter [11:0] OFF_THRESHOLD = 12'd100
) (
    input wire clk_audio,
    input wire rst_n,
    output wire adc_cs_n,
    output wire adc_sclk,
    output wire adc_mosi,
    input wire adc_miso,
    input wire enc_s1_n,
    input wire enc_s2_n,
    input wire enc_key_n,
    input wire key_up_n,
    input wire key_down_n,
    input wire [2:0] panel_bank,
    input wire [3:0] panel_key,
    input wire guide_override,
    input wire [2:0] guide_pad,
    input wire [6:0] guide_note,
    input wire remote_absolute,
    input wire [6:0] remote_note,
    input wire panel_timbre,
    input wire [1:0] panel_handpan_style,
    input wire panel_vibrato_enabled,
    input wire [3:0] panel_vibrato_depth,
    input wire [4:0] panel_volume_level,
    input wire [2:0] panel_effect_mask,
    input wire remote_command_valid,
    input wire [7:0] remote_command_type,
    input wire [7:0] remote_command_value,
    input wire remote_session_active,
    input wire remote_strike_valid,
    input wire [2:0] remote_strike_channel,
    input wire [7:0] remote_strike_velocity,
    input wire [6:0] remote_pressed,
    // Offline melody voice, independent of the phone's seven held-key slots.
    input wire autoplay_note_gate,
    input wire [6:0] autoplay_note_index,
    input wire autoplay_timbre,
    input wire tool_diag_enabled,
    input wire[31:0] tool_diag_gate,
    input wire[223:0] tool_diag_notes,
    input wire tool_map_enabled,tool_clear,
    input wire[48:0] tool_pad_map,
    output wire signed[15:0] output_pcm,
    output wire output_pcm_tick,
    output wire[5:0] synth_active_voices,
    output wire synth_deadline_fault,
    output wire[8:0] synth_max_cycles,
    output wire remote_voice_ready,
    output wire dac_bclk,
    output wire dac_lrclk,
    output wire dac_din,
    output wire [6:0] pad_led_on,
    output wire [6:0] pad_pressed_o,
    output wire [63:0] telemetry_o,
    output wire [55:0] force_visual_o,
    output wire [7:0] bend_o,
    // Status for a later OLED controller; not wired to a display yet.
    output wire [2:0] bank_index,
    output wire sustain_on,
    output wire [5:0] active_voice_count,
    output wire [1:0] display_mode,
    // Observability for the separate offline-guide experiment. Existing
    // tops may leave these outputs unconnected without changing audio.
    output wire strike_event,
    output wire [2:0] strike_channel_o
);
    wire adc_valid;
    wire [2:0] adc_channel;
    wire [11:0] adc_value;
    wire strike_valid;
    wire [2:0] strike_channel;
    wire [7:0] strike_velocity;
    assign strike_event = strike_valid;
    assign strike_channel_o = strike_channel;
    wire [6:0] pressed;
    assign pad_pressed_o = pressed;
    reg [63:0] sampled_levels;
    assign telemetry_o = sampled_levels;
    wire level_valid;
    wire [2:0] level_channel;
    wire [7:0] level_velocity;
    reg [55:0] force_visual_levels;
    assign force_visual_o = force_visual_levels;
    integer force_i;
    always @(posedge clk_audio or negedge rst_n) begin
        if (!rst_n) force_visual_levels <= 56'd0;
        else begin
            for (force_i=0; force_i<7; force_i=force_i+1)
                if (!pressed[force_i])
                    force_visual_levels[force_i*8 +: 8] <= 8'd0;
            if (level_valid && level_channel < 3'd7)
                force_visual_levels[level_channel*8 +: 8] <= level_velocity;
        end
    end
    wire sample_tick;
    wire diag_active=PRODUCT_TOOLS!=0 && tool_diag_enabled;
    reg[2:0] output_tick_delay;
    always @(posedge clk_audio or negedge rst_n)begin
        if(!rst_n)output_tick_delay<=0;else output_tick_delay<={output_tick_delay[1:0],sample_tick};
    end
    assign output_pcm_tick=output_tick_delay[2];
    wire [31:0] gate;
    wire [223:0] note_index;
    wire [255:0] velocity;
    wire [255:0] synth_velocity;
    wire [95:0] voice_zone;
    wire feature_gate;
    localparam integer DEMO_BITS = DEMO_HOLD_CYCLES < 2 ? 1 :
                                   $clog2(DEMO_HOLD_CYCLES + 1);
    reg [1:0] key_sync1, key_sync2;
    reg [DEMO_BITS-1:0] demo_hold_count;
    reg demo_armed;
    reg additive_mode_request;
    reg additive_mode;
    reg banked_mode_request;
    reg banked_mode;
    wire banked_mode_effective = PANEL_CONTROL != 0 ? 1'b1 : banked_mode;
    wire both_keys_down = key_sync2 == 2'b00;
    wire mode_can_switch = banked_mode ||
        ((pressed == 7'd0) && !feature_gate);
    wire mode_switch = PANEL_CONTROL == 0 &&
        BANKED32_AVAILABLE != 0 && sample_tick &&
        mode_can_switch &&
        ((additive_mode_request != additive_mode) ||
         (banked_mode_request != banked_mode));
    always @(posedge clk_audio or negedge rst_n) begin
        if (!rst_n) begin
            key_sync1 <= 2'b11;
            key_sync2 <= 2'b11;
            demo_hold_count <= {DEMO_BITS{1'b0}};
            demo_armed <= 1'b1;
            additive_mode_request <= 1'b0;
            additive_mode <= 1'b0;
            banked_mode_request <= 1'b0;
            banked_mode <= 1'b0;
        end else begin
            key_sync1 <= {key_down_n, key_up_n};
            key_sync2 <= key_sync1;
            if (!both_keys_down) begin
                demo_hold_count <= {DEMO_BITS{1'b0}};
                demo_armed <= 1'b1;
            end else if (demo_armed) begin
                if (demo_hold_count == DEMO_HOLD_CYCLES - 1) begin
                    if (BANKED32_AVAILABLE == 0)
                        additive_mode_request <= !additive_mode_request;
                    else if (!additive_mode_request &&
                             !banked_mode_request)
                        additive_mode_request <= 1'b1;
                    else if (additive_mode_request) begin
                        additive_mode_request <= 1'b0;
                        banked_mode_request <= 1'b1;
                    end else
                        banked_mode_request <= 1'b0;
                    demo_armed <= 1'b0;
                end else
                    demo_hold_count <= demo_hold_count + 1'b1;
            end
            // Apply a mode change at an audio frame boundary, after AI0 is
            // released, so an existing held note is not abruptly retimbred.
            if (BANKED32_AVAILABLE == 0 && sample_tick &&
                !pressed[0] && !feature_gate)
                additive_mode <= additive_mode_request;
            else if (BANKED32_AVAILABLE != 0 && sample_tick &&
                     mode_can_switch) begin
                additive_mode <= additive_mode_request;
                banked_mode <= banked_mode_request;
            end
        end
    end
    wire [2:0] active_bank;
    wire bank_sustain, bank_clear;
    generate if (PANEL_CONTROL != 0) begin: panel_bank_controls
        assign active_bank = panel_bank;
        assign bank_sustain = 1'b0;
        assign bank_clear = 1'b0;
    end else if (BANKED32_AVAILABLE != 0) begin: bank_controls
        banked32_controls #(.DEBOUNCE_CYCLES(VOLUME_DEBOUNCE_CYCLES),
                            .LONG_PRESS_CYCLES(ENC_LONG_PRESS_CYCLES))
            controls (
                .clk(clk_audio), .rst_n(rst_n), .enabled(banked_mode),
                .key_up_n(key_up_n), .key_down_n(key_down_n),
                .enc_key_n(enc_key_n), .bank(active_bank),
                .sustain_on(bank_sustain), .clear_pulse(bank_clear)
            );
    end else begin: no_bank_controls
        assign active_bank = 3'd0;
        assign bank_sustain = 1'b0;
        assign bank_clear = 1'b0;
    end endgenerate
    assign bank_index = active_bank;
    assign sustain_on = bank_sustain;
    assign display_mode = banked_mode_effective ? 2'd2 :
                          additive_mode ? 2'd1 : 2'd0;
    reg [5:0] voice_count_comb;
    integer count_i;
    always @* begin
        voice_count_comb = 6'd0;
        for (count_i=0; count_i<32; count_i=count_i+1)
            voice_count_comb = voice_count_comb + gate[count_i];
    end
    assign active_voice_count = voice_count_comb;
    reg [7:0] velocity_ramp [0:31];
    wire [31:0] remote_owner;
    wire [255:0] performance_velocity,spectral_expression;
    wire current_pressure_valid;
    wire [2:0] current_pressure_channel;
    wire [7:0] current_pressure_velocity;
    generate if(CONTINUOUS_EXPRESSION)begin: continuous_expression
        pressure_expression32 expression_control(
            .clk(clk_audio),.rst_n(rst_n),.sample_tick(sample_tick),.gate(gate),
            .remote_owner(remote_owner),.voice_zone(voice_zone),.attack_velocity(velocity),
            .pressure_valid(current_pressure_valid),.pressure_channel(current_pressure_channel),
            .pressure_velocity(current_pressure_velocity),.performance_velocity(performance_velocity),
            .expression(spectral_expression));
    end else begin: legacy_expression
        assign performance_velocity=velocity;assign spectral_expression=velocity;
    end endgenerate
    integer v;
    genvar g;
    generate for (g = 0; g < 32; g = g + 1) begin: volume_per_voice
        // Pad calibration belongs in the pressure profile. Physical pad 0
        // must not silently halve either a pad or a phone-owned voice.
        assign synth_velocity[g*8 +: 8] = velocity_ramp[g];
    end endgenerate

    always @(posedge clk_audio or negedge rst_n) begin
        if (!rst_n) begin
            for (v = 0; v < 32; v = v + 1)
                velocity_ramp[v] <= 8'd0;
        end else if (sample_tick) begin
            for (v = 0; v < 32; v = v + 1) begin
                if ({1'b0, performance_velocity[v*8 +: 8]} >
                    {1'b0, velocity_ramp[v]} + 9'd4)
                    velocity_ramp[v] <= velocity_ramp[v] + 8'd4;
                else if ({1'b0, velocity_ramp[v]} >
                         {1'b0, performance_velocity[v*8 +: 8]} + 9'd4)
                    velocity_ramp[v] <= velocity_ramp[v] - 8'd4;
                else
                    velocity_ramp[v] <= performance_velocity[v*8 +: 8];
            end
        end
    end

    reg [7:0] slider_bend;
    reg [7:0] remote_bend;
    reg remote_bend_active;
    reg [7:0] smooth_bend;
    wire legacy_vibrato_enabled;
    wire [3:0] legacy_vibrato_depth;
    wire legacy_timbre_select;
    wire vibrato_enabled = PANEL_CONTROL != 0 ?
        panel_vibrato_enabled : legacy_vibrato_enabled;
    wire [3:0] vibrato_depth = PANEL_CONTROL != 0 ?
        panel_vibrato_depth : legacy_vibrato_depth;
    wire timbre_select = PANEL_CONTROL != 0 ?
        panel_timbre : legacy_timbre_select;
    wire signed [7:0] vibrato_offset;
    wire [7:0] bend_base = PANEL_CONTROL != 0 ? smooth_bend : slider_bend;
    wire signed [9:0] combined_bend = $signed({2'b00, bend_base}) +
                                       $signed(vibrato_offset);
    wire [7:0] effective_bend = combined_bend < 0 ? 8'd0 :
        combined_bend > 10'sd255 ? 8'd255 : combined_bend[7:0];
    reg [7:0] effective_bend_q;
    assign bend_o = bend_base;
    always @(posedge clk_audio or negedge rst_n) begin
        if (!rst_n) begin
            slider_bend <= 8'd128;
            remote_bend <= 8'd128;
            remote_bend_active <= 0;
            smooth_bend <= 8'd128;
            sampled_levels <= 64'd0;
            effective_bend_q <= 8'd128;
        end else begin
            if (adc_valid) sampled_levels[adc_channel*8 +: 8] <= adc_value[11:4];
            if (adc_valid && adc_channel == 3'd7)
                slider_bend <= adc_value[11:4];
            if (PANEL_CONTROL != 0 && !remote_session_active)
                remote_bend_active <= 0;
            else if (PANEL_CONTROL != 0 && remote_command_valid) begin
                if (remote_command_type == 8'h1b) begin
                    remote_bend <= remote_command_value;
                    remote_bend_active <= 1;
                end else if (remote_command_type == 8'h1c)
                    remote_bend_active <= 0;
            end
            if (sample_tick && PANEL_CONTROL != 0) begin
                if (smooth_bend < (remote_bend_active ? remote_bend : slider_bend))
                    smooth_bend <= smooth_bend +
                        (((remote_bend_active ? remote_bend : slider_bend)-smooth_bend) > 8 ?
                         (((remote_bend_active ? remote_bend : slider_bend)-smooth_bend) >> 3) : 1);
                else if (smooth_bend > (remote_bend_active ? remote_bend : slider_bend))
                    smooth_bend <= smooth_bend -
                        ((smooth_bend-(remote_bend_active ? remote_bend : slider_bend)) > 8 ?
                         ((smooth_bend-(remote_bend_active ? remote_bend : slider_bend)) >> 3) : 1);
            end
            if (PANEL_CONTROL == 0 || sample_tick)
                effective_bend_q <= effective_bend;
        end
    end

    ec11_control #(.DEBOUNCE_CYCLES(ENC_DEBOUNCE_CYCLES),
                   .LONG_PRESS_CYCLES(ENC_LONG_PRESS_CYCLES),
                   .LONG_PRESS_ENABLE(1)) encoder (
        .clk(clk_audio), .rst_n(rst_n),
        .s1_n(banked_mode_effective ? 1'b1 : enc_s1_n),
        .s2_n(banked_mode_effective ? 1'b1 : enc_s2_n),
        .key_n(banked_mode_effective ? 1'b1 : enc_key_n),
        .enabled(legacy_vibrato_enabled),
        .depth(legacy_vibrato_depth),
        .timbre_select(legacy_timbre_select)
    );
    vibrato_bend vibrato (
        .clk(clk_audio), .rst_n(rst_n), .sample_tick(sample_tick),
        .enabled(PANEL_CONTROL != 0 ? vibrato_enabled :
                 (banked_mode ? 1'b0 : vibrato_enabled)),
        .depth(vibrato_depth),
        .offset(vibrato_offset)
    );
    mcp3208_scan #(.HALF_CYCLES(SCAN_HALF_CYCLES),
                   .GAP_CYCLES(SCAN_GAP_CYCLES)) scanner (
        .clk(clk_audio), .rst_n(rst_n), .spi_cs_n(adc_cs_n),
        .spi_sclk(adc_sclk), .spi_mosi(adc_mosi),
        .spi_miso(adc_miso), .sample_valid(adc_valid),
        .sample_channel(adc_channel), .sample_value(adc_value)
    );
    fsr_strike_detector #(.CAL_SAMPLES(CAL_SAMPLES),
                          .PEAK_SAMPLES(PEAK_SAMPLES),
                          .EARLY_ENABLE(EARLY_FORCE_ENABLE),
                          .REARM_SAMPLES(REARM_SAMPLES),
                          .ON_THRESHOLD(ON_THRESHOLD),
                          .OFF_THRESHOLD(OFF_THRESHOLD)) detector (
        .clk(clk_audio), .rst_n(rst_n),
        .sample_valid(adc_valid && adc_channel != 3'd7),
        .sample_channel(adc_channel), .sample_value(adc_value),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .pressed(pressed),
        .level_valid(level_valid), .level_channel(level_channel),
        .level_velocity(level_velocity),.pressure_valid(current_pressure_valid),
        .pressure_channel(current_pressure_channel),.pressure_value(current_pressure_velocity)
    );
    pad_led_feedback #(.FLASH_CYCLES(LED_FLASH_CYCLES)) indicators (
        .clk(clk_audio), .rst_n(rst_n), .pressed(pressed),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .led_on(pad_led_on)
    );
    strike_voice_allocator32 #(.HOLD_SAMPLES(HOLD_SAMPLES),
                                .BANKED_MODE(BANKED32_AVAILABLE),
                                .REMOTE_ENABLE(REMOTE_ENABLE),.CUSTOM_MAP_AVAILABLE(PRODUCT_TOOLS)) allocator (
        .clk(clk_audio), .rst_n(rst_n), .sample_tick(sample_tick),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .pressed(pressed),
        .key(panel_key),.guide_override(guide_override),.guide_pad(guide_pad),.guide_note(guide_note),
        .remote_absolute(remote_absolute),.remote_note(remote_note),
        .custom_map_enabled(PRODUCT_TOOLS!=0 && tool_map_enabled),.custom_map(tool_pad_map),
        .remote_strike_valid(remote_strike_valid),
        .remote_strike_channel(remote_strike_channel),
        .remote_strike_velocity(remote_strike_velocity),
        .remote_pressed(remote_pressed),
        .level_valid(level_valid), .level_channel(level_channel),
        .level_velocity(level_velocity), .bank(active_bank),
        .banked_enable(banked_mode_effective), .sustain(bank_sustain),
        .clear_all(bank_clear || mode_switch || (PRODUCT_TOOLS!=0 && tool_clear)), .gate(gate),
        .note_index(note_index), .velocity(velocity),
        .voice_zone(voice_zone),
        .remote_voice_ready(remote_voice_ready),.remote_owner(remote_owner)
    );

    wire [31:0] feature_active;
    wire [7:0] feature_tree [1:63];
    assign feature_gate = |feature_active;
    wire [7:0] feature_velocity = feature_tree[1];
    genvar f;
    generate for (f=0; f<32; f=f+1) begin: feature_leaf
        assign feature_active[f] = gate[f] &&
            voice_zone[f*3 +: 3] == 3'd0;
        assign feature_tree[32+f] = feature_active[f] ?
            velocity_ramp[f] : 8'd0;
    end
    for (f=1; f<32; f=f+1) begin: feature_max
        assign feature_tree[f] = feature_tree[2*f] > feature_tree[2*f+1]
            ? feature_tree[2*f] : feature_tree[2*f+1];
    end endgenerate
    wire [31:0] base_gate;
    genvar d;
    generate for (d=0; d<32; d=d+1) begin: mask_ai0
        assign base_gate[d] = gate[d] &&
            !(additive_mode && voice_zone[d*3 +: 3] == 3'd0);
    end endgenerate
    wire handpan_enabled=HANDPAN_AVAILABLE && panel_handpan_style!=0;
    wire signed [15:0] audio_sample;
    wire unused_sample_valid;
    playable_synth32 #(.EXPRESSION_TEXTURE(CONTINUOUS_EXPRESSION),.DIAGNOSTIC_AVAILABLE(PRODUCT_TOOLS)) synth (
        .clk(clk_audio), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(diag_active ? tool_diag_gate:handpan_enabled ? 32'd0:base_gate), .note_index(diag_active ? tool_diag_notes:note_index),
        .velocity(diag_active ? {32{8'd16}}:synth_velocity),
        .expression(diag_active ? {32{8'd16}}:spectral_expression),
        .bend(diag_active ? 8'd128:effective_bend_q), .timbre(timbre_select),
        .diagnostic_sine(diag_active),.active_count(synth_active_voices),
        .deadline_fault(synth_deadline_fault),.max_frame_cycles(synth_max_cycles),
        .sample_out(audio_sample),
        .sample_valid(unused_sample_valid)
    );

    wire [31:0] autoplay_step;
    wire signed [15:0] autoplay_sample;
    generate if (OFFLINE_PLAYER != 0) begin: offline_melody
        note_step_table72 autoplay_lookup (
            .note_index(autoplay_note_index),.phase_step(autoplay_step)
        );
        synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(CONTINUOUS_EXPRESSION)) autoplay_voice (
            .clk(clk_audio),.rst_n(rst_n),.sample_tick(sample_tick),
            .gate(autoplay_note_gate && autoplay_step != 0),
            .phase_step(autoplay_step),.velocity(8'd176),
            .expression(8'd176),.pitch_index(autoplay_note_index),
            .timbre(autoplay_timbre),.sample_out(autoplay_sample)
        );
    end else begin: no_offline_melody
        assign autoplay_step = 0;
        assign autoplay_sample = 0;
    end endgenerate

    wire [31:0] c4_step;
    note_step_table32 c4_lookup (.note_index(5'd0),
                                  .phase_step(c4_step));
    wire signed [8:0] bend_delta =
        $signed({1'b0,effective_bend_q}) - 9'sd128;
    wire signed [17:0] bend_ratio_signed =
        18'sd65536 + bend_delta * 9'sd30;
    wire [48:0] c4_bent_product = c4_step * bend_ratio_signed[16:0];
    wire [31:0] additive_step = c4_bent_product[47:16];
    wire signed [15:0] additive_sample;
    wire additive_sample_valid;
    additive32_tm additive (
        .clk(clk_audio), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(additive_mode && feature_gate), .base_step(additive_step),
        .velocity(feature_velocity >> 1),
        .component_mask(32'hffffffff),
        .sample_out(additive_sample),
        .sample_valid(additive_sample_valid)
    );

    wire [2:0] gain_level;
    // Match the ordinary AI0 level after the harmonic balance adjustment.
    wire signed [15:0] additive_balanced = additive_sample >>> 2;
    wire signed [15:0] additive_active =
        additive_mode ? additive_balanced : 16'sd0;
    wire signed [15:0] handpan_sample;
    generate if(HANDPAN_AVAILABLE)begin: handpan_instrument
        wire signed [15:0] modal_sample,metal_sample;
        wire modal_valid;
        wire [6:0] hit_note;
        wire note_valid;
        wire [2:0] hit_pad=strike_valid ? strike_channel:remote_strike_channel;
        wire [6:0] mapped_entry=tool_pad_map[hit_pad*7 +: 7];
        wire [2:0] arranged_pad=PRODUCT_TOOLS!=0 && tool_map_enabled && mapped_entry>=120 ? mapped_entry-7'd120:hit_pad;
        handpan_pitch_layout map(.bank(active_bank),.pad(arranged_pad),.key(panel_key),
            .note_index(hit_note),.valid(note_valid));
        handpan_modal32 sound(.clk(clk_audio),.rst_n(rst_n),.sample_tick(sample_tick),.enabled(handpan_enabled),
            .strike_valid(strike_valid || (remote_strike_valid && (remote_absolute || note_valid))),
            .strike_note(!strike_valid && remote_absolute ? remote_note:hit_note),
            .strike_velocity(strike_valid ? strike_velocity:remote_strike_velocity),
            .rhythmic(panel_handpan_style==2),.bend(effective_bend_q),
            .sample_out(modal_sample),.sample_valid(modal_valid),.overflow(),.active_count());
        rock_voice_fx metal(.clk(clk_audio),.rst_n(rst_n),.enabled(handpan_enabled && panel_handpan_style==2),
            .input_valid(modal_valid),.sample_in(modal_sample),.drive(vibrato_depth),.tone(bend_base),
            .sample_out(metal_sample),.sample_valid(),.overflow());
        assign handpan_sample=panel_handpan_style==2 ? metal_sample:modal_sample;
    end else begin:no_handpan
        assign handpan_sample=0;
    end endgenerate
    wire signed [15:0] poly_balanced = handpan_enabled ? (handpan_sample >>> 2):
        banked_mode_effective ? (audio_sample >>> 2) : audio_sample;
    wire signed [15:0] autoplay_balanced = diag_active ? 16'sd0:autoplay_sample >>> 2;
    wire signed [17:0] mixed_wide =
        $signed({{2{poly_balanced[15]}},poly_balanced}) +
        $signed({{2{additive_active[15]}},additive_active}) +
        $signed({{2{autoplay_balanced[15]}},autoplay_balanced});
    wire signed [15:0] mixed_sample =
        mixed_wide > 18'sd32767 ? 16'sh7fff :
        mixed_wide < -18'sd32768 ? 16'sh8000 : mixed_wide[15:0];
    wire signed [19:0] audio_extended =
        $signed({{4{mixed_sample[15]}}, mixed_sample});
    wire signed [19:0] boosted_wide = gain_level == 3'd3 ?
        ((audio_extended <<< 2) + (audio_extended <<< 1)) :
        (audio_extended <<< (gain_level >= 3'd4 ?
                              gain_level - 3'd1 : gain_level));
    wire signed [15:0] boosted_sample =
        boosted_wide > 20'sd32767 ? 16'sh7fff :
        boosted_wide < -20'sd32768 ? 16'sh8000 : boosted_wide[15:0];
    // Experimental panel volume: 16/31 equals the legacy 4x nominal gain
    // after the banked-mode quarter-scale headroom. Advance one half-step
    // per 64 audio frames so an EC11 click cannot cause a hard amplitude jump.
    reg [5:0] panel_gain_q;
    localparam integer GAIN_FRAME_BITS = PANEL_GAIN_RAMP_FRAMES < 2 ? 1 :
                                         $clog2(PANEL_GAIN_RAMP_FRAMES);
    reg [GAIN_FRAME_BITS-1:0] panel_gain_frame_count;
    wire[4:0] safe_volume=diag_active && panel_volume_level>16 ? 5'd16:panel_volume_level;
    wire [5:0] panel_gain_target = {safe_volume, 1'b0};
    always @(posedge clk_audio or negedge rst_n) begin
        if (!rst_n) begin
            panel_gain_q <= 6'd32;
            panel_gain_frame_count <= {GAIN_FRAME_BITS{1'b0}};
        end else if (sample_tick) begin
            panel_gain_frame_count <= panel_gain_frame_count + 1'b1;
            if (panel_gain_frame_count == PANEL_GAIN_RAMP_FRAMES - 1) begin
                panel_gain_frame_count <= {GAIN_FRAME_BITS{1'b0}};
                if (panel_gain_q < panel_gain_target)
                    panel_gain_q <= panel_gain_q + 1'b1;
                else if (panel_gain_q > panel_gain_target)
                    panel_gain_q <= panel_gain_q - 1'b1;
            end
        end
    end
    // Process at the unboosted synth level. Feeding already clipped 4x
    // panel audio into delay feedback made all three effects sound harsh and
    // disproportionately loud at the user's normal volume setting.
    wire signed [15:0] effected_pre_gain;
    generate if (PANEL_CONTROL != 0 && EFFECTS_AVAILABLE != 0) begin: panel_fx
        audio_effects_product effects (
            .clk(clk_audio),.rst_n(rst_n),.sample_tick(sample_tick),
            .dry_in(mixed_sample),.enable(diag_active ? 3'd0:panel_effect_mask),
            .sample_out(effected_pre_gain)
        );
    end else begin: no_panel_fx
        assign effected_pre_gain = mixed_sample;
    end endgenerate
    wire signed [22:0] panel_product =
        $signed(effected_pre_gain) * $signed({1'b0, panel_gain_q});
    wire signed [22:0] panel_scaled = panel_product >>> 3;
    wire signed [15:0] panel_sample =
        panel_scaled > 23'sd32767 ? 16'sh7fff :
        panel_scaled < -23'sd32768 ? 16'sh8000 : panel_scaled[15:0];
    wire signed [15:0] output_sample = PANEL_CONTROL != 0 ?
        panel_sample : boosted_sample;
    assign output_pcm=output_sample;
    volume_buttons #(.DEBOUNCE_CYCLES(VOLUME_DEBOUNCE_CYCLES)) volume_control (
        .clk(clk_audio), .rst_n(rst_n),
        .key_up_n((both_keys_down || banked_mode_effective) ?
                  1'b1 : key_up_n),
        .key_down_n((both_keys_down || banked_mode_effective) ?
                    1'b1 : key_down_n),
        .gain_level(gain_level)
    );
    generate if (HEADPHONE_OUTPUT != 0) begin: headphone_monitor
        pt8211_tx_12m288 #(.OUTPUT_SHIFT(HEADPHONE_SHIFT)) tx (
            .clk_audio(clk_audio),.rst_n(rst_n),.sample_in(output_sample),
            .sample_tick(sample_tick),.audio_bclk(dac_bclk),
            .audio_ws(dac_lrclk),.audio_din(dac_din)
        );
    end else begin: external_i2s
    i2s_stereo_tx tx (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .sample_in(output_sample), .sample_tick(sample_tick),
        .i2s_bclk(dac_bclk), .i2s_lrclk(dac_lrclk), .i2s_sd(dac_din)
    );
    end endgenerate
endmodule
