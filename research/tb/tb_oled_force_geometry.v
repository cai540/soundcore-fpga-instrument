`timescale 1ns/1ps
module tb_oled_force_geometry;
    reg clk=0;
    tri1 scl,sda;
    wire ready,nack;
    reg [34:0] levels=0;
    integer i;
    oled_status_ssd1315 dut (
        .clk(clk),.rst_n(1'b0),.bank(3'd0),.timbre(1'b1),
        .volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
        .guide_step(11'd0),.guide_target_bank(3'd0),.playback_state(2'd0),.guide_target(3'd0),
        .auth_pending(1'b0),.remote_write_allowed(1'b0),
        .ble_frame_seen(1'b0),.pad_active(7'd0),
        .force_levels(56'd0),.contrast(8'h7f),
        .oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack)
    );
    initial begin
        for (i=0;i<7;i=i+1) begin
            levels=0;
            levels[i*5 +: 5]=5'd24;
            if (dut.force_column(3'd4,16*i+5,levels)!=8'hff ||
                dut.force_column(3'd6,16*i+5,levels)!=8'hff ||
                dut.force_column(3'd7,16*i+5,levels)!=0 ||
                dut.force_column(3'd4,16*i+4,levels)!=0 ||
                dut.force_column(3'd4,16*i+15,levels)!=0)
                $fatal(1,"meter %0d is not centered or full height",i);
        end
        if (dut.force_column(3'd7,7'd9,35'd0)!=8'h7f ||
            dut.force_column(3'd7,7'd25,35'd0)!=8'h51 ||
            dut.force_column(3'd7,7'd104,35'd0)!=8'h71)
            $fatal(1,"full-size number glyphs missing");
        $display("PASS: seven aligned 24-pixel meters and full-size labels");
        $finish;
    end
endmodule
