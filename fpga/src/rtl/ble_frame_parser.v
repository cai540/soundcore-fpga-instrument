// Byte-stream parser for Soundcore protocol v1. Input bytes may be separated
// by arbitrary cycles. A bad frame is discarded without changing application
// state. Payload byte 0 occupies frame_payload[7:0].
module ble_frame_parser (
    input wire clk,
    input wire rst_n,
    input wire byte_valid,
    input wire [7:0] byte_data,
    output reg frame_valid,
    output reg frame_error,
    output reg [7:0] frame_type,
    output reg [7:0] frame_seq,
    output reg [7:0] frame_len,
    output reg [111:0] frame_payload
);
    localparam [2:0] WAIT_SOF=0, VERSION=1, TYPE=2, SEQ=3,
                     LENGTH=4, PAYLOAD=5, CHECK=6;
    reg [2:0] state;
    reg [7:0] crc, received;
    reg [3:0] payload_count;

    function [7:0] crc_next;
        input [7:0] prior;
        input [7:0] data;
        reg [7:0] c;
        integer bit_index;
        begin
            c = prior ^ data;
            for (bit_index=0; bit_index<8; bit_index=bit_index+1)
                c = c[7] ? (c << 1) ^ 8'h07 : (c << 1);
            crc_next = c;
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= WAIT_SOF;
            frame_valid <= 0;
            frame_error <= 0;
            frame_type <= 0;
            frame_seq <= 0;
            frame_len <= 0;
            frame_payload <= 0;
            payload_count <= 0;
            crc <= 0;
            received <= 0;
        end else begin
            frame_valid <= 0;
            frame_error <= 0;
            if (byte_valid) begin
                case (state)
                    WAIT_SOF: if (byte_data == 8'hA5) begin
                        state <= VERSION;
                        crc <= 0;
                        frame_payload <= 0;
                    end
                    VERSION: if (byte_data == 8'h01) begin
                        crc <= crc_next(0, byte_data);
                        state <= TYPE;
                    end else begin
                        frame_error <= 1;
                        state <= byte_data == 8'hA5 ? VERSION : WAIT_SOF;
                    end
                    TYPE: begin
                        frame_type <= byte_data;
                        crc <= crc_next(crc, byte_data);
                        state <= SEQ;
                    end
                    SEQ: begin
                        frame_seq <= byte_data;
                        crc <= crc_next(crc, byte_data);
                        state <= LENGTH;
                    end
                    LENGTH: if (byte_data <= 8'd14) begin
                        frame_len <= byte_data;
                        payload_count <= 0;
                        crc <= crc_next(crc, byte_data);
                        state <= byte_data == 0 ? CHECK : PAYLOAD;
                    end else begin
                        frame_error <= 1;
                        state <= WAIT_SOF;
                    end
                    PAYLOAD: begin
                        frame_payload[8*payload_count +: 8] <= byte_data;
                        crc <= crc_next(crc, byte_data);
                        payload_count <= payload_count + 1'b1;
                        if (payload_count == frame_len - 1'b1)
                            state <= CHECK;
                    end
                    CHECK: begin
                        received <= byte_data;
                        if (byte_data == crc)
                            frame_valid <= 1;
                        else
                            frame_error <= 1;
                        state <= WAIT_SOF;
                    end
                    default: state <= WAIT_SOF;
                endcase
            end
        end
    end
endmodule
