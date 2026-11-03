`timescale 1ns/1ps
module tb_front_panel_remote_auth;
    reg clk=0,rst_n=0;
    reg k4=1,k5=1,remote_valid=0;
    wire [1:0] ui_state;
    wire auth_pending,remote_write_allowed;
    always #5 clk=~clk;
    front_panel_five_keys #(
        .DEBOUNCE_CYCLES(2),.LONG_PRESS_CYCLES(12),
        .AUTH_CONFIRM_CYCLES(80),.AUTH_WINDOW_CYCLES(100),
        .REMOTE_CONTROL(1)
    ) dut (
        .clk(clk),.rst_n(rst_n),
        .bank_down_n(1'b1),.bank_up_n(1'b1),
        .timbre_n(1'b1),.song_back_n(k4),.play_pause_n(k5),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(remote_valid),.remote_type(8'h19),.remote_value(8'h00),
        .ui_state(ui_state),.auth_pending(auth_pending),
        .remote_write_allowed(remote_write_allowed)
    );
    task tap_k4;
        begin
            @(negedge clk); k4=0;
            repeat(6) @(negedge clk);
            k4=1;
            repeat(6) @(negedge clk);
        end
    endtask
    task tap_k5;
        begin
            @(negedge clk); k5=0;
            repeat(6) @(negedge clk);
            k5=1;
            repeat(6) @(negedge clk);
        end
    endtask
    task heartbeat;
        begin
            @(negedge clk); remote_valid=1;
            @(negedge clk); remote_valid=0;
        end
    endtask
    integer beat;
    initial begin
        repeat(4) @(negedge clk); rst_n=1;
        tap_k4();
        if (ui_state!=1 || auth_pending || remote_write_allowed)
            $fatal(1,"short K4 must only open song list");
        @(negedge clk); k4=0;
        repeat(23) @(negedge clk);
        if (!auth_pending || remote_write_allowed)
            $fatal(1,"long K4 must show prompt, not grant");
        k4=1;
        repeat(6) @(negedge clk);
        if (!auth_pending || ui_state!=1)
            $fatal(1,"long K4 release must retain prompt and list");
        tap_k5();
        if (auth_pending || !remote_write_allowed || ui_state!=1)
            $fatal(1,"K5 must grant without starting guide");
        for (beat=0;beat<4;beat=beat+1) begin
            repeat(70) @(negedge clk);
            heartbeat();
            if (!remote_write_allowed) $fatal(1,"heartbeat did not renew grant");
        end
        repeat(105) @(negedge clk);
        if (remote_write_allowed) $fatal(1,"grant must expire");
        @(negedge clk); k4=0;
        repeat(23) @(negedge clk);
        k4=1;
        repeat(6) @(negedge clk);
        if (!auth_pending) $fatal(1,"second prompt absent");
        tap_k4();
        if (auth_pending || remote_write_allowed)
            $fatal(1,"short K4 must cancel without grant");
        $display("PASS: local BLE consent prompt, heartbeat renewal, expiry, K4 cancel");
        $finish;
    end
endmodule
