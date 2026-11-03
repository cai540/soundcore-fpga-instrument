`timescale 1ns/1ps
module tb_ble_telemetry_scene;
    reg clk=0,rst_n=0,rx_valid=0;
    reg [7:0] rx_byte=0;
    wire remote_valid,tx_valid;
    wire [7:0] remote_type,remote_value,tx_byte;
    wire [55:0] remote_payload;
    wire [2:0] bank;
    wire timbre,vibrato;
    wire [4:0] volume;
    wire [3:0] depth;
    wire [7:0] song;
    wire [1:0] ui_state;
    reg [7:0] response[0:19];
    integer n,i;
    reg [55:0] payload;
    reg [7:0] crc;
    always #5 clk=~clk;
    front_panel_five_keys #(.REMOTE_CONTROL(1),.DEBOUNCE_CYCLES(2)) panel (
        .clk(clk),.rst_n(rst_n),.bank_down_n(1'b1),.bank_up_n(1'b1),
        .timbre_n(1'b1),.song_back_n(1'b1),.play_pause_n(1'b1),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.remote_payload(remote_payload),
        .bank(bank),.timbre_select(timbre),.volume_level(volume),
        .vibrato_enabled(vibrato),.vibrato_depth(depth),
        .song_index(song),.ui_state(ui_state)
    );
    ble_control_endpoint #(.EXTENDED_STATE(1)) dut (
        .clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),
        .write_enable(1'b1),.bank(bank),.timbre(timbre),.volume(volume),
        .vibrato(vibrato),.ui_state(ui_state),.song_index(song),
        .guide_step(11'd0),.guide_target(3'd0),.vibrato_depth(depth),
        .bend(8'd128),.led_mode(2'd2),.oled_contrast(8'd200),
        .pad_mask(7'h55),.telemetry({8'h55,64'h8877665544332211}),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.remote_payload(remote_payload),
        .tx_valid(tx_valid),.tx_byte(tx_byte),.tx_ready(1'b1)
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
        begin @(negedge clk);rx_byte=b;rx_valid=1;
              @(negedge clk);rx_valid=0; end
    endtask
    task send_frame;
        input [7:0] typ,seq,len;
        input [55:0] data;
        reg [7:0] c;
        integer k;
        begin
            c=crc_next(0,1);c=crc_next(c,typ);c=crc_next(c,seq);
            c=crc_next(c,len);
            send_byte(8'hA5);send_byte(1);send_byte(typ);
            send_byte(seq);send_byte(len);
            for(k=0;k<len;k=k+1)begin
                send_byte(data[8*k +: 8]);c=crc_next(c,data[8*k +: 8]);
            end
            send_byte(c);
        end
    endtask
    task collect;
        begin
            n=0;wait(tx_valid);
            while(tx_valid)begin
                @(posedge clk);response[n]=tx_byte;n=n+1;@(negedge clk);
            end
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        send_frame(8'h20,8'h30,0,0);collect();
        if(n!=15||response[2]!=8'h81||response[4]!=9||
           response[5]!=8'h11||response[12]!=8'h88||response[13]!=8'h55)
            $fatal(1,"telemetry bytes wrong");
        crc=0;for(i=1;i<14;i=i+1)crc=crc_next(crc,response[i]);
        if(response[14]!=crc)$fatal(1,"telemetry CRC wrong");
        payload={8'd200,8'd2,8'd7,8'd1,8'd24,8'd1,8'd3};
        send_frame(8'h1f,8'h31,7,payload);collect();
        if(n!=20||response[2]!=8'h80||bank!=3||timbre!=1||
           volume!=24||vibrato!=1||depth!=7||response[5]!=3||
           response[7]!=24||response[14]!=7)
            $fatal(1,"scene was not applied atomically");
        payload={8'd200,8'd2,8'd7,8'd1,8'd32,8'd1,8'd4};
        send_frame(8'h1f,8'h32,7,payload);collect();
        if(response[2]!=8'hE0||response[5]!=3||bank!=3||volume!=24)
            $fatal(1,"invalid scene changed settings");
        $display("PASS: BLE telemetry CRC, atomic scene and invalid-scene rejection");
        $finish;
    end
endmodule
