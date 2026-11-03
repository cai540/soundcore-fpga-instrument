`timescale 1ns/1ps
module tb_front_panel_guide_bridge;
    reg clk = 0, rst_n = 0;
    reg [4:0] buttons_n = 5'b11111;
    reg s1_n = 1, s2_n = 1, key_n = 1;
    reg strike_valid = 0;
    reg [2:0] strike_channel = 0;
    wire [2:0] bank, guide_target_pad;
    wire timbre_select, song_selected, vibrato_enabled, depth_edit;
    wire [1:0] ui_state;
    wire [7:0] song_index;
    wire [4:0] volume_level;
    wire [3:0] vibrato_depth, guide_step, guide_length;
    wire guide_complete, guide_correct_pulse, guide_wrong_pulse;
    wire [6:0] guide_target_led;
    wire guide_button_led;
    always #5 clk = ~clk;
    front_panel_guide_bridge #(
        .DEBOUNCE_CYCLES(2), .LONG_PRESS_CYCLES(16),
        .DEPTH_EDIT_TIMEOUT_CYCLES(50), .BLINK_HALF_CYCLES(4)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .bank_down_n(buttons_n[0]), .bank_up_n(buttons_n[1]),
        .timbre_n(buttons_n[2]), .song_back_n(buttons_n[3]),
        .play_pause_n(buttons_n[4]),
        .enc_s1_n(s1_n), .enc_s2_n(s2_n), .enc_key_n(key_n),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .bank(bank), .timbre_select(timbre_select),
        .ui_state(ui_state), .song_index(song_index),
        .song_selected(song_selected), .volume_level(volume_level),
        .vibrato_enabled(vibrato_enabled), .vibrato_depth(vibrato_depth),
        .depth_edit(depth_edit), .guide_step(guide_step),
        .guide_length(guide_length), .guide_target_pad(guide_target_pad),
        .guide_complete(guide_complete),
        .guide_correct_pulse(guide_correct_pulse),
        .guide_wrong_pulse(guide_wrong_pulse),
        .guide_target_led(guide_target_led),
        .guide_button_led(guide_button_led)
    );
    task settle;
        begin repeat (9) @(negedge clk); end
    endtask
    task tap;
        input integer key_index;
        begin
            buttons_n[key_index] = 0; settle();
            buttons_n[key_index] = 1; settle();
        end
    endtask
    task strike;
        input [2:0] pad;
        begin
            @(negedge clk); strike_channel = pad; strike_valid = 1;
            @(posedge clk); #1;
            @(negedge clk); strike_valid = 0;
        end
    endtask
    initial begin
        settle(); rst_n = 1; settle();
        tap(4);
        if (ui_state != 1) $fatal(1, "K5 did not open song list");
        tap(4);
        if (ui_state != 2 || !guide_button_led ||
            guide_target_led != 7'b0000001)
            $fatal(1, "K5 did not start target LED");
        strike(3'd2);
        if (guide_step != 0 || !guide_wrong_pulse)
            $fatal(1, "wrong strike advanced bridge");
        strike(3'd0);
        if (guide_step != 1 || !guide_correct_pulse ||
            guide_target_led != 7'b0000010)
            $fatal(1, "correct strike did not move LED");
        tap(4);
        if (ui_state != 3 || guide_target_led != 0)
            $fatal(1, "pause did not hide target");
        strike(3'd1);
        if (guide_step != 1) $fatal(1, "paused strike advanced");
        tap(4);
        if (ui_state != 2 || guide_step != 1 ||
            guide_target_led != 7'b0000010)
            $fatal(1, "resume lost target");
        tap(3);
        if (ui_state != 0 || guide_target_led != 0 ||
            guide_button_led)
            $fatal(1, "K4 did not exit guide");
        $display("PASS: K5 guide, ADC strike event, target LED, pause/resume and K4 exit chain");
        $finish;
    end
endmodule
