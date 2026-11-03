`timescale 1ns/1ps
// The purchased OLED carrier marks both 0x78 and 0x7A write addresses.
// A slave that ACKs only 0x7A must still reach a completed status frame.
module tb_oled_dual_address;
    reg clk=0, rst_n=0;
    reg [2:0] bank=0, guide_target=0;
    reg [4:0] volume=16;
    reg [1:0] ui_state=0;
    reg [10:0] guide_step=0;
    reg [6:0] pad_active=0;
    tri1 scl,sda;
    wire ready,nack_seen;
    integer address_78_count=0,address_7a_count=0;
    always #5 clk=~clk;
    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(300),
                          .PAD_HOLD_CYCLES(20)) dut (
        .clk(clk),.rst_n(rst_n),.bank(bank),.timbre(1'b1),
        .volume(volume),.vibrato(1'b0),.ui_state(ui_state),
        .guide_step(guide_step),.guide_target_bank(3'd0),.playback_state(2'd0),.guide_target(guide_target),
        .auth_pending(1'b0),.remote_write_allowed(1'b0),
        .ble_frame_seen(1'b0),
        .pad_active(pad_active),.force_levels(56'd0),.contrast(8'h7f),.oled_scl(scl),.oled_sda(sda),
        .ready(ready),.nack_seen(nack_seen)
    );
    // Address byte gets an ACK only when it is 0x7A. Once selected, all
    // control/payload bytes are ACKed as well.
    assign sda = (dut.writer.state==4 || dut.writer.state==5 || dut.writer.state==9) &&
                 (dut.writer.byte_index!=0 || dut.writer.shift_byte==8'h7A)
                 ? 1'b0 : 1'bz;
    always @(posedge clk) if (rst_n && dut.tx_start && dut.phase==0) begin
        if (dut.oled_address==8'h78) address_78_count=address_78_count+1;
        if (dut.oled_address==8'h7A) address_7a_count=address_7a_count+1;
    end
    initial begin
        #5000000;
        $fatal(1,"alternate OLED address did not reach ready");
    end
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        wait(ready);
        if (!nack_seen || address_78_count<2 || address_7a_count<1 ||
            dut.oled_address!=8'h7A)
            $fatal(1,"OLED address probe failed 78=%0d 7A=%0d",address_78_count,address_7a_count);
        $display("PASS: OLED auto-probes 0x78 and 0x7A");
        $finish;
    end
endmodule
