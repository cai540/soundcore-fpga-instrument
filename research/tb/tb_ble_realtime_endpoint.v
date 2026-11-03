`timescale 1ns/1ps
module tb_ble_realtime_endpoint;
    reg clk=0,rst_n=0,rx_valid=0,tx_ready=0;
    reg [7:0] rx_byte=0;
    always #5 clk=~clk;
    wire remote_valid,tx_valid,activity;
    wire [7:0] typ,value,value2,tx_byte;
    wire [55:0] payload;
    integer accepted=0;
    ble_control_endpoint #(.EXTENDED_STATE(1),.SONG_EXTENSIONS(1),.REALTIME_NOTES(1)) dut(
        .clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),.write_enable(1'b1),
        .bank(3'd0),.timbre(1'b1),.volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
        .song_index(8'd0),.guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd0),.vibrato_depth(4'd4),.bend(8'd128),.led_mode(2'd0),
        .effect_mask(3'd0),.oled_contrast(8'h7f),.pad_mask(7'd0),.telemetry(72'd0),
        .remote_valid(remote_valid),.remote_type(typ),.remote_value(value),.remote_value2(value2),
        .remote_payload(payload),.link_activity(activity),.tx_valid(tx_valid),.tx_byte(tx_byte),.tx_ready(tx_ready));
    function [7:0] crc;
        input [7:0] p,d;
        reg [7:0] c;integer j;
        begin c=p^d;for(j=0;j<8;j=j+1)c=c[7] ? (c<<1)^8'h07:c<<1;crc=c;end
    endfunction
    task byte_send;
        input [7:0] b;
        begin @(negedge clk);rx_byte=b;rx_valid=1;@(negedge clk);rx_valid=0;end
    endtask
    task frame;
        input [7:0] t,s,l;
        input [23:0] p;
        reg [7:0] c;integer k;
        begin
            c=0;byte_send(8'ha5);byte_send(1);c=crc(c,1);
            byte_send(t);c=crc(c,t);byte_send(s);c=crc(c,s);byte_send(l);c=crc(c,l);
            for(k=0;k<l;k=k+1)begin byte_send(p[k*8+:8]);c=crc(c,p[k*8+:8]);end
            byte_send(c);repeat(3)@(negedge clk);
        end
    endtask
    always @(posedge clk)if(remote_valid && typ==8'h24)accepted=accepted+1;
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        frame(1,1,0,0);repeat(5)@(negedge clk);
        if(!tx_valid || !dut.full_state[95])$fatal(1,"state/capability absent");
        frame(8'h24,2,3,{8'd190,8'h45,8'h45});
        if(accepted!=1 || value!=8'h45 || value2!=8'h45 || payload[23:16]!=190)
            $fatal(1,"real-time frame blocked by STATE TX");
        frame(8'h24,2,3,{8'd190,8'h45,8'h45});
        if(accepted!=1)$fatal(1,"duplicate re-attacked");
        frame(8'h24,3,3,{8'd190,8'd0,8'd0});
        if(accepted!=2 || value!=0 || dut.response_seq!=1)$fatal(1,"release/correlated STATE damaged");
        $display("PASS: CRC real-time frames bypass busy STATE response; capability, duplicate and release checked");$finish;
    end
endmodule
