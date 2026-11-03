`timescale 1ns/1ps
module tb_front_panel_auto_ble;
    reg clk=0,rst_n=0,remote_valid=0;
    reg [7:0] remote_type=0,remote_value=0;
    wire [4:0] volume;
    wire auth_pending,panel_write_allowed;
    always #5 clk=~clk;
    front_panel_five_keys #(.DEBOUNCE_CYCLES(2),
        .REMOTE_CONTROL(1),.PANEL_AUTH_REQUIRED(0)) dut (
        .clk(clk),.rst_n(rst_n),
        .bank_down_n(1'b1),.bank_up_n(1'b1),.timbre_n(1'b1),
        .song_back_n(1'b1),.play_pause_n(1'b1),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(remote_valid),.remote_type(remote_type),
        .remote_value(remote_value),.remote_payload(56'd0),
        .volume_level(volume),.auth_pending(auth_pending),
        .remote_write_allowed(panel_write_allowed)
    );
    initial begin
        repeat(4) @(negedge clk); rst_n=1;
        @(negedge clk); remote_type=8'h10;remote_value=8'd25;remote_valid=1;
        @(negedge clk); remote_valid=0;
        repeat(3) @(negedge clk);
        if(volume!=25 || auth_pending || panel_write_allowed)
            $fatal(1,"automatic BLE mode must accept command without panel consent");
        $display("PASS: remote control requires no uninstalled K4/K5 authorization");
        $finish;
    end
endmodule
