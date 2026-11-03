`timescale 1ns/1ps
module tb_oled_product_text;
    tri1 scl,sda;
    wire ready,nack;
    oled_status_ssd1315 dut (
        .clk(1'b0),.rst_n(1'b0),.bank(3'd0),.timbre(1'b1),
        .volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
        .guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd0),.auth_pending(1'b0),.remote_write_allowed(1'b0),
        .ble_frame_seen(1'b0),.pad_active(7'd0),.force_levels(56'd0),
        .contrast(8'h7f),.oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
    integer page,col,fd;
    reg [255:0] bitmap;
    reg [7:0] value;
    reg [34:0] levels;
    initial begin
        force dut.shown_bank=0;force dut.shown_timbre=1;
        force dut.shown_volume=16;force dut.shown_vibrato=0;
        force dut.shown_ble_recent=0;
        #1;
        if(dut.hanzi_at(1,0)!=5 || dut.hanzi_at(1,1)!=6 ||
           dut.hanzi_at(1,3)!=12 || dut.hanzi_at(1,4)!=13 ||
           dut.hanzi_at(1,5)!=14 || dut.hanzi_at(1,6)!=15 || dut.hanzi_at(1,7)!=0)
            $fatal(1,"waiting text must be harmonica / Bluetooth waiting");
        force dut.shown_ble_recent=1;
        #1;
        if(dut.hanzi_at(1,5)!=16 || dut.hanzi_at(1,6)!=17 || dut.hanzi_at(1,7)!=18)
            $fatal(1,"connected text must include the whole Bluetooth prefix");
        levels={5'd24,5'd18,5'd8,5'd24,5'd12,5'd6,5'd20};
        fd=$fopen("build/fx_review/oled_frame.hex","w");
        for(page=0;page<8;page=page+1)
            for(col=0;col<128;col=col+1)begin
                if(page<4)begin
                    bitmap=dut.hanzi_bitmap(dut.hanzi_at(page/2,col/16));
                    value=page%2 ? bitmap[(15-col%16)*8 +:8] : bitmap[128+(15-col%16)*8 +:8];
                end else value=dut.force_column(page,col,levels);
                $fdisplay(fd,"%02x",value);
            end
        $fclose(fd);
        $display("PASS: complete Chinese Bluetooth text, snapshot saved");$finish;
    end
endmodule
