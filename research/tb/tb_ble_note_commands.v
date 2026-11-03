`timescale 1ns/1ps
module tb_ble_note_commands;
    reg clk=0,rst_n=0,rx_valid=0,write_enable=1;
    reg [7:0] rx_byte=0;
    wire remote_valid,tx_valid;
    wire [7:0] remote_type,remote_value,remote_value2,tx_byte;
    reg [7:0] response[0:19];
    integer count=0,n=0;
    always #5 clk=~clk;
    always @(posedge clk) if(remote_valid) begin
        count=count+1;
        if(remote_type==8'h16 &&
           (remote_value!=0 || remote_value2!=8'd180))
            $fatal(1,"NOTE_ON payload mismatch");
    end
    ble_control_endpoint dut (
        .clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),
        .write_enable(write_enable),.bank(3'd0),.timbre(1'b1),
        .volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
        .song_index(8'd0),.guide_step(4'd0),.guide_target(3'd0),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.remote_value2(remote_value2),
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
        input [7:0] typ,seq,len,a,b;
        reg [7:0] c;
        begin
            c=crc_next(0,1);c=crc_next(c,typ);
            c=crc_next(c,seq);c=crc_next(c,len);
            send_byte(8'hA5);send_byte(1);send_byte(typ);
            send_byte(seq);send_byte(len);
            if(len>=1)begin send_byte(a);c=crc_next(c,a);end
            if(len>=2)begin send_byte(b);c=crc_next(c,b);end
            send_byte(c);
        end
    endtask
    task collect;
        begin
            n=0;wait(tx_valid);
            while(tx_valid)begin
                @(posedge clk);response[n]=tx_byte;n=n+1;
                @(negedge clk);
            end
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        send_frame(8'h16,8'h30,2,0,180);collect();
        if(n!=15 || response[2]!=8'h80 || count!=1)
            $fatal(1,"NOTE_ON not acknowledged once");
        send_frame(8'h16,8'h30,2,0,180);collect();
        if(count!=1) $fatal(1,"repeated SEQ retriggered NOTE_ON");
        send_frame(8'h16,8'h31,2,7,180);collect();
        if(response[2]!=8'hE0 || response[5]!=3 || count!=1)
            $fatal(1,"invalid pad accepted");
        send_frame(8'h17,8'h32,1,0,0);collect();
        if(count!=2 || remote_type!=8'h17)
            $fatal(1,"NOTE_OFF not forwarded");
        send_frame(8'h18,8'h33,0,0,0);collect();
        if(count!=3 || remote_type!=8'h18)
            $fatal(1,"ALL_NOTES_OFF not forwarded");
        write_enable=0;
        send_frame(8'h16,8'h34,2,0,180);collect();
        if(response[2]!=8'hE0 || response[5]!=4 || count!=3)
            $fatal(1,"locked NOTE_ON accepted");
        $display("PASS: BLE phone note commands, bounds, retry and lock");
        $finish;
    end
endmodule
