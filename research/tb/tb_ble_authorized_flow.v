`timescale 1ns/1ps
module tb_ble_authorized_flow;
    reg clk=0,rst_n=0,k4=1,k5=1,rx_valid=0;
    reg [7:0] rx_byte=0;
    wire remote_valid,tx_valid,write_allowed,auth_pending;
    wire [7:0] remote_type,remote_value,tx_byte,song;
    wire [2:0] bank;
    wire timbre,vibrato,selected,depth_edit,led_on,led_blink;
    wire [1:0] ui_state;
    wire [4:0] volume;
    wire [3:0] depth;
    tri1 oled_scl,oled_sda;
    reg oled_ack=1;
    wire oled_ready,oled_nack;
    reg saw_oled_volume_25=0;
    reg [7:0] response[0:19];
    integer response_len=0;
    always #5 clk=~clk;
    front_panel_five_keys #(.DEBOUNCE_CYCLES(2),.LONG_PRESS_CYCLES(12),
        .AUTH_CONFIRM_CYCLES(80),.AUTH_WINDOW_CYCLES(300),
        .REMOTE_CONTROL(1)) panel (
        .clk(clk),.rst_n(rst_n),.bank_down_n(1'b1),.bank_up_n(1'b1),
        .timbre_n(1'b1),.song_back_n(k4),.play_pause_n(k5),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.bank(bank),.timbre_select(timbre),
        .ui_state(ui_state),.song_index(song),.song_selected(selected),
        .volume_level(volume),.vibrato_enabled(vibrato),
        .vibrato_depth(depth),.depth_edit(depth_edit),
        .auth_pending(auth_pending),.remote_write_allowed(write_allowed),
        .guide_led_on(led_on),.guide_led_blink(led_blink)
    );
    ble_control_endpoint endpoint (
        .clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),
        .write_enable(write_allowed),.bank(bank),.timbre(timbre),
        .volume(volume),.vibrato(vibrato),.ui_state(ui_state),
        .song_index(song),.guide_step(4'd0),.guide_target(3'd0),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.tx_valid(tx_valid),
        .tx_byte(tx_byte),.tx_ready(1'b1)
    );
    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(300)) oled (
        .clk(clk),.rst_n(rst_n),.bank(bank),.timbre(timbre),
        .volume(volume),.vibrato(vibrato),.ui_state(ui_state),
        .guide_step(4'd0),.guide_target(3'd0),
        .auth_pending(auth_pending),.remote_write_allowed(write_allowed),
        .pad_active(7'd0),.contrast(8'h7f),
        .oled_scl(oled_scl),.oled_sda(oled_sda),
        .ready(oled_ready),.nack_seen(oled_nack)
    );
    assign oled_sda = oled_ack &&
        (oled.writer.state==4 || oled.writer.state==5 || oled.writer.state==9)
        ? 1'b0 : 1'bz;
    always @(posedge clk) if (rst_n && oled.tx_start && oled.phase==2 &&
                                oled.page_index==0 && oled.column==114 &&
                                oled.tx_payload==8'hF8 && volume==25)
        saw_oled_volume_25=1;
    function [7:0] crc_next;
        input [7:0] old,data;
        reg [7:0] c;
        integer j;
        begin
            c=old^data;
            for(j=0;j<8;j=j+1)c=c[7]?(c<<1)^8'h07:(c<<1);
            crc_next=c;
        end
    endfunction
    task send_byte;
        input [7:0] b;
        begin
            @(negedge clk);rx_byte=b;rx_valid=1;
            @(negedge clk);rx_valid=0;
        end
    endtask
    task send_frame;
        input [7:0] typ,seq,len,value;
        reg [7:0] c;
        begin
            c=crc_next(0,1);
            c=crc_next(c,typ);c=crc_next(c,seq);c=crc_next(c,len);
            send_byte(8'hA5);send_byte(1);send_byte(typ);
            send_byte(seq);send_byte(len);
            if(len!=0)begin send_byte(value);c=crc_next(c,value);end
            send_byte(c);
        end
    endtask
    task collect;
        begin
            response_len=0;
            wait(tx_valid);
            while(tx_valid)begin
                @(posedge clk);response[response_len]=tx_byte;
                response_len=response_len+1;
                @(negedge clk);
            end
        end
    endtask
    task tap_k4;
        begin
            @(negedge clk);k4=0;
            repeat(6)@(negedge clk);k4=1;
            repeat(6)@(negedge clk);
        end
    endtask
    task tap_k5;
        begin
            @(negedge clk);k5=0;
            repeat(6)@(negedge clk);k5=1;
            repeat(6)@(negedge clk);
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        send_frame(8'h01,8'h01,0,0);collect();
        if(response_len!=15||response[13]!=0) $fatal(1,"power-on must be read-only");
        send_frame(8'h10,8'h02,1,25);collect();
        if(response[2]!=8'hE0||response[5]!=4||volume!=16)
            $fatal(1,"write before consent accepted");
        tap_k4();
        @(negedge clk);k4=0;
        repeat(23)@(negedge clk);k4=1;
        repeat(6)@(negedge clk);
        if(!auth_pending||write_allowed) $fatal(1,"prompt missing");
        tap_k5();
        if(!write_allowed||auth_pending) $fatal(1,"consent failed");
        send_frame(8'h10,8'h03,1,25);collect();
        if(response_len!=15||response[13]!=1||response[7]!=25||volume!=25)
            $fatal(1,"authorized write not applied/confirmed");
        repeat(100) @(negedge clk);
        send_frame(8'h19,8'h30,0,0);collect();
        if(response[2]!=8'h80||response[13]!=1)
            $fatal(1,"authorized heartbeat must renew and acknowledge");
        tap_k4(); // Leave song list so the Chinese play row shows volume.
        wait(saw_oled_volume_25);
        repeat(310)@(negedge clk);
        send_frame(8'h01,8'h04,0,0);collect();
        if(response[13]!=0) $fatal(1,"authorization did not expire");
        $display("PASS: BLE locked query, K4/K5 grant, confirmed write, OLED update, expiry");
        $finish;
    end
    initial begin
        #10000000;
        $fatal(1,"OLED did not reflect confirmed BLE volume command");
    end
endmodule
