`timescale 1ns/1ps
// Real debounced five-key controller -> real OLED scheduler -> independent
// pin-level I2C receiver. No ACK is generated from the writer's internal state.
module tb_panel_oled_menu_flow;
    reg clk=0,rst_n=0;
    reg [4:0] keys=5'b11111;
    reg [87:0] capture=0;
    always #5 clk=~clk;
    wire [2:0] bank;
    wire timbre,vibrato;
    wire [4:0] volume;
    wire [1:0] ui;
    wire [7:0] song;
    front_panel_five_keys #(.DEBOUNCE_CYCLES(2),.REMOTE_CONTROL(1),.PANEL_AUTH_REQUIRED(0)) panel(
        .clk(clk),.rst_n(rst_n),.bank_down_n(keys[0]),.bank_up_n(keys[1]),
        .timbre_n(keys[2]),.song_back_n(keys[3]),.play_pause_n(keys[4]),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(1'b0),.remote_type(8'd0),.remote_value(8'd0),.remote_payload(56'd0),
        .bank(bank),.timbre_select(timbre),.volume_level(volume),.vibrato_enabled(vibrato),
        .ui_state(ui),.song_index(song));
    tri1 scl,sda;
    wire ready,nack;
    oled_status_ssd1315 #(.I2C_DIV(1),.REFRESH_CYCLES(2000000),
        .PANEL_MENU(1),.LONG_SONG_UI(1),.LYRIC_OVERLAY(1),.CAPTURE_OVERLAY(1)) display(
        .clk(clk),.rst_n(rst_n),.bank(bank),.timbre(timbre),.volume(volume),.vibrato(vibrato),
        .ui_state(ui),.menu_song(song),.guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd0),.auth_pending(1'b0),.remote_write_allowed(1'b0),.ble_frame_seen(1'b0),
        .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),
        .lyric_mode(ui==2 || ui==3),.lyric_phrase(7'd0),.lyric_character(5'd0),.lyric_progress(8'd0),
        .capture_payload((ui==2 || ui==3) ? 88'd0 : capture),.oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
    reg ack=0,receiving=0,matched=0;
    reg [7:0] shifted=0,control=0;
    integer bits=0,byte_no=0,write_page=0,write_column=0,data_count=0;
    reg [7:0] frame[0:1023];
    assign sda=ack ? 1'b0:1'bz;
    always @(negedge sda) if(scl===1'b1)begin
        receiving=1;bits=0;byte_no=0;shifted=0;matched=0;
    end
    always @(posedge sda) if(scl===1'b1)begin receiving=0;ack=0;end
    always @(negedge scl)begin
        if(receiving)ack=(bits==8 && matched);else ack=0;
    end
    always @(posedge scl) if(receiving)begin
        if(bits<8)begin
            shifted={shifted[6:0],sda};bits=bits+1;
            if(bits==8)begin
                if(byte_no==0)matched=(shifted==8'h78);
                else if(byte_no==1)control=shifted;
                else if(byte_no==2 && matched)begin
                    if(control==0)begin
                        if(shifted>=8'hb0 && shifted<=8'hb7)begin write_page=shifted-8'hb0;write_column=0;end
                    end else if(control==8'h40)begin
                        if(write_column>127)$fatal(1,"column overflow");
                        frame[write_page*128+write_column]=shifted;
                        write_column=write_column+1;data_count=data_count+1;
                    end
                end
            end
        end else begin bits=0;byte_no=byte_no+1;end
    end
    task settle;begin repeat(12)@(negedge clk);end endtask
    task tap;input integer n;begin keys[n]=0;settle();keys[n]=1;settle();end endtask
    task save_frame;
        input integer wanted_ui,wanted_bank,wanted_song;
        input [1023:0] path;
        integer fd,i;
        begin
            wait(display.shown_ui_state==wanted_ui && display.shown_bank==wanted_bank && display.shown_timbre==timbre &&
                 display.shown_menu_song==wanted_song && display.phase==3 && ready);
            @(negedge clk);
            if(nack || data_count<1024)$fatal(1,"independent slave did not receive a complete frame");
            fd=$fopen(path,"w");
            for(i=0;i<1024;i=i+1)$fdisplay(fd,"%02x",frame[i]);
            $fclose(fd);
        end
    endtask
    integer i;
    reg [7:0] menu0[0:511],golden[0:1023];
    initial begin #30000000;$fatal(1,"panel/OLED menu flow timeout");end
    initial begin
        $readmemh("D:/FPGA/Projects/soundcore_2026/board/panel_menu_frames.mem",golden);
        settle();rst_n=1;settle();
        save_frame(0,0,0,"build/panel_menu_fix_20261031/home.hex");
        tap(1);if(bank!=1)$fatal(1,"K2 did not increase bank on release");
        save_frame(0,1,0,"build/panel_menu_fix_20261031/bank_up.hex");
        tap(0);if(bank!=0)$fatal(1,"K1 did not decrease bank");
        tap(2);if(timbre!=0)$fatal(1,"K3 did not toggle timbre");
        save_frame(0,0,0,"build/panel_menu_fix_20261031/home_erhu.hex");
        // A stale phone capture overlay must not hide the local song menu.
        capture[15:8]=3;
        tap(3);if(ui!=1)$fatal(1,"K4 did not open song list");
        save_frame(1,0,0,"build/panel_menu_fix_20261031/menu0.hex");
        for(i=0;i<512;i=i+1)begin
            if(frame[i]!==golden[i])$fatal(1,"menu0 pin byte %0d got %h expected %h",i,frame[i],golden[i]);
            menu0[i]=frame[i];
        end
        tap(1);if(song!=1 || bank!=0)$fatal(1,"K2 did not select next song independently of pitch bank");
        save_frame(1,0,1,"build/panel_menu_fix_20261031/menu1.hex");
        for(i=0;i<512;i=i+1)if(frame[i]!==golden[512+i])$fatal(1,"menu1 pin byte %0d",i);
        tap(0);if(song!=0)$fatal(1,"K1 did not select previous song");
        save_frame(1,0,0,"build/panel_menu_fix_20261031/menu0_again.hex");
        for(i=0;i<512;i=i+1)if(frame[i]!==menu0[i])$fatal(1,"song-title update incoherent");
        capture=0;
        tap(4);if(ui!=2)$fatal(1,"K5 did not start guidance");
        save_frame(2,0,0,"build/panel_menu_fix_20261031/guide.hex");
        tap(4);if(ui!=3)$fatal(1,"K5 did not pause guidance");
        save_frame(3,0,0,"build/panel_menu_fix_20261031/paused.hex");
        if(frame[4*128+121]!==8'h7e)$fatal(1,"pause icon missing");
        tap(4);if(ui!=2)$fatal(1,"K5 did not resume guidance");
        save_frame(2,0,0,"build/panel_menu_fix_20261031/resumed.hex");
        if(frame[4*128+121]!==0)$fatal(1,"pause icon not cleared");
        tap(3);if(ui!=0)$fatal(1,"K4 did not return home");
        save_frame(0,0,0,"build/panel_menu_fix_20261031/restored.hex");
        $display("PASS: real five-key releases, range, timbre, song menu/selection, K5 guidance/pause/resume, home return; complete independent pin-level I2C frames match both Chinese menu images; stale capture overlay cannot hide local menu");
        $finish;
    end
endmodule
