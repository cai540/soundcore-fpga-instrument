`timescale 1ns/1ps
module tb_front_panel_five_keys;
    reg clk = 0, rst_n = 0;
    reg [4:0] buttons_n = 5'b11111;
    reg s1_n = 1, s2_n = 1, key_n = 1;
    wire [2:0] bank;
    wire timbre_select;
    wire [1:0] ui_state;
    wire [7:0] song_index;
    wire song_selected;
    wire [4:0] volume_level;
    wire vibrato_enabled;
    wire [3:0] vibrato_depth;
    wire depth_edit, guide_led_on, guide_led_blink;
    always #5 clk = ~clk;
    front_panel_five_keys #(
        .DEBOUNCE_CYCLES(2), .LONG_PRESS_CYCLES(16),
        .DEPTH_EDIT_TIMEOUT_CYCLES(50), .NUM_SONGS(2)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .bank_down_n(buttons_n[0]), .bank_up_n(buttons_n[1]),
        .timbre_n(buttons_n[2]), .song_back_n(buttons_n[3]),
        .play_pause_n(buttons_n[4]),
        .enc_s1_n(s1_n), .enc_s2_n(s2_n), .enc_key_n(key_n),
        .bank(bank), .timbre_select(timbre_select), .ui_state(ui_state),
        .song_index(song_index), .song_selected(song_selected),
        .volume_level(volume_level),
        .vibrato_enabled(vibrato_enabled), .vibrato_depth(vibrato_depth),
        .depth_edit(depth_edit), .guide_led_on(guide_led_on),
        .guide_led_blink(guide_led_blink)
    );
    task settle;
        begin repeat (9) @(negedge clk); end
    endtask
    task tap;
        input integer n;
        begin
            buttons_n[n] = 0; settle();
            buttons_n[n] = 1; settle();
        end
    endtask
    task turn_up;
        begin
            s2_n = 1; settle(); s1_n = 0; settle();
            s1_n = 1; settle();
        end
    endtask
    task turn_down;
        begin
            s2_n = 0; settle(); s1_n = 0; settle();
            s1_n = 1; settle(); s2_n = 1; settle();
        end
    endtask
    initial begin
        settle(); rst_n = 1; settle();
        if (bank != 0 || timbre_select != 1 || ui_state != 0 ||
            song_index != 0 || song_selected || volume_level != 16 ||
            vibrato_enabled || vibrato_depth != 4 || depth_edit)
            $fatal(1, "reset state");

        tap(4);
        if (ui_state != 1 || song_selected)
            $fatal(1, "first play must open song list");
        tap(3);
        if (ui_state != 0) $fatal(1, "return from song list");
        tap(1);
        if (bank != 1) $fatal(1, "bank up");
        tap(0);
        if (bank != 0) $fatal(1, "bank down");
        repeat (6) tap(1);
        if (bank != 4) $fatal(1, "bank upper boundary");
        repeat (6) tap(0);
        if (bank != 0) $fatal(1, "bank lower boundary");
        tap(2);
        if (timbre_select != 0) $fatal(1, "timbre toggle");
        tap(3);
        if (ui_state != 1 || guide_led_on || guide_led_blink)
            $fatal(1, "song list");
        tap(1);
        if (song_index != 1 || bank != 0) $fatal(1, "song next");
        tap(1);
        if (song_index != 0) $fatal(1, "song wrap");
        tap(0);
        if (song_index != 1) $fatal(1, "song previous wrap");
        tap(4);
        if (ui_state != 2 || !guide_led_on || !song_selected)
            $fatal(1, "guide start");
        tap(1);
        if (song_index != 1 || bank != 0) $fatal(1, "bank/song changed while guiding");
        tap(4);
        if (ui_state != 3 || !guide_led_blink) $fatal(1, "guide pause");
        tap(4);
        if (ui_state != 2) $fatal(1, "guide resume");
        tap(3);
        if (ui_state != 0 || guide_led_on) $fatal(1, "guide stop/back");

        turn_up();
        if (volume_level != 17 || vibrato_depth != 4)
            $fatal(1, "rotation must adjust volume");
        turn_down();
        if (volume_level != 16) $fatal(1, "volume down");
        key_n = 0; settle(); key_n = 1; settle();
        if (!vibrato_enabled) $fatal(1, "short press vibrato");
        key_n = 0; repeat (30) @(negedge clk);
        if (!depth_edit || !vibrato_enabled)
            $fatal(1, "long press depth mode, no vibrato toggle");
        key_n = 1; settle();
        turn_up();
        if (vibrato_depth != 5 || volume_level != 16)
            $fatal(1, "depth edit must not adjust volume");
        key_n = 0; settle(); key_n = 1; settle();
        if (depth_edit || !vibrato_enabled)
            $fatal(1, "short press exits edit without vibrato toggle");

        key_n = 0; repeat (30) @(negedge clk); key_n = 1; settle();
        if (!depth_edit) $fatal(1, "depth mode did not reopen");
        repeat (60) @(negedge clk);
        if (depth_edit) $fatal(1, "depth edit inactivity timeout");
        dut.volume_level = 5'd30;
        turn_up(); turn_up();
        if (volume_level != 31) $fatal(1, "volume upper saturation");
        dut.volume_level = 5'd1;
        turn_down(); turn_down();
        if (volume_level != 0) $fatal(1, "volume lower saturation");

        // A chord is ignored even when its final key is released.
        buttons_n[1:0] = 2'b00; settle();
        buttons_n[0] = 1; settle();
        buttons_n[1] = 1; settle();
        if (bank != 0) $fatal(1, "two-key chord changed bank");
        $display("PASS: five-key panel mapping, guide menu, volume, EC11 and chord rejection");
        $finish;
    end
endmodule
