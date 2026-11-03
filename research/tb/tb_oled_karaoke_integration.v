`timescale 1ns/1ps
// Exercise the real OLED transaction scheduler, not only the glyph renderer.
module tb_oled_karaoke_integration;
    reg clk=0,rst_n=0,lyric_mode=0;
    reg [6:0] phrase=0;
    reg [4:0] character=7;
    reg [7:0] progress=128;
    reg [55:0] force_levels=0;
    tri1 scl,sda;
    wire ready,nack;
    reg [7:0] baseline[0:511],golden[0:511];
    integer count,frame,fd;
    reg [1023:0] path;
    always #5 clk=~clk;
    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(200000),.LYRIC_OVERLAY(1)) dut(
        .clk(clk),.rst_n(rst_n),.bank(3'd0),.timbre(1'b0),.volume(5'd0),.vibrato(1'b0),
        .ui_state(2'd0),.guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd0),.auth_pending(1'b0),.remote_write_allowed(1'b0),.ble_frame_seen(1'b0),
        .pad_active(7'd0),.force_levels(force_levels),.contrast(8'h7f),
        .lyric_mode(lyric_mode),.lyric_phrase(phrase),.lyric_character(character),.lyric_progress(progress),
        .oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
    assign sda=(dut.writer.state==4 || dut.writer.state==5 || dut.writer.state==9) ? 1'b0:1'bz;
    initial begin #50000000;$fatal(1,"OLED karaoke integration timeout");end
    initial begin
        $readmemh("build/karaoke_oled_2.hex",golden);
        repeat(3)@(negedge clk);rst_n=1;
        for(frame=0;frame<3;frame=frame+1)begin
            wait(dut.tx_start && dut.phase==2 && dut.page_index==0 && dut.column==0);
            @(negedge clk);
            $sformat(path,"build/karaoke_i2c_frame_%0d.hex",frame);fd=$fopen(path,"w");
            count=0;
            while(count<1024)begin
                if(dut.tx_start && dut.phase==2)begin
                    if(dut.page_index*128+dut.column!=count)$fatal(1,"skipped OLED byte");
                    $fdisplay(fd,"%02x",dut.tx_payload);
                    if(count<512)begin
                        if(frame==0)baseline[count]=dut.tx_payload;
                        if(frame==1 && dut.tx_payload!==golden[count])
                            $fatal(1,"lyric pipeline stale frame byte=%0d got=%h expected=%h",count,dut.tx_payload,golden[count]);
                        if(frame==2 && dut.tx_payload!==baseline[count])
                            $fatal(1,"configuration not restored byte=%0d",count);
                    end else if(dut.tx_payload!==dut.force_column(dut.page_index,dut.column,dut.shown_force_buckets))
                        $fatal(1,"lyric mode damaged lower force/number rows");
                    // Exit requested in the middle of a lyric frame must wait
                    // for the next snapshot, never mix lyric/config columns.
                    if(frame==1 && count==200)lyric_mode=0;
                    count=count+1;
                end
                @(negedge clk);
            end
            $fclose(fd);
            wait(dut.phase==3);@(negedge clk);
            if(frame==0)begin
                lyric_mode=1;
                force_levels={8'd224,8'd192,8'd64,8'd160,8'd96,8'd32,8'd128};
            end
        end
        if(nack)$fatal(1,"unexpected NACK");
        $display("PASS: complete I2C lyric frame matches golden; mid-frame exit coherent; configuration and force labels restored");$finish;
    end
endmodule
