`timescale 1ns/1ps
// A display that resets or is reconnected at the alternate I2C address
// must be reinitialized rather than left with a partial data page.
module tb_oled_reconnect;
    reg clk=0, rst_n=0;
    reg [7:0] active_address=8'h78;
    tri1 scl,sda;
    wire ready,nack_seen;
    integer init_ae=0;
    always #5 clk=~clk;

    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(300),
                          .PAD_HOLD_CYCLES(20)) dut (
        .clk(clk),.rst_n(rst_n),.bank(3'd0),.timbre(1'b1),
        .volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
        .guide_step(11'd0),.guide_target_bank(3'd0),.playback_state(2'd0),.guide_target(3'd0),
        .auth_pending(1'b0),.remote_write_allowed(1'b0),
        .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),.oled_scl(scl),.oled_sda(sda),
        .ready(ready),.nack_seen(nack_seen)
    );
    assign sda = (dut.writer.state==4 || dut.writer.state==5 || dut.writer.state==9) &&
                 (dut.writer.byte_index!=0 || dut.writer.shift_byte==active_address)
                 ? 1'b0 : 1'bz;
    always @(posedge clk) if (rst_n && dut.tx_start && dut.phase==0 &&
                             dut.tx_payload==8'hAE)
        init_ae=init_ae+1;

    initial begin
        #15000000;
        $fatal(1,"OLED reconnect timeout: ready=%b address=%h init=%0d",
               ready,dut.oled_address,init_ae);
    end
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        wait(ready);
        if (dut.oled_address!=8'h78) $fatal(1,"initial OLED address wrong");
        active_address=8'h7A;
        wait(!ready);
        wait(ready);
        if (dut.oled_address!=8'h7A || init_ae<2 || !nack_seen)
            $fatal(1,"OLED did not reinitialize after address change");
        $display("PASS: OLED reinitializes and reprobes after live NACKs");
        $finish;
    end
endmodule
