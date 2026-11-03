`timescale 1ns/1ps
module tb_k5_lamp_follow;
    reg clk=0,rst_n=0;always #5 clk=~clk;
    reg [4:0] keys=5'b11111;
    reg player_finished=0,guide_finished=0;
    wire lamp,demo,mode_menu;
    wire [1:0] ui;
    front_panel_product #(.DEBOUNCE_CYCLES(2),.LONG_PRESS_CYCLES(40),.BLINK_CYCLES(4)) dut(
        .clk(clk),.rst_n(rst_n),.bank_down_n(keys[0]),.bank_up_n(keys[1]),.timbre_n(keys[2]),
        .song_back_n(keys[3]),.play_pause_n(keys[4]),.enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .remote_valid(1'b0),.remote_type(8'd0),.remote_value(8'd0),.remote_payload(56'd0),
        .player_finished(player_finished),.guide_finished(guide_finished),.guide_button_led(lamp),
        .ui_state(ui),.demo_mode(demo),.mode_menu(mode_menu));
    task settle;begin repeat(12)@(negedge clk);end endtask
    task tap;input integer n;begin keys[n]=0;settle();keys[n]=1;settle();end endtask
    task expect_off;integer n;begin for(n=0;n<20;n=n+1)begin @(negedge clk);if(lamp!==0)$fatal(1,"lamp not off");end end endtask
    task expect_on;integer n;begin for(n=0;n<20;n=n+1)begin @(negedge clk);if(lamp!==1)$fatal(1,"lamp not steadily on");end end endtask
    task expect_blink;integer n,ones;begin ones=0;for(n=0;n<24;n=n+1)begin @(negedge clk);if(lamp)ones=ones+1;end if(ones==0 || ones==24)$fatal(1,"pause lamp not blinking");end endtask
    initial begin
        settle();rst_n=1;settle();expect_off();
        tap(3);expect_off();tap(4);expect_on();tap(4);expect_blink();tap(4);expect_on();
        player_finished=1;expect_off();tap(4);player_finished=0;expect_on();tap(3);expect_off();
        keys[3]=0;repeat(70)@(negedge clk);keys[3]=1;settle();
        tap(0);tap(4);if(demo || mode_menu || ui!=1)$fatal(1,"guide mode not confirmed");
        player_finished=1;tap(4);expect_on();
        guide_finished=1;expect_off();guide_finished=0;expect_on();tap(4);expect_blink();
        guide_finished=1;expect_off();tap(3);expect_off();
        $display("PASS: B10 logic off in idle/menu, steady running, pause blink, off on automatic completion or guided completion, replay on; completion source isolated by mode");
        $finish;
    end
endmodule
