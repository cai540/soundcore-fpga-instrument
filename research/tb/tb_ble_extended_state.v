`timescale 1ns/1ps
module tb_ble_extended_state;
    reg clk=0, rst_n=0, rx_valid=0;
    reg [7:0] rx_byte=0;
    wire tx_valid, remote_valid;
    wire [7:0] tx_byte, remote_type, remote_value;
    reg [7:0] response [0:19];
    integer n=0, i;
    reg [7:0] crc;
    reg saw_effect_command=0;
    always #5 clk=~clk;
    always @(posedge clk) if(remote_valid && remote_type==8'h22 &&
                             remote_value==8'h03) saw_effect_command<=1;

    ble_control_endpoint #(.EXTENDED_STATE(1)) dut (
        .clk(clk), .rst_n(rst_n), .rx_valid(rx_valid), .rx_byte(rx_byte),
        .write_enable(1'b1), .bank(3'd4), .timbre(1'b1), .volume(5'd25),
        .vibrato(1'b1), .ui_state(2'd2), .song_index(8'd1),
        .guide_step(11'd3), .guide_target(3'd6), .vibrato_depth(4'd7),
        .guide_target_bank(3'd0),.playback_state(2'd0),.telemetry(72'd0),
        .bend(8'd128), .led_mode(2'd2), .effect_mask(3'b101),
        .oled_contrast(8'd200),
        .pad_mask(7'h55), .remote_valid(remote_valid),
        .remote_type(remote_type), .remote_value(remote_value),
        .tx_valid(tx_valid), .tx_byte(tx_byte), .tx_ready(1'b1)
    );

    function [7:0] crc_next;
        input [7:0] old, data;
        reg [7:0] c;
        integer j;
        begin
            c=old^data;
            for(j=0;j<8;j=j+1) c=c[7] ? (c<<1)^8'h07 : (c<<1);
            crc_next=c;
        end
    endfunction

    task send_byte;
        input [7:0] b;
        begin
            @(negedge clk); rx_byte=b; rx_valid=1;
            @(negedge clk); rx_valid=0;
        end
    endtask

    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        send_byte(8'hA5); send_byte(8'h01); send_byte(8'h01);
        send_byte(8'h21); send_byte(8'h00); send_byte(8'hC6);
        wait(tx_valid);
        while(tx_valid) begin
            @(posedge clk); response[n]=tx_byte; n=n+1;
            @(negedge clk);
        end
        if(n!=20 || response[2]!=8'h80 || response[4]!=14 ||
           response[5]!=4 || response[13]!=1 || response[14]!=7 ||
           response[15]!=128 || response[16]!=22 || response[17]!=200 ||
           response[18]!=8'h55)
            $fatal(1,"extended STATE mismatch length=%0d",n);
        crc=0;
        for(i=1;i<19;i=i+1) crc=crc_next(crc,response[i]);
        if(response[19]!=crc) $fatal(1,"extended STATE CRC mismatch");
        n=0;
        crc=0;
        crc=crc_next(crc,8'h01);crc=crc_next(crc,8'h22);
        crc=crc_next(crc,8'h22);crc=crc_next(crc,8'h01);
        crc=crc_next(crc,8'h03);
        send_byte(8'hA5);send_byte(8'h01);send_byte(8'h22);
        send_byte(8'h22);send_byte(8'h01);send_byte(8'h03);
        send_byte(crc);
        wait(tx_valid);
        while(tx_valid) begin
            @(posedge clk);response[n]=tx_byte;n=n+1;
            @(negedge clk);
        end
        if(!saw_effect_command || n!=20 || response[2]!=8'h80)
            $fatal(1,"SET_EFFECTS was not accepted");
        $display("PASS: BLE extended STATE, effect bits and SET_EFFECTS");
        $finish;
    end
endmodule
