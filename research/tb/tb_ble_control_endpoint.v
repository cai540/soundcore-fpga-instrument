`timescale 1ns/1ps
module tb_ble_control_endpoint;
    reg clk=0,rst_n=0,rx_valid=0,write_enable=1;
    reg [7:0] rx_byte=0;
    wire remote_valid,tx_valid;
    wire [7:0] remote_type,remote_value,tx_byte;
    wire [2:0] bank;
    wire timbre,vibrato,selected,depth_edit,led_on,led_blink;
    wire [1:0] ui_state;
    wire [7:0] song;
    wire [4:0] volume;
    wire [3:0] depth;
    reg [7:0] response[0:19];
    integer response_len=0,i;
    reg [7:0] checked_crc;
    always #5 clk=~clk;
    front_panel_five_keys #(.DEBOUNCE_CYCLES(2),
        .LONG_PRESS_CYCLES(20),.DEPTH_EDIT_TIMEOUT_CYCLES(20),
        .REMOTE_CONTROL(1)) panel (
        .clk(clk),.rst_n(rst_n),.bank_down_n(1'b1),
        .bank_up_n(1'b1),.timbre_n(1'b1),.song_back_n(1'b1),
        .play_pause_n(1'b1),.enc_s1_n(1'b1),.enc_s2_n(1'b1),
        .enc_key_n(1'b1),.remote_valid(remote_valid),
        .remote_type(remote_type),.remote_value(remote_value),.remote_payload(56'd0),
        .bank(bank),.timbre_select(timbre),.ui_state(ui_state),
        .song_index(song),.song_selected(selected),
        .volume_level(volume),.vibrato_enabled(vibrato),
        .vibrato_depth(depth),.depth_edit(depth_edit),
        .guide_led_on(led_on),.guide_led_blink(led_blink)
    );
    ble_control_endpoint dut (
        .clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),
        .write_enable(write_enable),.bank(bank),.timbre(timbre),
        .volume(volume),.vibrato(vibrato),.ui_state(ui_state),
        .song_index(song),.guide_step(11'd0),.guide_target(3'd0),
        .guide_target_bank(3'd0),.playback_state(2'd0),.vibrato_depth(depth),
        .bend(8'd128),.led_mode(2'd0),.effect_mask(3'd0),.oled_contrast(8'h7f),
        .pad_mask(7'd0),.telemetry(72'd0),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.tx_valid(tx_valid),
        .tx_byte(tx_byte),.tx_ready(1'b1)
    );
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
            c=crc_next(0,8'h01);
            c=crc_next(c,typ);c=crc_next(c,seq);c=crc_next(c,len);
            send_byte(8'hA5);send_byte(8'h01);send_byte(typ);
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
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        send_frame(8'h01,8'h21,0,0);collect();
        if(response_len!=15||response[2]!=8'h80||response[3]!=8'h21||response[4]!=9||
           response[5]!=0||response[7]!=16||response[13]!=1||response[14]!=8'hCE)
            $fatal(1,"initial STATE wrong len=%0d bank=%0d vol=%0d",response_len,response[5],response[7]);
        send_frame(8'h10,8'h22,1,25);collect();
        if(volume!=25||response[7]!=25||response[3]!=8'h22)
            $fatal(1,"SET_VOLUME not acknowledged after update vol=%0d rsp=%0d",volume,response[7]);
        send_frame(8'h11,8'h23,1,4);collect();
        if(bank!=4||response[5]!=4)$fatal(1,"SET_BANK failed");
        write_enable=0;
        send_frame(8'h01,8'h26,0,0);collect();
        if(response_len!=15||response[13]!=0)
            $fatal(1,"locked state must report write_allowed=0");
        checked_crc=0;
        for (i=1;i<14;i=i+1) checked_crc=crc_next(checked_crc,response[i]);
        if (response[14]!=checked_crc) $fatal(1,"STATE CRC invalid");
        send_frame(8'h10,8'h24,1,3);collect();
        if(volume!=25||response_len!=7||response[2]!=8'hE0||response[5]!=4)
            $fatal(1,"unauthorized write accepted");
        write_enable=1;
        send_frame(8'h11,8'h25,1,5);collect();
        if(bank!=4||response[5]!=3)$fatal(1,"invalid bank accepted");
        $display("PASS: BLE state query, absolute settings, ACK-after-apply, authorization, bounds");
        $finish;
    end
endmodule
