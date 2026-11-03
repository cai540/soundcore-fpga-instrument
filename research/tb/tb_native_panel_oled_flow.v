`timescale 1ns/1ps
// Product mode selection and native K5 feedback, decoded from actual I2C pins.
module tb_native_panel_oled_flow;
    reg clk=0,rst_n=0;
    reg [4:0] keys=5'b11111;
    reg [87:0] capture=0;
    always #5 clk=~clk;
    wire [2:0] bank;
    wire timbre,vibrato,demo,mode_menu,mode_cursor;
    wire [4:0] volume;
    wire [1:0] ui;
    wire [7:0] song,cursor;
    front_panel_product #(.DEBOUNCE_CYCLES(2),.LONG_PRESS_CYCLES(40)) panel(
        .clk(clk),.rst_n(rst_n),.bank_down_n(keys[0]),.bank_up_n(keys[1]),
        .timbre_n(keys[2]),.song_back_n(keys[3]),.play_pause_n(keys[4]),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(1'b0),.remote_type(8'd0),.remote_value(8'd0),.remote_payload(56'd0),
        .player_finished(1'b0),.bank(bank),.timbre_select(timbre),.volume_level(volume),
        .vibrato_enabled(vibrato),.ui_state(ui),.song_index(song),.menu_song_index(cursor),
        .demo_mode(demo),.mode_menu(mode_menu),.mode_cursor(mode_cursor));
    tri1 scl,sda;
    wire ready,nack;
    oled_status_ssd1315 #(.I2C_DIV(1),.REFRESH_CYCLES(2000000),
        .PANEL_MENU(1),.PRODUCT_PANEL(1),.LONG_SONG_UI(1),.LYRIC_OVERLAY(1),.CAPTURE_OVERLAY(1)) display(
        .clk(clk),.rst_n(rst_n),.bank(bank),.timbre(timbre),.volume(volume),.vibrato(vibrato),
        .ui_state(ui),.menu_song(cursor),.menu_mode_select(mode_menu),.menu_mode_cursor(mode_cursor),.demo_mode(demo),
        .guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(demo ? (ui==2 ? 2'd1:ui==3 ? 2'd2:2'd0):2'd0),
        .auth_pending(1'b0),.remote_write_allowed(1'b0),.ble_frame_seen(1'b0),
        .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),
        .lyric_mode(ui==2 || ui==3),.lyric_phrase(7'd0),.lyric_character(5'd0),.lyric_progress(8'd0),
        .capture_payload((ui==2 || ui==3) ? 88'd0:capture),.oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
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
    task hold;input integer n;begin keys[n]=0;repeat(70)@(negedge clk);keys[n]=1;settle();end endtask
    task save_frame;
        input integer wanted_ui,wanted_song,wanted_mode_menu,wanted_cursor,wanted_demo;
        input [1023:0] path;
        integer fd,i;
        begin
            wait(display.shown_ui_state==wanted_ui && display.shown_menu_song==wanted_song &&
                display.shown_mode_select==wanted_mode_menu && display.shown_mode_cursor==wanted_cursor &&
                display.shown_demo_mode==wanted_demo && display.shown_timbre==timbre && display.phase==3 && ready);
            @(negedge clk);
            if(nack || data_count<1024)$fatal(1,"independent I2C receiver did not get complete frame");
            fd=$fopen(path,"w");
            for(i=0;i<1024;i=i+1)$fdisplay(fd,"%02x",frame[i]);
            $fclose(fd);
        end
    endtask
    reg [7:0] golden[0:4095];
    integer i;
    task expect_menu;
        input integer index;
        begin for(i=0;i<512;i=i+1)
            if(frame[i]!==golden[index*512+i])$fatal(1,"menu frame=%0d byte=%0d got=%h expected=%h",index,i,frame[i],golden[index*512+i]);
        end
    endtask
    initial begin #60000000;$fatal(1,"product OLED mode flow timeout");end
    initial begin
        $readmemh("D:/FPGA/Projects/soundcore_2026/board/panel_product_menu_frames.mem",golden);
        settle();rst_n=1;settle();
        save_frame(0,0,0,1,1,"build/native_panel_playback_20261031/home.hex");
        capture[15:8]=3;
        tap(3);save_frame(1,0,0,1,1,"build/native_panel_playback_20261031/demo0.hex");expect_menu(2);
        tap(1);save_frame(1,1,0,1,1,"build/native_panel_playback_20261031/demo1.hex");expect_menu(3);
        capture=0;
        tap(4);save_frame(2,1,0,1,1,"build/native_panel_playback_20261031/playing.hex");
        tap(4);save_frame(3,1,0,1,1,"build/native_panel_playback_20261031/paused.hex");
        if(frame[4*128+121]!==8'h7e)$fatal(1,"demo pause mark missing");
        tap(4);save_frame(2,1,0,1,1,"build/native_panel_playback_20261031/resumed.hex");
        tap(3);save_frame(0,1,0,1,1,"build/native_panel_playback_20261031/back.hex");
        hold(3);save_frame(1,1,1,1,1,"build/native_panel_playback_20261031/mode_demo.hex");expect_menu(5);
        tap(0);save_frame(1,1,1,0,1,"build/native_panel_playback_20261031/mode_guide.hex");expect_menu(4);
        if(!demo)$fatal(1,"moving mode cursor must not commit it");
        tap(4);save_frame(1,1,0,0,0,"build/native_panel_playback_20261031/guide1.hex");expect_menu(1);
        tap(0);save_frame(1,0,0,0,0,"build/native_panel_playback_20261031/guide0.hex");expect_menu(0);
        tap(4);save_frame(2,0,0,0,0,"build/native_panel_playback_20261031/guiding.hex");
        hold(4);save_frame(3,0,0,0,0,"build/native_panel_playback_20261031/rewound_guide.hex");
        tap(3);save_frame(0,0,0,0,0,"build/native_panel_playback_20261031/restored.hex");
        $display("PASS: native song and guide/demo mode cursors; all six 512-byte Chinese menu frames match independent I2C receiver; K5 play/pause/resume/guide feedback and long-key release suppression; local menus override stale phone capture");
        $finish;
    end
endmodule
