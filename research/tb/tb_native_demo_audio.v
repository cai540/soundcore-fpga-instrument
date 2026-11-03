`timescale 1ns/1ps
// Native K4/K5 -> real event player -> real synthesis -> decoded speaker I2S.
// Every pressure input stays at its calibrated baseline throughout this test.
module tb_native_demo_audio;
    reg clk=0,rst_n=0;always #41 clk=~clk;
    reg [4:0] keys=5'b11111;
    wire [2:0] bank;
    wire [1:0] ui,state;
    wire [7:0] song,local_value,command_value;
    wire [4:0] volume;
    wire timbre,vibrato,local_valid,command_valid,active,paused,restart,finished,gate;
    wire [5:0] note;
    wire cs,sclk,mosi,miso,bck,ws,din;
    front_panel_product #(.DEBOUNCE_CYCLES(2)) panel(
        .clk(clk),.rst_n(rst_n),.bank_down_n(keys[0]),.bank_up_n(keys[1]),.timbre_n(keys[2]),
        .song_back_n(keys[3]),.play_pause_n(keys[4]),.enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(1'b0),.remote_type(8'd0),.remote_value(8'd0),.remote_payload(56'd0),
        .player_finished(finished),.bank(bank),.ui_state(ui),.song_index(song),.volume_level(volume),
        .vibrato_enabled(vibrato),.timbre_select(timbre),.player_command_valid(local_valid),.player_command(local_value));
    song_transport_router router(.local_valid(local_valid),.local_value(local_value),
        .remote_valid(1'b0),.remote_type(8'd0),.remote_value(8'd0),.score_start(1'b0),
        .command_valid(command_valid),.command_value(command_value));
    song_autoplay_control transport(.clk(clk),.rst_n(rst_n),.command_valid(command_valid),
        .command_type(8'h23),.command_value(command_value),.song_index(song),.player_finished(finished),
        .active(active),.paused(paused),.restart_pulse(restart),.playback_state(state));
    song_event_player #(.LENGTH0(3),.LENGTH1(3),.ARTICULATION_GAP_MS(0),
        .ROM0_FILE("D:/FPGA/Projects/soundcore_2026/build/native_panel_playback_20261031/native_song0.mem"),
        .ROM1_FILE("D:/FPGA/Projects/soundcore_2026/build/native_panel_playback_20261031/native_song1.mem")) player(
        .clk(clk),.rst_n(rst_n),.run(active),.pause(paused),.restart(restart),.song_select(song[0]),
        .note_index(note),.note_gate(gate),.finished(finished));
    pressure_i2s_additive32_core #(.BANKED32_AVAILABLE(1),.PANEL_CONTROL(1),.REMOTE_ENABLE(1),
        .OFFLINE_PLAYER(1),.HEADPHONE_OUTPUT(0),.EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1),
        .CAL_SAMPLES(2),.SCAN_HALF_CYCLES(3),.SCAN_GAP_CYCLES(4)) audio(
        .clk_audio(clk),.rst_n(rst_n),.adc_cs_n(cs),.adc_sclk(sclk),.adc_mosi(mosi),.adc_miso(miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),.key_up_n(1'b1),.key_down_n(1'b1),
        .panel_bank(bank),.panel_timbre(timbre),.panel_volume_level(volume),.panel_effect_mask(3'd0),
        .panel_vibrato_enabled(vibrato),.panel_vibrato_depth(4'd4),.remote_command_valid(1'b0),
        .remote_command_type(8'd0),.remote_command_value(8'd0),.remote_session_active(1'b0),
        .remote_strike_valid(1'b0),.remote_strike_channel(3'd0),.remote_strike_velocity(8'd0),.remote_pressed(7'd0),
        .autoplay_note_gate(gate),.autoplay_note_index(note),.autoplay_timbre(1'b1),
        .dac_bclk(bck),.dac_lrclk(ws),.dac_din(din));
    wire [11:0] sample=audio.scanner.scan_channel==7 ? 12'd2048:12'd1000;
    assign miso=audio.scanner.bit_index<=11 ? sample[audio.scanner.bit_index]:1'b0;
    integer words=0,nonzero=0,physical_strikes=0,bit_count=0;
    reg previous_ws=1,have_left=0;
    reg [15:0] decoded=0,left_word=0;
    always @(posedge clk)if(rst_n && audio.strike_valid)physical_strikes=physical_strikes+1;
    always @(posedge bck)if(rst_n)begin
        if(ws!=previous_ws)begin previous_ws=ws;bit_count=0;decoded=0;end
        else begin
            bit_count=bit_count+1;
            if(bit_count>=1 && bit_count<=16)decoded={decoded[14:0],din};
            if(bit_count==16)begin
                if((^decoded)===1'bx)$fatal(1,"unknown I2S PCM word");
                if(!ws)begin left_word=decoded;have_left=1;words=words+1;if(decoded!=0)nonzero=nonzero+1;end
                else if(have_left && decoded!==left_word)$fatal(1,"left/right speaker PCM mismatch");
            end
        end
    end
    task settle;begin repeat(12)@(negedge clk);end endtask
    task tap;input integer n;begin keys[n]=0;settle();keys[n]=1;settle();end endtask
    initial begin #50000000;$fatal(1,"native speaker audio timeout");end
    initial begin
        settle();rst_n=1;
        repeat(100000)@(negedge clk);
        if(active || gate || nonzero || physical_strikes)$fatal(1,"idle input unexpectedly made sound");
        tap(3);tap(4);
        if(ui!=2 || !gate)$fatal(1,"native start did not reach the melody input");
        nonzero=0;
        repeat(200000)@(negedge clk);
        if(words<1000 || nonzero<100 || physical_strikes!=0)$fatal(1,"no real speaker PCM from native song start words=%0d nonzero=%0d strikes=%0d",words,nonzero,physical_strikes);
        tap(4);if(!paused || gate)$fatal(1,"native pause did not reach audio gate");
        $display("PASS: native K4/K5 -> timed song ROM -> harmonica synthesis -> standard speaker I2S; %0d decoded mono frames, %0d nonzero after start, zero physical strikes",words,nonzero);
        $finish;
    end
endmodule
