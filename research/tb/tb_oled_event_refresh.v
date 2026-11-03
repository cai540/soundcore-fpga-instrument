`timescale 1ns/1ps
// A button-derived status change must start a new OLED frame without
// waiting for the periodic idle timer to expire.
module tb_oled_event_refresh;
    reg clk=0, rst_n=0;
    reg [2:0] bank=0;
    tri1 scl,sda;
    wire ready,nack_seen;
    integer delay_clocks;
    always #5 clk=~clk;

    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(200000),
                          .PAD_HOLD_CYCLES(50)) dut (
        .clk(clk),.rst_n(rst_n),.bank(bank),.timbre(1'b0),
        .volume(5'd0),.vibrato(1'b0),.ui_state(2'd0),
        .guide_step(11'd0),.guide_target_bank(3'd0),.playback_state(2'd0),.guide_target(3'd0),
        .auth_pending(1'b0),.remote_write_allowed(1'b0),
        .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),.oled_scl(scl),.oled_sda(sda),
        .ready(ready),.nack_seen(nack_seen)
    );
    assign sda = (dut.writer.state==4 || dut.writer.state==5 ||
                  dut.writer.state==9) ? 1'b0 : 1'bz;

    initial begin
        #6000000;
        $fatal(1,"OLED event-refresh timeout");
    end
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        wait(ready);
        @(negedge clk);
        if (dut.phase != 3 || dut.refresh_count > 3)
            $fatal(1,"expected newly idle display");
        bank=1;
        delay_clocks=0;
        while (dut.phase == 3 && delay_clocks < 20) begin
            @(negedge clk);
            delay_clocks=delay_clocks+1;
        end
        if (dut.phase != 1 || delay_clocks >= 20)
            $fatal(1,"status update waited for periodic timer");
        wait(dut.tx_start && dut.phase==2 && dut.page_index==0 && dut.column==34);
        if (dut.tx_payload != 8'h18)
            $fatal(1,"new bank glyph not transmitted");
        $display("PASS: OLED status change starts refresh immediately (%0d clocks)",delay_clocks);
        $finish;
    end
endmodule
