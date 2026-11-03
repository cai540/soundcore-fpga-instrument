`timescale 1ns/1ps
module tb_pressure_i2s_led_core;
    reg clk_audio = 0;
    always #5 clk_audio = ~clk_audio;
    reg rst_n = 0;
    wire [6:0] pad_led_on;
    pressure_i2s_additive32_core #(.LED_FLASH_CYCLES(4)) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_miso(1'b0), .enc_s1_n(1'b1), .enc_s2_n(1'b1),
        .enc_key_n(1'b1), .key_up_n(1'b1), .key_down_n(1'b1),
        .pad_led_on(pad_led_on)
    );
    initial begin
        force dut.pressed = 7'b0000000;
        force dut.strike_valid = 1'b0;
        force dut.strike_channel = 3'd0;
        repeat (2) @(negedge clk_audio);
        rst_n = 1;
        force dut.pressed = 7'b1000001;
        #1;
        if (pad_led_on !== 7'b1000001)
            $fatal(1, "core AI0/AI6 hold-to-light wiring");
        force dut.pressed = 7'b0000000;
        force dut.strike_channel = 3'd3;
        force dut.strike_valid = 1'b1;
        @(negedge clk_audio);
        force dut.strike_valid = 1'b0;
        #1;
        if (pad_led_on !== 7'b0001000)
            $fatal(1, "core AI3 strike-to-light wiring");
        repeat (4) @(negedge clk_audio);
        #1;
        if (pad_led_on !== 7'b0000000)
            $fatal(1, "core quick-tap flash timeout");
        $display("PASS: core exposes AI0..AI6 LED status independently");
        $finish;
    end
endmodule
