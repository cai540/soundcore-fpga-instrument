`timescale 1ns/1ps
module tb_mcp3208_scan;
    reg clk = 0;
    reg rst_n = 0;
    wire spi_cs_n, spi_sclk, spi_mosi;
    wire sample_valid;
    wire [2:0] sample_channel;
    wire [11:0] sample_value;
    wire spi_miso;
    reg [23:0] sent_bits = 24'd0;
    integer serial_count = 0;
    integer sample_count = 0;
    integer cycles = 0;

    always #5 clk = ~clk;
    mcp3208_scan #(.HALF_CYCLES(3), .GAP_CYCLES(4)) dut (
        .clk(clk), .rst_n(rst_n), .spi_cs_n(spi_cs_n),
        .spi_sclk(spi_sclk), .spi_mosi(spi_mosi), .spi_miso(spi_miso),
        .sample_valid(sample_valid), .sample_channel(sample_channel),
        .sample_value(sample_value)
    );
    function [11:0] code_for_channel;
        input [2:0] channel;
        begin code_for_channel = 12'h120 + {channel, 6'b0}; end
    endfunction
    // Fake converter: only the last 12 bits carry conversion data.
    wire [11:0] simulated_code = code_for_channel(dut.scan_channel);
    assign spi_miso = dut.bit_index <= 11
        ? simulated_code[dut.bit_index] : 1'b0;

    always @(posedge spi_sclk) if (!spi_cs_n) begin
        sent_bits = {sent_bits[22:0], spi_mosi};
        serial_count = serial_count + 1;
    end
    always @(posedge spi_cs_n) if (rst_n && serial_count != 0) begin
        if (serial_count != 24 || sent_bits[23:16] !==
            (8'h06 | {7'd0, sample_channel[2]}) ||
            sent_bits[15:8] !== {sample_channel[1:0], 6'b0})
            $fatal(1, "MCP3208 SPI command or frame invalid: ch=%0d bits=%0d tx=%h",
                   sample_channel, serial_count, sent_bits);
        serial_count = 0;
        sent_bits = 24'd0;
    end
    always @(negedge clk) if (sample_valid) begin
        if (sample_channel !== sample_count[2:0] ||
            sample_value !== code_for_channel(sample_count[2:0]))
            $fatal(1, "MCP3208 sample %0d: channel=%0d value=%h",
                   sample_count, sample_channel, sample_value);
        sample_count = sample_count + 1;
    end
    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        while (sample_count < 16 && cycles < 15000) begin
            @(negedge clk);
            cycles = cycles + 1;
        end
        if (sample_count != 16) $fatal(1, "ADC scan timed out");
        $display("PASS: MCP3208 eight-channel SPI scan, framing, commands and data");
        $finish;
    end
endmodule
