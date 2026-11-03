// Runtime monophonic score. Two RAM regions provide atomic publication: a bad
// CRC, interrupted transfer or timeout cannot replace the previous valid score.
// No samples are streamed over BLE; committed event playback is autonomous.
module uploaded_song_engine #(
    parameter integer CYCLES_PER_MS=12288,
    parameter integer UPLOAD_TIMEOUT_MS=6000
)(
    input wire clk,rst_n,link_active,
    input wire request_valid,
    input wire [7:0] request_type,request_seq,request_length,
    input wire [111:0] request_payload,
    output reg response_valid,
    output wire [111:0] response_payload,
    input wire stop_external,
    input wire strike_valid,
    input wire [2:0] strike_pad,
    output reg playing,paused,guiding,finished,
    output reg [9:0] step,
    output wire [2:0] bank,pad,
    output wire [6:0] note,
    output reg [3:0] key,
    output wire gate,
    output reg timbre,
    output reg start_pulse,
    output wire [6:0] guide_led,
    output wire ready,
    output wire display_receiving,
    output wire [9:0] display_count,display_received,display_expected
);
    reg [23:0] memory [0:2047];
    reg active_region,committed,receiving;
    reg [9:0] active_count,expected_count,received;
    reg [15:0] active_crc,active_token,token,expected_crc,crc;
    reg stage_timbre;
    reg stage_absolute,active_absolute;
    reg [3:0] stage_key;
    reg [17:0] total_ms;
    reg [7:0] error;
    reg [2:0] work;
    reg [71:0] chunk;
    reg [23:0] word_read,word_now;
    reg [1:0] load_wait;
    reg [15:0] elapsed_ms;
    reg [31:0] tick_count,timeout_ms;
    reg ack_pending;
    reg action_seen;
    reg [7:0] last_action_seq;
    wire tick = tick_count==CYCLES_PER_MS-1;
    wire [15:0] status_token=receiving ? token : active_token;
    wire [9:0] status_count=receiving ? received : active_count;
    assign ready=committed;
    assign display_receiving=receiving;
    assign display_count=active_count;
    assign display_received=received;
    assign display_expected=expected_count;
    wire event_ready=(playing || guiding) && load_wait==0 && !finished;
    wire rest_now=active_absolute ? word_now[6:0]==127 : word_now[2:0]==7;
    wire [15:0] duration_now=active_absolute ? word_now[22:7] : word_now[21:6];
    wire [2:0] projected_bank,projected_pad;
    assign note=active_absolute ? word_now[6:0] : 7'd24+{4'd0,word_now[5:3]}*7'd7+{4'd0,word_now[2:0]};
    pitch_projection project(.note_index(note),.key(key),.bank(projected_bank),.pad(projected_pad),.sharp(),.valid());
    assign bank=event_ready && !rest_now ? projected_bank : 3'd0;
    assign pad=event_ready && !rest_now ? projected_pad : 3'd7;
    assign gate=playing && !paused && !finished && load_wait==0 && pad<7 &&
                {1'b0,elapsed_ms}+17'd6 < {1'b0,duration_now};
    assign guide_led=guiding && !paused && !finished && load_wait==0 && pad<7 ? 7'b1<<pad : 7'd0;
    wire [7:0] status_pitch=active_absolute ? (event_ready && !rest_now ? {1'b0,note} : 8'd127) :
        (event_ready && !rest_now ? {5'd0,word_now[5:3]} : 8'd0);
    wire status_absolute=receiving ? stage_absolute : active_absolute;
    assign response_payload={status_token,active_crc,7'd0,timbre,status_pitch,5'd0,pad,
        6'd0,step,6'd0,status_count,error,2'd0,finished,guiding,paused,playing,receiving,committed,
        (status_absolute ? 8'd2 : 8'd1)};

    function [15:0] crc_byte;
        input [15:0] prior;input [7:0] data;
        reg [15:0] c;integer i;
        begin c=prior^{data,8'd0};for(i=0;i<8;i=i+1)c=c[15] ? (c<<1)^16'h1021 : c<<1;crc_byte=c;end
    endfunction
    wire [23:0] incoming=chunk[23:0];
    wire [15:0] incoming_ms=stage_absolute ? incoming[22:7] : incoming[21:6];
    wire valid_word=stage_absolute ? !incoming[23] && incoming_ms!=0 &&
        (incoming[6:0]==127 || incoming[6:0]<72 && incoming_ms>=20) :
        incoming[23:22]==0 && incoming_ms!=0 &&
        (incoming[2:0]==7 ? incoming[5:3]==0 : incoming[5:3]<=4 && incoming_ms>=20);
    // Synchronous read infers block memory. Changing step incurs two clocks;
    // no stale target is accepted during that short load interval.
    always @(posedge clk) begin
        word_read<=memory[{active_region,step[9:0]}];
        if(work!=0 && valid_word && {1'b0,total_ms}+{3'b0,incoming_ms}<=19'd180000)
            memory[{~active_region,received[9:0]}]<=incoming;
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            active_region<=0;committed<=0;receiving<=0;active_count<=0;expected_count<=0;received<=0;
            active_crc<=0;active_token<=0;token<=0;expected_crc<=0;crc<=16'hffff;
            stage_timbre<=0;timbre<=0;total_ms<=0;error<=0;work<=0;chunk<=0;
            stage_absolute<=0;active_absolute<=0;stage_key<=0;key<=0;
            word_now<=0;load_wait<=0;elapsed_ms<=0;tick_count<=0;timeout_ms<=0;
            response_valid<=0;ack_pending<=0;playing<=0;paused<=0;guiding<=0;finished<=0;step<=0;
            action_seen<=0;last_action_seq<=0;
            start_pulse<=0;
        end else begin
            response_valid<=0;
            start_pulse<=0;
            if(tick) tick_count<=0;else tick_count<=tick_count+1'b1;
            if(ack_pending) begin response_valid<=1;ack_pending<=0;end
            if(receiving && tick) begin
                if(!link_active || timeout_ms>=UPLOAD_TIMEOUT_MS-1) begin
                    receiving<=0;work<=0;error<=7;timeout_ms<=0;
                end else timeout_ms<=timeout_ms+1'b1;
            end
            if(work!=0) begin
                if(!valid_word || {1'b0,total_ms}+{3'b0,incoming_ms}>19'd180000) begin
                    work<=0;receiving<=0;error<=1;ack_pending<=1;
                end else begin
                    received<=received+1'b1;total_ms<=total_ms+incoming_ms;
                    crc<=crc_byte(crc_byte(crc_byte(crc,incoming[7:0]),incoming[15:8]),incoming[23:16]);
                    chunk<=chunk>>24;work<=work-1'b1;
                    if(work==1)ack_pending<=1;
                end
            end
            if(request_valid && work==0) begin
                error<=0;timeout_ms<=0;ack_pending<=1;
                if(request_type!=8'h34)action_seen<=0;
                case(request_type)
                    8'h30: if(request_length!=0)error<=1;
                    8'h31,8'h38: begin
                        if(request_length!=(request_type==8'h38 ? 8 : 7) || request_payload[15:0]==0 || request_payload[31:16]==0 ||
                           request_payload[31:16]>1023 || request_payload[55:48]>1 ||
                           request_type==8'h38 && request_payload[63:56]>11)error<=1;
                        else if((playing || guiding) && !finished)error<=2;
                        else if(receiving && token==request_payload[15:0] &&
                            (stage_absolute!=(request_type==8'h38) || expected_count!=request_payload[25:16] ||
                             expected_crc!=request_payload[47:32] || stage_timbre!=request_payload[48] ||
                             (request_type==8'h38 && stage_key!=request_payload[59:56])))error<=1;
                        else if(!(receiving && token==request_payload[15:0]))begin
                            if(finished)begin playing<=0;guiding<=0;end
                            receiving<=1;token<=request_payload[15:0];expected_count<=request_payload[25:16];
                            expected_crc<=request_payload[47:32];stage_timbre<=request_payload[48];
                            stage_absolute<=request_type==8'h38;
                            stage_key<=request_type==8'h38 ? request_payload[59:56] : 4'd0;
                            received<=0;crc<=16'hffff;total_ms<=0;
                        end
                    end
                    8'h32: begin
                        if(!receiving || token!=request_payload[15:0])error<=3;
                        else if(request_length!=7 && request_length!=10 && request_length!=13)error<=1;
                        else if(request_payload[31:16]>received ||
                            request_payload[31:16]+(request_length-4)/3>expected_count)error<=4;
                        else if(request_payload[31:16]==received)begin
                            work<=(request_length-4)/3;chunk<=request_payload[103:32];ack_pending<=0;
                        end else if(request_payload[31:16]+(request_length-4)/3>received)error<=4;
                    end
                    8'h33: begin
                        if(request_length!=2)error<=1;
                        else if(committed && active_token==request_payload[15:0] && !receiving)begin end
                        else if(!receiving || token!=request_payload[15:0])error<=3;
                        else if(received!=expected_count)error<=4;
                        else if(crc!=expected_crc)begin receiving<=0;error<=5;end
                        else begin
                            active_region<=~active_region;committed<=1;receiving<=0;
                            active_count<=expected_count;active_crc<=crc;active_token<=token;timbre<=stage_timbre;
                            active_absolute<=stage_absolute;key<=stage_key;
                            step<=0;finished<=0;load_wait<=2;elapsed_ms<=0;
                        end
                    end
                    8'h34: begin
                        if(request_length!=1 || request_payload[7:0]>4)error<=1;
                        else if(receiving)error<=2;
                        else if(request_payload[7:0]!=0 && !committed)error<=6;
                        else if(!action_seen || request_seq!=last_action_seq)begin
                            action_seen<=1;last_action_seq<=request_seq;
                            case(request_payload[7:0])
                                0:begin playing<=0;guiding<=0;paused<=0;finished<=0;end
                                1,4:begin playing<=request_payload[7:0]==1;guiding<=request_payload[7:0]==4;
                                    paused<=0;finished<=0;step<=0;elapsed_ms<=0;load_wait<=2;tick_count<=0;start_pulse<=1;end
                                2:if(playing || guiding)paused<=1;
                                3:if(playing || guiding)paused<=0;
                            endcase
                        end
                    end
                    8'h35:begin
                        if(request_length!=2)error<=1;
                        else if(receiving && token==request_payload[15:0])receiving<=0;
                    end
                    default:error<=1;
                endcase
            end
            if(load_wait!=0)begin
                load_wait<=load_wait-1'b1;
                if(load_wait==1)word_now<=word_read;
            end else if((playing || guiding) && !paused && !finished &&
                !(request_valid && request_type==8'h34))begin
                if((guiding && (pad==7 || strike_valid && strike_pad==pad)) ||
                   (playing && tick && elapsed_ms+16'd1>=duration_now))begin
                    elapsed_ms<=0;
                    if(step+1'b1>=active_count)begin finished<=1;step<=active_count;end
                    else begin step<=step+1'b1;load_wait<=2;end
                end else if(playing && tick)elapsed_ms<=elapsed_ms+1'b1;
            end
            if(stop_external)begin playing<=0;guiding<=0;paused<=0;finished<=0;end
        end
    end
endmodule
