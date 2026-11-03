`timescale 1ns/1ps
module tb_oled_ble_stable;
    reg clk=0,rst_n=0,frame_seen=0;
    tri1 scl,sda;
    wire ready,nack;
    always #5 clk=~clk;
    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(100),
        .PAD_HOLD_CYCLES(10),.BLE_IDLE_CYCLES(1000)) dut (
        .clk(clk),.rst_n(rst_n),.bank(3'd0),.timbre(1'b1),
        .volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
        .guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),
        .playback_state(2'd0),.force_levels(56'd0),
        .auth_pending(1'b0),.remote_write_allowed(1'b0),
        .ble_frame_seen(frame_seen),.pad_active(7'd0),
        .contrast(8'h7f),.oled_scl(scl),.oled_sda(sda),
        .ready(ready),.nack_seen(nack)
    );
    assign sda = (dut.writer.state==4 || dut.writer.state==5 ||
                  dut.writer.state==9) ? 1'b0 : 1'bz;
    task pulse_frame;
        begin
            @(negedge clk);frame_seen=1;
            @(negedge clk);frame_seen=0;
        end
    endtask
    integer i;
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        if(dut.hanzi_at(2,2)!=14) $fatal(1,"initial BLE status not waiting");
        pulse_frame();
        for(i=0;i<4;i=i+1) begin
            repeat(600) @(negedge clk);
            if(!dut.ble_recent || dut.ble_idle_left==0)
                $fatal(1,"valid periodic traffic must keep connected state stable");
            pulse_frame();
        end
        repeat(1005) @(negedge clk);
        if(dut.ble_recent) $fatal(1,"stale BLE status did not expire");
        $display("PASS: BLE status remains connected across polling, then times out");
        $finish;
    end
endmodule
