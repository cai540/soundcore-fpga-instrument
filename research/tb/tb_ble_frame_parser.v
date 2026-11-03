`timescale 1ns/1ps
module tb_ble_frame_parser;
    reg clk=0, rst_n=0, byte_valid=0;
    reg [7:0] byte_data=0;
    wire frame_valid, frame_error;
    wire [7:0] frame_type, frame_seq, frame_len;
    wire [111:0] frame_payload;
    integer good=0, bad=0;
    always #5 clk=~clk;
    ble_frame_parser dut (
        .clk(clk), .rst_n(rst_n), .byte_valid(byte_valid),
        .byte_data(byte_data), .frame_valid(frame_valid),
        .frame_error(frame_error), .frame_type(frame_type),
        .frame_seq(frame_seq), .frame_len(frame_len),
        .frame_payload(frame_payload)
    );
    always @(posedge clk) if (rst_n) begin
        if (frame_valid) good=good+1;
        if (frame_error) bad=bad+1;
    end
    task send;
        input [7:0] b;
        begin
            @(negedge clk); byte_data=b; byte_valid=1;
            @(negedge clk); byte_valid=0;
        end
    endtask
    initial begin
        repeat (3) @(negedge clk); rst_n=1;
        // GET_STATE: CRC(01 01 2A 00)=51.
        send(8'hA5); send(8'h01); send(8'h01); send(8'h2A);
        send(8'h00); send(8'h51);
        repeat (2) @(negedge clk);
        if (good != 1 || frame_type != 8'h01 || frame_seq != 8'h2A || frame_len != 0)
            $fatal(1,"valid GET_STATE failed good=%0d type=%h seq=%h",good,frame_type,frame_seq);
        // Same frame with damaged CRC must be rejected.
        send(8'hA5); send(8'h01); send(8'h01); send(8'h2B);
        send(8'h00); send(8'h00);
        repeat (2) @(negedge clk);
        if (good != 1 || bad != 1) $fatal(1,"bad CRC accepted");
        // Oversized LEN must not consume following SOF.
        send(8'hA5); send(8'h01); send(8'h10); send(8'h01); send(8'h0F);
        send(8'hA5); send(8'h01); send(8'h01); send(8'h2A);
        send(8'h00); send(8'h51);
        repeat (2) @(negedge clk);
        if (good != 2 || bad != 2) $fatal(1,"length recovery failed good=%0d bad=%0d",good,bad);
        $display("PASS: BLE frame parser CRC, sequence, length, recovery");
        $finish;
    end
endmodule
