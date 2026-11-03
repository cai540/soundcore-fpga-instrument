`timescale 1ns/1ps
module tb_pressure_adc_direct_core;
    reg clk_audio = 1'b0;
    reg rst_n = 1'b0;
    reg key_up_n = 1'b1;
    reg key_down_n = 1'b1;
    reg [11:0] ai0_input = 12'd0;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire dac_bclk, dac_lrclk, dac_din;
    integer loops;
    always #40 clk_audio = ~clk_audio;
    pressure_adc_direct_core #(.SCAN_HALF_CYCLES(3),
                               .SCAN_GAP_CYCLES(4)) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .key_up_n(key_up_n), .key_down_n(key_down_n),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk), .dac_din(dac_din)
    );
    assign adc_miso = dut.scanner.bit_index <= 11 &&
                      dut.scanner.scan_channel == 0
        ? ai0_input[dut.scanner.bit_index] : 1'b0;

    task wait_ai0;
        input [11:0] expected;
        begin
            loops = 0;
            while (dut.ai0_code != expected && loops < 20000) begin
                @(negedge clk_audio); loops = loops + 1;
            end
            if (loops == 20000)
                $fatal(1, "AI0 update failed: expected=%0d actual=%0d",
                       expected, dut.ai0_code);
            repeat (3) @(negedge clk_audio);
        end
    endtask

    initial begin
        repeat (4) @(negedge clk_audio);
        rst_n = 1'b1;
        repeat (3) @(negedge clk_audio);
        if (dut.gate != 0) $fatal(1, "idle input must be silent");
        ai0_input = 12'd2457;
        wait_ai0(12'd2457);
        if (dut.gate != 4'b0001 || dut.velocity[7:0] != 8'd60)
            $fatal(1, "1.5 V must select weak level");
        ai0_input = 12'd3440;
        wait_ai0(12'd3440);
        if (dut.gate != 4'b0001 || dut.velocity[7:0] != 8'd240)
            $fatal(1, "2.1 V must select strong level");
        ai0_input = 12'd0;
        wait_ai0(12'd0);
        if (dut.gate != 0) $fatal(1, "released input must be silent");
        key_up_n = 1'b0;
        repeat (4) @(negedge clk_audio);
        if (dut.gate != 4'b0001 || dut.velocity[7:0] != 8'd60)
            $fatal(1, "KEY0 reference failed");
        key_up_n = 1'b1;
        key_down_n = 1'b0;
        repeat (4) @(negedge clk_audio);
        if (dut.gate != 4'b0001 || dut.velocity[7:0] != 8'd240)
            $fatal(1, "KEY1 reference failed");
        $display("PASS: raw AI0 0/1.5/2.1 V and KEY0/KEY1 references");
        $finish;
    end
endmodule
