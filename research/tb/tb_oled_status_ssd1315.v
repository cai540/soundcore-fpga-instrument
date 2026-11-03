`timescale 1ns/1ps
module tb_oled_status_ssd1315;
    reg clk=0, rst_n=0, slave_ack=0;
    reg [2:0] bank=0, target=0;
    reg timbre=1, vibrato=0;
    reg [4:0] volume=16;
    reg [1:0] ui_state=0;
    reg [3:0] guide_step=0;
    reg auth_pending=0,remote_write_allowed=0;
    reg ble_frame_seen=0;
    reg [6:0] pad_active=0;
    reg [7:0] contrast=8'h7f;
    tri1 scl,sda;
    wire ready,nack_seen;
    integer writes=0, init_ae=0, saw_bank1=0, saw_bank5=0;
    integer saw_auth_prompt=0,saw_auth_open=0;
    integer saw_contrast_cmd=0,saw_contrast_value=0;
    reg [6:0] saw_pad_columns=0;
    integer pad_i;
    always #5 clk=~clk;
    oled_status_ssd1315 #(.I2C_DIV(2),.REFRESH_CYCLES(300),
                          .PAD_HOLD_CYCLES(250000),
                          .BLE_IDLE_CYCLES(200000)) dut (
        .clk(clk),.rst_n(rst_n),.bank(bank),.timbre(timbre),
        .volume(volume),.vibrato(vibrato),.ui_state(ui_state),
        .guide_step(guide_step),.guide_target_bank(3'd0),.playback_state(2'd0),.guide_target(target),
        .auth_pending(auth_pending),.remote_write_allowed(remote_write_allowed),
        .ble_frame_seen(ble_frame_seen),
        .pad_active(pad_active),.force_levels(56'd0),.contrast(contrast),
        .oled_scl(scl),.oled_sda(sda),.ready(ready),
        .nack_seen(nack_seen)
    );
    assign sda = slave_ack && (dut.writer.state==4 || dut.writer.state==5 || dut.writer.state==9)
                 ? 1'b0 : 1'bz;
    always @(posedge clk) if (rst_n && dut.tx_start) begin
        writes=writes+1;
        if (dut.phase==0 && dut.tx_payload==8'hAE) init_ae=init_ae+1;
        if (dut.phase==4 && dut.tx_payload==8'h81) saw_contrast_cmd=1;
        if (dut.phase==5 && dut.tx_payload==8'd200) saw_contrast_value=1;
        if (dut.phase==2 && dut.page_index==0 && dut.column==34) begin
            if (dut.tx_payload==8'h30) saw_bank1=1;
            if (dut.tx_payload==8'hF8) saw_bank5=1;
        end
        if (dut.phase==2 && dut.page_index==4 && dut.column==0 &&
            dut.hanzi_at(2,0)==19)
            saw_auth_prompt=1;
        if (dut.phase==2 && dut.page_index==4 && dut.column==32 &&
            dut.hanzi_at(2,2)==16)
            saw_auth_open=1;
        if (dut.phase==2 && dut.page_index==7 && dut.pad_visible==7'b1010101)
            for (pad_i=0;pad_i<7;pad_i=pad_i+1)
                if (dut.column==4+17*pad_i &&
                    dut.tx_payload==((7'b1010101 >> pad_i) & 1 ? 8'h7E : 8'h42))
                    saw_pad_columns[pad_i]=1;
    end
    initial begin
        #6000000; $fatal(1,"OLED timeout writes=%0d bank1=%0d bank5=%0d prompt=%0d open=%0d pads=%b contrast=%0d",
                          writes,saw_bank1,saw_bank5,saw_auth_prompt,saw_auth_open,saw_pad_columns,saw_contrast_value);
    end
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        // First address NACK must force retry of the same initialization byte.
        wait(dut.writer.done);
        @(negedge clk); slave_ack=1;
        wait(ready);
        if (!nack_seen || init_ae<2 || writes<1000 || !saw_bank1)
            $fatal(1,"OLED init/retry/frame failed writes=%0d ae=%0d bank1=%0d",writes,init_ae,saw_bank1);
        bank=4; volume=31; timbre=0; target=6;
        wait(saw_bank5);
        ui_state=2;
        auth_pending=1;
        wait(saw_auth_prompt);
        auth_pending=0; remote_write_allowed=1;
        ble_frame_seen=1; repeat(3) @(negedge clk); ble_frame_seen=0;
        wait(saw_auth_open);
        pad_active=7'b1010101;
        repeat(3) @(negedge clk); pad_active=0;
        wait(&saw_pad_columns);
        contrast=8'd200;
        wait(saw_contrast_value);
        if(!saw_contrast_cmd || init_ae!=2)
            $fatal(1,"OLED live contrast caused reinitialization");
        $display("PASS: SSD1315 init, NACK retry, live contrast, status and seven-pad display");
        $finish;
    end
endmodule
