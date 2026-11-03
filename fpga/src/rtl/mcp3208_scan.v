// Continuous eight-channel single-ended MCP3208 scanner, SPI mode 0.
// The 24-bit command is {0x06 | channel[2], channel[1:0] << 6, 0x00};
// the returned 12-bit ADC code is in the final twelve received bits.
// At 50 MHz, HALF_CYCLES=25 gives 1 MHz SCLK and GAP_CYCLES=50 gives
// at least 1 us CS-high between frames. Both are conservative defaults.
module mcp3208_scan #(
    parameter integer HALF_CYCLES = 25,
    parameter integer GAP_CYCLES = 50
) (
    input  wire        clk,
    input  wire        rst_n,
    output reg         spi_cs_n,
    output reg         spi_sclk,
    output reg         spi_mosi,
    input  wire        spi_miso,
    output reg         sample_valid,
    output reg [2:0]   sample_channel,
    output reg [11:0]  sample_value
);
    localparam integer HALF_BITS = (HALF_CYCLES < 2) ? 1 : $clog2(HALF_CYCLES);
    localparam integer GAP_BITS = (GAP_CYCLES < 2) ? 1 : $clog2(GAP_CYCLES + 1);
    localparam [1:0] GAP = 2'd0, SETUP = 2'd1,
                     RISING = 2'd2, FALLING = 2'd3;
    reg [1:0] state;
    reg [HALF_BITS-1:0] half_count;
    reg [GAP_BITS-1:0] gap_count;
    reg [4:0] bit_index;
    reg [2:0] scan_channel;
    reg [23:0] command;
    reg [23:0] received;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_cs_n <= 1'b1;
            spi_sclk <= 1'b0;
            spi_mosi <= 1'b0;
            sample_valid <= 1'b0;
            sample_channel <= 3'd0;
            sample_value <= 12'd0;
            state <= GAP;
            half_count <= {HALF_BITS{1'b0}};
            gap_count <= GAP_CYCLES;
            bit_index <= 5'd23;
            scan_channel <= 3'd0;
            command <= 24'd0;
            received <= 24'd0;
        end else begin
            sample_valid <= 1'b0;
            case (state)
                GAP: begin
                    spi_cs_n <= 1'b1;
                    spi_sclk <= 1'b0;
                    if (gap_count == 0) begin
                        command <= {8'h06 | {7'd0, scan_channel[2]},
                                    scan_channel[1:0], 6'b0, 8'd0};
                        // The first command bit is zero; set it before CS falls.
                        spi_mosi <= 1'b0;
                        received <= 24'd0;
                        bit_index <= 5'd23;
                        half_count <= {HALF_BITS{1'b0}};
                        state <= SETUP;
                    end else
                        gap_count <= gap_count - 1'b1;
                end
                SETUP: begin
                    spi_cs_n <= 1'b0;
                    if (half_count == HALF_CYCLES - 1) begin
                        half_count <= {HALF_BITS{1'b0}};
                        state <= RISING;
                    end else
                        half_count <= half_count + 1'b1;
                end
                RISING: begin
                    spi_sclk <= 1'b1;
                    received <= {received[22:0], spi_miso};
                    half_count <= {HALF_BITS{1'b0}};
                    state <= FALLING;
                end
                FALLING: begin
                    if (half_count == HALF_CYCLES - 1) begin
                        spi_sclk <= 1'b0;
                        half_count <= {HALF_BITS{1'b0}};
                        if (bit_index == 0) begin
                            spi_cs_n <= 1'b1;
                            sample_channel <= scan_channel;
                            sample_value <= received[11:0];
                            sample_valid <= 1'b1;
                            scan_channel <= scan_channel + 1'b1;
                            gap_count <= GAP_CYCLES;
                            spi_mosi <= 1'b0;
                            state <= GAP;
                        end else begin
                            bit_index <= bit_index - 1'b1;
                            spi_mosi <= command[bit_index - 1'b1];
                            state <= SETUP;
                        end
                    end else
                        half_count <= half_count + 1'b1;
                end
                default: state <= GAP;
            endcase
        end
    end
endmodule
