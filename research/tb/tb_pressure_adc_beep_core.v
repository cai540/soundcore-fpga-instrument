`timescale 1ns/1ps
module tb_pressure_adc_beep_core;
    reg clk_audio = 1'b0;
    reg rst_n = 1'b0;
    reg [11:0] ai0_input = 12'd0;
    wire adc_cs_n, adc_sclk, adc_mosi, adc_miso;
    wire dac_bclk, dac_lrclk, dac_din;
    integer loops;
    always #40 clk_audio = ~clk_audio;
    pressure_adc_beep_core #(.SCAN_HALF_CYCLES(3),
                             .SCAN_GAP_CYCLES(4)) dut (
        .clk_audio(clk_audio), .rst_n(rst_n),
        .adc_cs_n(adc_cs_n), .adc_sclk(adc_sclk),
        .adc_mosi(adc_mosi), .adc_miso(adc_miso),
        .dac_bclk(dac_bclk), .dac_lrclk(dac_lrclk), .dac_din(dac_din)
    );
    assign adc_miso = dut.scanner.bit_index <= 11 &&
                      dut.scanner.scan_channel == 0
        ? ai0_input[dut.scanner.bit_index] : 1'b0;

    task check_code;
        input [11:0] adc_code;
        input [2:0] expected_beeps;
        begin
            ai0_input = adc_code;
            loops = 0;
            while (dut.ai0_code != adc_code && loops < 20000) begin
                @(negedge clk_audio); loops = loops + 1;
            end
            if (loops == 20000 || dut.beep_count != expected_beeps)
                $fatal(1, "ADC beep count wrong: code=%0d count=%0d expected=%0d",
                       dut.ai0_code, dut.beep_count, expected_beeps);
        end
    endtask

    initial begin
        repeat (4) @(negedge clk_audio);
        rst_n = 1'b1;
        check_code(12'd409, 3'd0);
        check_code(12'd1023, 3'd0);
        check_code(12'd1024, 3'd1);
        check_code(12'd1075, 3'd2);
        check_code(12'd1126, 3'd3);
        check_code(12'd1177, 3'd4);
        check_code(12'd3506, 3'd4);
        force dut.sample_index = 16'd0;
        #1;
        if (!dut.beep_gate) $fatal(1, "first beep missing");
        force dut.sample_index = 16'd8500;
        #1;
        if (!dut.beep_gate) $fatal(1, "second beep missing");
        force dut.sample_index = 16'd16500;
        #1;
        if (!dut.beep_gate) $fatal(1, "third beep missing");
        force dut.sample_index = 16'd24500;
        #1;
        if (!dut.beep_gate) $fatal(1, "fourth beep missing");
        force dut.sample_index = 16'd30000;
        #1;
        if (dut.beep_gate) $fatal(1, "group gap missing");
        release dut.sample_index;
        $display("PASS: AI0 ADC code maps to 0..4 audible beeps");
        $finish;
    end
endmodule
