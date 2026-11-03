`timescale 1ns/1ps
// Slave observes only the external bus; it keeps its bit state across FPGA reset.
module tb_oled_pin_recovery #(parameter integer EXPECT_ALL_PIXELS=0);
    reg clk=0,rst_n=0,present=1;
    always #5 clk=~clk;
    tri1 scl,sda;
    reg slave_low=0,receiving=0,selected=0;
    reg [7:0] shift=0,control=0,address=8'h78;
    integer bit_count=0,byte_count=0,ae_count=0,af_count=0,data_count=0;
    integer all_on_count=0;
    integer idle_clocks=0,first_start_clocks=-1,cycles=0,first_start_cycle=0;
    wire ready,nack;
    assign sda=slave_low ? 1'b0:1'bz;
    oled_status_ssd1315 #(.I2C_DIV(2),.POWERUP_CYCLES(80),.REFRESH_CYCLES(300)) dut(
        .clk(clk),.rst_n(rst_n),.bank(3'd0),.timbre(1'b1),.volume(5'd6),.vibrato(1'b0),
        .ui_state(2'd0),.guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd0),.auth_pending(1'b0),.remote_write_allowed(1'b0),.ble_frame_seen(1'b0),
        .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),.lyric_mode(1'b0),
        .lyric_phrase(7'd0),.lyric_character(5'd0),.lyric_progress(8'd0),.capture_payload(88'd0),
        .oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
    always @(posedge clk) cycles=cycles+1;
    always @(negedge sda) if(scl===1'b1)begin
        receiving=1;selected=0;bit_count=0;byte_count=0;shift=0;
        if(first_start_clocks<0)begin first_start_clocks=idle_clocks;first_start_cycle=cycles;end
    end
    always @(posedge sda) if(scl===1'b1)begin
        receiving=0;selected=0;bit_count=0;byte_count=0;
    end
    always @(posedge scl)begin
        if(!receiving)idle_clocks=idle_clocks+1;
        else if(bit_count<8)begin
            shift={shift[6:0],sda};bit_count=bit_count+1;
            if(bit_count==8)begin
                if(byte_count==0)selected=present && shift==address;
                else if(selected && present)begin
                    if(byte_count==1)control=shift;
                    if(byte_count==2 && control==0)begin
                        if(shift==8'hAE)ae_count=ae_count+1;
                        if(shift==8'hA5)all_on_count=all_on_count+1;
                        if(shift==8'hAF)af_count=af_count+1;
                    end
                    if(byte_count==2 && control==8'h40)data_count=data_count+1;
                end
            end
        end else begin bit_count=0;byte_count=byte_count+1;end
    end
    always @(negedge scl)slave_low=receiving && present && selected && bit_count==8;
    integer ae_before,af_before;
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        wait(ready);
        if(EXPECT_ALL_PIXELS && all_on_count!=1)$fatal(1,"all-pixels A5 command missing from actual I2C bus");
        if(first_start_cycle<80 || first_start_clocks<9 || ae_count!=1 || af_count!=1 || data_count<1024)
            $fatal(1,"cold boot/pin decode failed wait=%0d clear=%0d AE=%0d AF=%0d data=%0d",first_start_cycle,first_start_clocks,ae_count,af_count,data_count);
        ae_before=ae_count;af_before=af_count;
        // The panel remains powered, holding ACK low, when only the FPGA resets.
        wait(slave_low && scl===1'b0);
        @(negedge clk);rst_n=0;
        repeat(4)@(negedge clk);rst_n=1;
        wait(ready);
        if(ae_count<=ae_before || af_count<=af_before)$fatal(1,"warm reload did not replay full display init");
        present=0;wait(!ready);
        repeat(600)@(negedge clk);present=1;address=8'h7A;
        wait(ready);
        if(dut.oled_address!=8'h7A || !nack)$fatal(1,"late power/alternate address did not recover");
        $display("PASS: pin-level slave, power wait, >=9 clear clocks, full init+1024 bytes, interrupted ACK reload, late power and 0x3D recovery");
        $finish;
    end
    initial begin #25000000;$fatal(1,"pin recovery timeout ready=%b phase=%d writer=%d AE=%0d AF=%0d data=%0d",ready,dut.phase,dut.writer.state,ae_count,af_count,data_count);end
endmodule
