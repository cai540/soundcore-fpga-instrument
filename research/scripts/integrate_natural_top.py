from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'board/pressure_i2s_panel_oled_ble_experiment_top.v';t=p.read_text(encoding='utf8')
def rep(a,b):
    global t
    assert a in t,a[:100];t=t.replace(a,b)
rep('wire [55:0] remote_payload;','wire [111:0] remote_payload;\n    reg [3:0] manual_key;\n    wire [3:0] score_key;\n    wire [3:0] builtin_key=song_index[0] ? 4\'d2 : 4\'d5;\n    wire [3:0] effective_key=score_engaged && !score_finished ? score_key :\n        (autoplay_active || (!demo_mode && (ui_state==2 || ui_state==3))) ? builtin_key : manual_key;')
rep('led_mode <= 0;','led_mode <= 0;\n            manual_key<=0;')
rep("if (remote_type == 8'h1d)","if (remote_type == 8'h27 && remote_value<12)manual_key<=remote_value[3:0];\n            if (remote_type == 8'h1d)")
rep('wire remote_fire;','''wire remote_fire;
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
    assign remote_visual_mask=remote_mask_comb;''')
rep('wire [5:0] score_note;','wire [6:0] score_note;')
rep('wire [5:0] autoplay_note;','wire [6:0] autoplay_note;')
rep('.strike_valid(strike_event | remote_fire),','.strike_valid(strike_event | judge_remote),')
rep('.strike_pad(remote_fire ? remote_pending_channel : strike_channel),','.strike_pad(judge_pad),')
rep('.step(score_step),.bank(score_bank),','.key(score_key),.step(score_step),.bank(score_bank),')
rep('assign score_bank=0;','assign score_key=0;assign score_bank=0;')
rep('.song_select(song_index[0]),.event_index','.song_select(song_index[0]),.key(builtin_key),.event_index')
rep('.remote_strike_velocity(remote_pending_velocity)\n','.remote_strike_velocity(remote_pending_velocity),.remote_absolute(remote_absolute),\n        .remote_strike_note(remote_note),.remote_notes(remote_notes_exact)\n')
rep('.panel_bank(guide_bank),.panel_timbre(score_guiding && !score_finished ? score_timbre : timbre_select),', '''.panel_bank(guide_bank),.panel_key(effective_key),
        .guide_override(guide_override),.guide_pad(exact_guide_pad),.guide_note(guide_note_exact),
        .remote_absolute(remote_absolute),.remote_note(remote_note),
        .panel_timbre(score_guiding && !score_finished ? score_timbre :
            !demo_mode && (ui_state==2 || ui_state==3) ? ~song_index[0] : timbre_select),''')
rep('.remote_value(score_start ? 8\'d0 : remote_value),.remote_payload(remote_payload),', '.remote_value(score_start ? 8\'d0 : remote_value),.remote_payload(remote_payload[55:0]),')
rep('.song_select(song_index[0]),\n        .strike_valid', '.song_select(song_index[0]),.key(builtin_key),.target_note(native_guide_note),\n        .strike_valid')
rep('wire [6:0] visual_pad_mask = pad_pressed | remote_pressed | autoplay_led;', 'wire [6:0] visual_pad_mask = pad_pressed | remote_visual_mask | autoplay_led;')
rep('.performance_led(performance_led),','.performance_led(performance_led | remote_visual_mask),')
rep('.clk(clk_audio),.rst_n(run_n),.bank(visual_bank),','.clk(clk_audio),.rst_n(run_n),.key(effective_key),.bank(visual_bank),')
rep('.bank(visual_bank),.timbre(visual_timbre),.volume(volume_level),','.key(effective_key),.bank(visual_bank),.timbre(visual_timbre),.volume(volume_level),')
p.write_text(t,encoding='utf8')
