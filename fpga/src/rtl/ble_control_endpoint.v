// FPGA-owned instrument-state endpoint. Consumes CRC-checked command frames
// and returns STATE only after the panel controller has applied a SET.
// write_enable comes from the current link/session policy. GET_STATE remains
// available when writes are locked. Real-time finger snapshots bypass reply
// serialization and never wait for an individual STATE acknowledgement.
module ble_control_endpoint #(
    parameter EXTENDED_STATE = 0,
    parameter SONG_EXTENSIONS = 0,
    parameter REALTIME_NOTES = 0,
    parameter SCORE_UPLOAD = 0,
    parameter CAPTURE_UI = 0,
    parameter OMR_ENABLE = 0,
    parameter HANDPAN_ENABLE = 0,
    parameter PRODUCT_TOOLS = 0
) (
    input wire clk,
    input wire rst_n,
    input wire rx_valid,
    input wire [7:0] rx_byte,
    input wire write_enable,
    input wire [2:0] bank,
    input wire [3:0] key,
    input wire [1:0] timbre,
    input wire [4:0] volume,
    input wire vibrato,
    input wire [1:0] ui_state,
    input wire [7:0] song_index,
    input wire [10:0] guide_step,
    input wire [2:0] guide_target,
    input wire [2:0] guide_target_bank,
    input wire [1:0] playback_state,
    input wire [3:0] vibrato_depth,
    input wire [7:0] bend,
    input wire [1:0] led_mode,
    input wire [2:0] effect_mask,
    input wire [7:0] oled_contrast,
    input wire [6:0] pad_mask,
    input wire [71:0] telemetry,
    output reg remote_valid,
    output reg [7:0] remote_type,
    output reg [7:0] remote_value,
    output reg [7:0] remote_value2,
    output reg [111:0] remote_payload,
    output wire link_activity,
    output wire tx_valid,
    output reg [7:0] tx_byte,
    input wire tx_ready,
    output reg score_request_valid,
    output reg [7:0] score_request_type,score_request_seq,score_request_length,
    output reg [111:0] score_request_payload,
    input wire score_response_valid,
    input wire [111:0] score_response_payload,
    output reg capture_display_valid,
    output reg [87:0] capture_display_payload,
    output reg tools_request_valid,
    output reg[7:0] tools_request_type,tools_request_length,
    output reg[111:0] tools_request_payload,
    input wire tools_response_valid,
    input wire[111:0] tools_response_payload,
    input wire tools_response_bulk,input wire[7:0] tools_bulk_byte,output wire[6:0] tools_bulk_index
);
    wire frame_valid, frame_error;
    wire [7:0] frame_type, frame_seq, frame_len;
    wire [111:0] frame_payload;
    ble_frame_parser parser (
        .clk(clk), .rst_n(rst_n), .byte_valid(rx_valid),
        .byte_data(rx_byte), .frame_valid(frame_valid),
        .frame_error(frame_error), .frame_type(frame_type),
        .frame_seq(frame_seq), .frame_len(frame_len),
        .frame_payload(frame_payload)
    );
    // A complete CRC-checked request is evidence of a live phone data path.
    assign link_activity = frame_valid;

    localparam [2:0] IDLE=0, APPLY=1, CAPTURE=2, SEND=3, SCORE_WAIT=4, OMR_WAIT=5,TOOLS_WAIT=6;
    reg [2:0] phase;
    reg [15:0] score_wait_count;
    reg [7:0] tx_index;
    assign tools_bulk_index=tx_index>=10 ? tx_index-10:0;
    reg [7:0] response_seq, response_crc, error_code;
    reg [7:0] response_type, response_len;
    reg response_error;
    reg [111:0] snapshot;
    reg last_write_valid;
    reg [7:0] last_write_seq, last_write_type;
    reg realtime_seen;
    reg [7:0] realtime_seq;
    reg [7:0] captured_request_type;
    wire [111:0] layout_state={56'd0,8'd7,4'd0,key,8'd5,8'd107,8'd36,8'd2,8'd1};
    reg absolute_payload_ok;
    integer note_i;
    always @* begin
        absolute_payload_ok=1;
        for(note_i=0;note_i<7;note_i=note_i+1)
            if(frame_payload[note_i] && frame_payload[24+note_i*8 +: 8]>=72)absolute_payload_ok=0;
    end
    localparam [7:0] STATE_LEN = EXTENDED_STATE ? 8'd14 : 8'd9;
    wire [2:0] response_target_bank = SONG_EXTENSIONS ? guide_target_bank : 3'd0;
    wire [2:0] response_step_high = SONG_EXTENSIONS ? guide_step[10:8] : 3'd0;
    wire [1:0] response_playback = SONG_EXTENSIONS ? playback_state : 2'd0;
    wire [71:0] base_state = {(SONG_EXTENSIONS != 0),response_target_bank,response_step_high,write_enable,
                              5'd0,guide_target,guide_step[7:0],
                              song_index,6'd0,ui_state,7'd0,vibrato,
                              3'd0,volume,6'd0,timbre,5'd0,bank};
    wire [111:0] full_state = {{1'b0,pad_mask},oled_contrast,{(REALTIME_NOTES != 0),response_playback,effect_mask,led_mode},
                               bend,{4'd0,vibrato_depth},base_state};
    wire [7:0] command_value = frame_payload[7:0];
    wire [7:0] command_value2 = frame_payload[15:8];
    wire capture_value_ok=frame_len==11 && frame_payload[7:0]==1 && frame_payload[15:8]<=8 &&
        frame_payload[23:16]<=100 && frame_payload[39:24]<=1800 && frame_payload[55:40]<=1800 &&
        frame_payload[71:56]<=1023 && (frame_payload[79:72]==255 ||
        (frame_payload[79:72]>=24 && frame_payload[79:72]<=108));
    wire [111:0] capture_reply={16'd0,8'd1,frame_payload[87:0]};
    wire is_set = (frame_type >= 8'h10 && frame_type <= 8'h1f) ||
                  frame_type == 8'h21 || frame_type == 8'h22 ||
                  frame_type == 8'h23 || frame_type==8'h27;
    wire valid_length = frame_len == ((frame_type == 8'h01 ||
                        frame_type == 8'h18 || frame_type == 8'h19 ||
                        frame_type == 8'h1c || frame_type == 8'h20 || frame_type==8'h26) ? 0 :
                        (frame_type == 8'h16 ? 2 :
                         frame_type == 8'h1f ? 7 : 1));
    wire valid_value = (frame_type == 8'h10 && command_value <= 31) ||
                       (frame_type == 8'h11 && command_value <= 4) ||
                       (frame_type == 8'h12 && command_value <= (HANDPAN_ENABLE ? 3:1)) ||
                       ((frame_type == 8'h13 || frame_type == 8'h14) && command_value <= 1) ||
                       (frame_type == 8'h15 && command_value <= 3) ||
                       (frame_type == 8'h16 && command_value <= 6 &&
                        command_value2 != 0) ||
                       (frame_type == 8'h17 && command_value <= 6) ||
                       frame_type == 8'h18 || frame_type == 8'h19 ||
                       (frame_type == 8'h1a && command_value <= 15) ||
                       frame_type == 8'h1b || frame_type == 8'h1c ||
                       (frame_type == 8'h1d && command_value <= 3) ||
                       frame_type == 8'h1e ||
                       (frame_type == 8'h1f && frame_payload[7:0] <= 4 &&
                        frame_payload[15:8] <= (HANDPAN_ENABLE ? 3:1) &&
                        frame_payload[23:16] <= 31 &&
                        frame_payload[31:24] <= 1 &&
                        frame_payload[39:32] <= 15 &&
                        frame_payload[47:40] <= 3) ||
                       (frame_type == 8'h21 && command_value <= 8'h7f) ||
                       (frame_type == 8'h22 && command_value <= 8'h07) ||
                       (frame_type == 8'h23 && command_value <= 8'h03) ||
                       (frame_type == 8'h27 && command_value<=11);

    function [7:0] crc_next;
        input [7:0] prior, data;
        reg [7:0] c;
        integer i;
        begin
            c=prior ^ data;
            for (i=0;i<8;i=i+1) c=c[7] ? (c<<1)^8'h07 : (c<<1);
            crc_next=c;
        end
    endfunction
    function [7:0] crc_response;
        input [7:0] typ, seq;
        input [111:0] payload;
        input [7:0] length;
        reg [7:0] c;
        integer i;
        begin
            c=crc_next(0,8'h01);
            c=crc_next(c,typ);
            c=crc_next(c,seq);
            c=crc_next(c,length);
            for (i=0;i<14;i=i+1)
                if (i<length) c=crc_next(c,payload[8*i +: 8]);
            crc_response=c;
        end
    endfunction
    function [7:0] crc_error;
        input [7:0] seq, code;
        reg [7:0] c;
        begin
            c=crc_next(0,8'h01);
            c=crc_next(c,8'hE0);
            c=crc_next(c,seq);
            c=crc_next(c,8'd1);
            crc_error=crc_next(c,code);
        end
    endfunction

    assign tx_valid = phase == SEND;
    always @(*) begin
        case (tx_index)
            0: tx_byte=8'hA5;
            1: tx_byte=8'h01;
            2: tx_byte=response_error ? 8'hE0 : response_type;
            3: tx_byte=response_seq;
            4: tx_byte=response_error ? 8'd1 : response_len;
            default: if (response_error)
                tx_byte=tx_index==5 ? error_code : response_crc;
            else if(response_type==8'h86 && tx_index>=10 && tx_index<response_len+5)tx_byte=tools_bulk_byte;
            else if (tx_index<5+response_len)
                tx_byte=snapshot[8*(tx_index-5) +: 8];
            else tx_byte=response_crc;
        endcase
    end

    wire omr_response_valid;wire [111:0] omr_response_payload;
    omr_frame_endpoint #(.W1_FILE("D:/FPGA/Projects/soundcore_2026/build/fpga_omr_20261031/model/w1.hex"),.B1_FILE("D:/FPGA/Projects/soundcore_2026/build/fpga_omr_20261031/model/b1.hex"),.W2_FILE("D:/FPGA/Projects/soundcore_2026/build/fpga_omr_20261031/model/w2.hex"),.B2_FILE("D:/FPGA/Projects/soundcore_2026/build/fpga_omr_20261031/model/b2.hex"),.SHIFT1(2),.MODEL_CRC(32'he6726e10)) omr(
      .clk(clk),.rst_n(rst_n),.request_valid(OMR_ENABLE!=0 && phase==IDLE && frame_valid && frame_type>=8'h60 && frame_type<=8'h63),
      .request_type(frame_type),.request_length(frame_len),.request_payload(frame_payload),
      .response_valid(omr_response_valid),.response_payload(omr_response_payload));
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase<=IDLE;
            tx_index<=0;
            response_seq<=0;
            response_crc<=0;
            error_code<=0;
            response_error<=0;
            snapshot<=0;
            remote_valid<=0;
            remote_type<=0;
            remote_value<=0;
            remote_value2<=0;
            remote_payload<=0;
            response_type<=8'h80;
            response_len<=STATE_LEN;
            last_write_valid<=0;
            last_write_seq<=0;
            last_write_type<=0;
            realtime_seen<=0;realtime_seq<=0;
            captured_request_type<=0;
            score_request_valid<=0;score_request_type<=0;score_request_seq<=0;
            score_request_length<=0;score_request_payload<=0;score_wait_count<=0;
            capture_display_valid<=0;capture_display_payload<=0;
            tools_request_valid<=0;tools_request_type<=0;tools_request_length<=0;tools_request_payload<=0;
        end else begin
            remote_valid<=0;
            score_request_valid<=0;
            capture_display_valid<=0;
            tools_request_valid<=0;
            // Live notes do not wait behind UART STATE transmission. They
            // have no per-key ACK and can only carry current held state.
            if (!write_enable) realtime_seen<=0;
            if (REALTIME_NOTES != 0 && frame_valid &&
                ((frame_type==8'h24 && frame_len==3) ||
                 (frame_type==8'h25 && frame_len==10 && absolute_payload_ok)) &&
                !frame_payload[7] && !frame_payload[15] &&
                frame_payload[23:16]!=0 && write_enable &&
                (!realtime_seen || frame_seq!=realtime_seq)) begin
                remote_valid<=1;remote_type<=frame_type;
                remote_value<=frame_payload[7:0];remote_value2<=frame_payload[15:8];
                remote_payload<=frame_payload;
                realtime_seen<=1;realtime_seq<=frame_seq;
            end
            if (!write_enable) last_write_valid<=0;
            case (phase)
                IDLE: if ((frame_error || frame_valid) &&
                          !(REALTIME_NOTES != 0 && (frame_type==8'h24 || frame_type==8'h25))) begin
                    response_seq<=frame_seq;
                    captured_request_type<=frame_type;
                    tx_index<=0;
                    if (frame_error) begin
                        response_error<=1;
                        error_code<=1;
                        response_crc<=crc_error(frame_seq,1);
                        phase<=SEND;
                    end else if(PRODUCT_TOOLS!=0 && frame_type>=8'h40 && frame_type<=8'h55)begin
                        response_error<=0;
                        tools_request_valid<=1;tools_request_type<=frame_type;
                        tools_request_length<=frame_len;tools_request_payload<=frame_payload;
                        score_wait_count<=0;phase<=TOOLS_WAIT;
                    end else if(OMR_ENABLE!=0 && frame_type>=8'h60 && frame_type<=8'h63)begin
                        response_error<=0;score_wait_count<=0;phase<=OMR_WAIT;
                    end else if(CAPTURE_UI!=0 && (frame_type==8'h36 || frame_type==8'h37))begin
                        response_error<=0;
                        if((frame_type==8'h36 && frame_len!=0) || (frame_type==8'h37 && !capture_value_ok))begin
                            response_error<=1;error_code<=3;response_crc<=crc_error(frame_seq,3);
                        end else if(frame_type==8'h37 && !write_enable)begin
                            response_error<=1;error_code<=4;response_crc<=crc_error(frame_seq,4);
                        end else begin
                            response_type<=8'h83;response_len<=14;
                            snapshot<=frame_type==8'h36 ? {16'd0,8'd1,80'd0,8'd1} : capture_reply;
                            response_crc<=crc_response(8'h83,frame_seq,
                                frame_type==8'h36 ? {16'd0,8'd1,80'd0,8'd1} : capture_reply,14);
                            if(frame_type==8'h37)begin capture_display_valid<=1;capture_display_payload<=frame_payload[87:0];end
                        end
                        phase<=SEND;
                    end else if (SCORE_UPLOAD!=0 && (frame_type>=8'h30 && frame_type<=8'h35 || frame_type==8'h38)) begin
                        response_error<=0;
                        if(frame_type!=8'h30 && !write_enable)begin
                            response_error<=1;error_code<=4;response_crc<=crc_error(frame_seq,4);phase<=SEND;
                        end else begin
                            score_request_valid<=1;score_request_type<=frame_type;score_request_seq<=frame_seq;
                            score_request_length<=frame_len;score_request_payload<=frame_payload;
                            score_wait_count<=0;phase<=SCORE_WAIT;
                        end
                    end else if (frame_type != 8'h01 && frame_type != 8'h20 && frame_type!=8'h26 && !is_set) begin
                        response_error<=1;
                        error_code<=2;
                        response_crc<=crc_error(frame_seq,2);
                        phase<=SEND;
                    end else if (!valid_length ||
                                 (is_set && !valid_value)) begin
                        response_error<=1;
                        error_code<=3;
                        response_crc<=crc_error(frame_seq,3);
                        phase<=SEND;
                    end else if (is_set && !write_enable) begin
                        response_error<=1;
                        error_code<=4;
                        response_crc<=crc_error(frame_seq,4);
                        phase<=SEND;
                    end else if (is_set && last_write_valid &&
                                 frame_seq == last_write_seq &&
                                 frame_type == last_write_type) begin
                        response_error<=0;
                        phase<=CAPTURE; // idempotent retry, especially NOTE_ON
                    end else if (is_set) begin
                        remote_type<=frame_type;
                        remote_value<=command_value;
                        remote_value2<=command_value2;
                        remote_payload<=frame_payload;
                        remote_valid<=1;
                        last_write_valid<=1;
                        last_write_seq<=frame_seq;
                        last_write_type<=frame_type;
                        response_error<=0;
                        phase<=APPLY;
                    end else begin
                        response_error<=0;
                        phase<=CAPTURE;
                    end
                end
                APPLY: phase<=CAPTURE; // panel samples remote_valid here
                TOOLS_WAIT:begin
                    if(tools_response_valid)begin
                        snapshot<=tools_response_payload;response_type<=tools_response_bulk ? 8'h86:8'h85;response_len<=tools_response_bulk ? (tools_response_payload[15:8]==8'h48 ? 80:128):14;
                        response_crc<=tools_response_bulk ? 0:crc_response(8'h85,response_seq,tools_response_payload,14);phase<=SEND;
                    end else if(score_wait_count==16'hffff)begin
                        response_error<=1;error_code<=5;response_crc<=crc_error(response_seq,5);phase<=SEND;
                    end else score_wait_count<=score_wait_count+1'b1;
                end
                OMR_WAIT:begin
                    if(omr_response_valid)begin
                        snapshot<=omr_response_payload;response_type<=8'he0;response_len<=14;
                        response_crc<=crc_response(8'he0,response_seq,omr_response_payload,14);phase<=SEND;
                    end else if(score_wait_count==16'hffff)begin
                        response_error<=1;error_code<=5;response_crc<=crc_error(response_seq,5);phase<=SEND;
                    end else score_wait_count<=score_wait_count+1'b1;
                end
                SCORE_WAIT:begin
                    if(score_response_valid)begin
                        snapshot<=score_response_payload;response_type<=8'h82;response_len<=14;
                        response_crc<=crc_response(8'h82,response_seq,score_response_payload,14);phase<=SEND;
                    end else if(score_wait_count==16'hffff)begin
                        response_error<=1;error_code<=5;response_crc<=crc_error(response_seq,5);phase<=SEND;
                    end else score_wait_count<=score_wait_count+1'b1;
                end
                CAPTURE: begin
                    if(captured_request_type==8'h26 || captured_request_type==8'h27)begin
                        response_type<=8'h84;response_len<=7;snapshot<=layout_state;
                        response_crc<=crc_response(8'h84,response_seq,layout_state,7);
                    end else begin
                    response_type<=captured_request_type == 8'h20 ? 8'h81 : 8'h80;
                    response_len<=captured_request_type == 8'h20 ? 8'd9 : STATE_LEN;
                    snapshot<=captured_request_type == 8'h20 ? {40'd0,telemetry} :
                              EXTENDED_STATE ? full_state : {40'd0,base_state};
                    response_crc<=crc_response(captured_request_type == 8'h20 ? 8'h81 : 8'h80,
                                              response_seq,
                                              captured_request_type == 8'h20 ? {40'd0,telemetry} :
                                              EXTENDED_STATE ? full_state : {40'd0,base_state},
                                              captured_request_type == 8'h20 ? 8'd9 : STATE_LEN);
                    end
                    phase<=SEND;
                end
                SEND: if (tx_ready) begin
                    if(response_type==8'h86 && !response_error && tx_index>=1 && tx_index<response_len+5)response_crc<=crc_next(response_crc,tx_byte);
                    if (tx_index == (response_error ? 6 : 5+response_len))
                        phase<=IDLE;
                    else tx_index<=tx_index+1'b1;
                end
                default: phase<=IDLE;
            endcase
        end
    end
endmodule
