`timescale 1ns/1ps
module tb_native_panel_transport;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    reg [4:0] keys=5'b11111;
    reg s1=1,s2=1,ek=1,remote_valid=0,score_start=0,strike=0;
    reg [7:0] remote_type=0,remote_value=0;
    reg [2:0] struck_pad=0;
    wire [2:0] bank,target_bank,target_pad;
    wire [1:0] ui,state;
    wire [7:0] song,cursor,local_value,command_value;
    wire local_valid,command_valid,demo,mode_menu,mode_cursor,selected;
    wire [4:0] volume;
    wire vibrato,timbre,guide_restart,active,paused,restart,finished,gate;
    wire [10:0] event_index,guide_step;
    wire [5:0] note;
    wire [17:0] playback_ms;
    front_panel_product #(.DEBOUNCE_CYCLES(2),.LONG_PRESS_CYCLES(40),.DEPTH_TIMEOUT_CYCLES(200)) panel(
        .clk(clk),.rst_n(rst_n),.bank_down_n(keys[0]),.bank_up_n(keys[1]),.timbre_n(keys[2]),
        .song_back_n(keys[3]),.play_pause_n(keys[4]),.enc_s1_n(s1),.enc_s2_n(s2),.enc_key_n(ek),
        .remote_valid(remote_valid || score_start),.remote_type(score_start ? 8'h15:remote_type),
        .remote_value(score_start ? 8'd0:remote_value),.remote_payload(56'd0),.player_finished(finished),
        .bank(bank),.ui_state(ui),.song_index(song),.menu_song_index(cursor),.song_selected(selected),
        .demo_mode(demo),.mode_menu(mode_menu),.mode_cursor(mode_cursor),.volume_level(volume),
        .vibrato_enabled(vibrato),.timbre_select(timbre),.player_command_valid(local_valid),
        .player_command(local_value),.guide_restart(guide_restart));
    song_transport_router router(.local_valid(local_valid),.local_value(local_value),
        .remote_valid(remote_valid),.remote_type(remote_type),.remote_value(remote_value),
        .score_start(score_start),.command_valid(command_valid),.command_value(command_value));
    song_autoplay_control transport(.clk(clk),.rst_n(rst_n),.command_valid(command_valid),
        .command_type(8'h23),.command_value(command_value),.song_index(song),.player_finished(finished),
        .active(active),.paused(paused),.restart_pulse(restart),.playback_state(state));
    song_event_player #(.MAX_STEPS(1024),.LENGTH0(3),.LENGTH1(3),.CLK_HZ(2000),.ARTICULATION_GAP_MS(0),
        .ROM0_FILE("D:/FPGA/Projects/soundcore_2026/build/native_panel_playback_20261031/native_song0.mem"),
        .ROM1_FILE("D:/FPGA/Projects/soundcore_2026/build/native_panel_playback_20261031/native_song1.mem")) player(
        .clk(clk),.rst_n(rst_n),.run(active),.pause(paused),.restart(restart),.song_select(song[0]),
        .event_index(event_index),.note_index(note),.note_gate(gate),.finished(finished),.playback_ms(playback_ms));
    song_guide_long #(.LENGTH0(3),.LENGTH1(3),
        .ROM0_FILE("D:/FPGA/Projects/soundcore_2026/build/native_panel_playback_20261031/native_song0.mem"),
        .ROM1_FILE("D:/FPGA/Projects/soundcore_2026/build/native_panel_playback_20261031/native_song1.mem")) guide(
        .clk(clk),.rst_n(rst_n),.restart(guide_restart),.ui_state(demo ? 2'd0:ui),.song_select(song[0]),
        .strike_valid(strike),.strike_bank(target_bank),.strike_pad(struck_pad),
        .step_index(guide_step),.target_bank(target_bank),.target_pad(target_pad));
    task settle;begin repeat(12)@(negedge clk);end endtask
    task tap;input integer n;begin keys[n]=0;settle();keys[n]=1;settle();end endtask
    task hold;input integer n;begin keys[n]=0;repeat(70)@(negedge clk);keys[n]=1;settle();end endtask
    task turn;input direction;begin s2=direction;settle();s1=0;settle();s1=1;settle();s2=1;settle();end endtask
    task confirm;begin ek=0;settle();ek=1;settle();end endtask
    task remote;input [7:0] kind,value;begin
        @(negedge clk);remote_type=kind;remote_value=value;remote_valid=1;
        @(negedge clk);remote_valid=0;settle();
    end endtask
    task hit;input correct;begin
        @(negedge clk);struck_pad=correct ? target_pad:(target_pad+1)%7;strike=1;
        @(negedge clk);strike=0;settle();
    end endtask
    integer saved_ms,saved_event;
    initial begin #10000000;$fatal(1,"native transport timeout");end
    initial begin
        settle();rst_n=1;settle();
        if(!demo || ui!=0 || volume!=6 || gate)$fatal(1,"default must be idle demonstration mode");
        tap(1);if(bank!=1)$fatal(1,"K2 home bank");tap(0);if(bank!=0)$fatal(1,"K1 home bank");
        tap(2);if(timbre!=0)$fatal(1,"K3 timbre");
        tap(3);if(ui!=1 || mode_menu)$fatal(1,"K4 song menu");
        tap(1);if(cursor!=1 || song!=0)$fatal(1,"song cursor changed committed song early");
        turn(1);if(cursor!=0 || volume!=6 || vibrato)$fatal(1,"selection encoder changed settings");
        turn(1);confirm();if(ui!=0 || song!=1 || !selected)$fatal(1,"encoder song confirmation");
        tap(4);if(ui!=2 || !active || paused || !gate || note!=8)$fatal(1,"K5 must start timed song without a physical strike");
        tap(4);saved_ms=playback_ms;saved_event=event_index;
        repeat(50)@(negedge clk);
        if(ui!=3 || !paused || gate || playback_ms!=saved_ms || event_index!=saved_event)$fatal(1,"local pause not coherent");
        tap(4);if(ui!=2 || paused || !gate)$fatal(1,"local resume");
        hold(4);if(ui!=3 || !paused || gate || playback_ms!=0 || event_index!=0)$fatal(1,"long K5 must rewind and remain paused");
        tap(4);if(paused || !gate)$fatal(1,"resume from rewound start");
        wait(finished);settle();tap(4);
        if(finished || !gate || event_index!=0)$fatal(1,"K5 cannot replay a finished song");
        tap(3);if(ui!=0 || active || gate)$fatal(1,"K4 did not stop demo");
        hold(3);if(ui!=1 || !mode_menu || !mode_cursor || !demo)$fatal(1,"long K4 mode menu");
        tap(0);if(mode_cursor || !demo)$fatal(1,"mode cursor committed before confirmation");
        turn(1);turn(0);confirm();
        if(demo || mode_menu || ui!=1 || volume!=6 || vibrato)$fatal(1,"mode confirmation or encoder isolation");
        tap(0);tap(4);if(demo || ui!=2 || active || gate || guide_step!=0)$fatal(1,"guide must wait for pad strikes");
        hit(1);if(guide_step!=1)$fatal(1,"correct guided pad did not advance");
        hit(0);if(guide_step!=1)$fatal(1,"wrong guided pad advanced");
        tap(4);hit(1);if(ui!=3 || guide_step!=1)$fatal(1,"paused guide advanced");
        tap(4);hold(4);if(ui!=3 || guide_step!=0 || active)$fatal(1,"guide rewind must reset target and pause");
        hold(3);tap(1);tap(3);
        if(demo || mode_menu || ui!=1)$fatal(1,"cancelled mode choice changed committed mode");
        remote(8'h14,1);remote(8'h23,1);
        if(!demo || ui!=2 || !active || !gate)$fatal(1,"App demo must share native transport state");
        tap(4);if(ui!=3 || !paused)$fatal(1,"panel cannot pause App-started playback");
        remote(8'h23,3);if(ui!=2 || paused || !gate)$fatal(1,"App cannot resume panel-paused playback");
        remote(8'h15,1);if(demo || ui!=2 || active || gate)$fatal(1,"guide command did not stop previous demo");
        remote(8'h23,1);@(negedge clk);score_start=1;@(negedge clk);score_start=0;settle();
        if(active || ui!=0)$fatal(1,"uploaded-score takeover did not stop native player");
        $display("PASS: native K5 starts real timed ROM notes; pause/resume and clocks; rewind-paused and finished replay; K4 stop/mode; separate cursors and encoder confirmation; guide awaits correct strikes; local/App handover and score takeover");
        $finish;
    end
endmodule
