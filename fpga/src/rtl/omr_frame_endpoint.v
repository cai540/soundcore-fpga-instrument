// Commands 60 BEGIN(id16), 61 DATA(id16,offset8,1..11 bytes),
// 62 INFER(id16), 63 ABORT(id16). All frames already passed CRC validation.
// Reply payload: id16,status8,class8,margin32,received8,version8,model_crc32.
module omr_frame_endpoint #(
    parameter W1_FILE="omr_w1.hex",parameter B1_FILE="omr_b1.hex",
    parameter W2_FILE="omr_w2.hex",parameter B2_FILE="omr_b2.hex",
    parameter integer SHIFT1=4,parameter [31:0] MODEL_CRC=0
)(input wire clk,input wire rst_n,input wire request_valid,
  input wire [7:0] request_type,input wire [7:0] request_length,
  input wire [111:0] request_payload,
  output reg response_valid,output reg [111:0] response_payload);
    localparam WAIT=0,COPY=1,START=2,INFER=3,REPLY=4;
    reg [2:0] state;reg active,cancel;
    reg [15:0] glyph_id;reg [5:0] count;reg [3:0] copy_index,copy_length;
    reg [111:0] staged;reg [7:0] status,result_digit;reg [31:0] margin;
    wire [15:0] incoming_id=request_payload[15:0];
    wire core_busy,core_ready,result_valid;wire [3:0] result_class;wire [31:0] result_margin;
    wire [5:0] copy_address=count+copy_index;
    omr_symbol_mlp #(.W1_FILE(W1_FILE),.B1_FILE(B1_FILE),.W2_FILE(W2_FILE),.B2_FILE(B2_FILE),.SHIFT1(SHIFT1)) core(
      .clk(clk),.rst_n(rst_n&&!cancel),.load_valid(state==COPY),.load_address(copy_address[4:0]),
      .load_byte(staged[24+copy_index*8+:8]),.start(state==START),.load_ready(core_ready),.busy(core_busy),
      .score_valid(),.score_index(),.score(),.result_valid(result_valid),.result_class(result_class),.result_margin(result_margin));
    always @(posedge clk or negedge rst_n)begin
      if(!rst_n)begin state<=WAIT;active<=0;cancel<=0;glyph_id<=0;count<=0;copy_index<=0;copy_length<=0;
        staged<=0;status<=0;result_digit<=255;margin<=0;response_valid<=0;response_payload<=0;
      end else begin
        response_valid<=0;cancel<=0;
        if(request_valid&&request_type==8'h63&&request_length==2&&incoming_id==glyph_id)begin
          cancel<=1;active<=0;count<=0;status<=0;result_digit<=255;margin<=0;state<=REPLY;
        end else case(state)
          WAIT:if(request_valid)begin
            result_digit<=255;margin<=0;status<=0;state<=REPLY;
            if(request_type==8'h60)begin
              if(request_length!=2||incoming_id==0)status<=2;
              else begin glyph_id<=incoming_id;count<=0;active<=1;end
            end else if(!active||incoming_id!=glyph_id)status<=5;
            else if(request_type==8'h61)begin
              if(request_length<4||request_length>14)status<=2;
              else if(request_payload[23:16]!=count||count+request_length-3>32)begin status<=3;active<=0;end
              else begin staged<=request_payload;copy_index<=0;copy_length<=request_length-3;state<=COPY;end
            end else if(request_type==8'h62)begin
              if(request_length!=2)status<=2;
              else if(count!=32)status<=6;
              else state<=START;
            end else status<=7;
          end
          COPY:if(copy_index+1==copy_length)begin count<=count+copy_length;state<=REPLY;end
               else copy_index<=copy_index+1'b1;
          START:state<=INFER;
          INFER:if(result_valid)begin status<=1;result_digit<={4'd0,result_class};margin<=result_margin;active<=0;state<=REPLY;end
          REPLY:begin
            response_valid<=1;response_payload<={MODEL_CRC,8'd1,2'd0,count,margin,result_digit,status,glyph_id};state<=WAIT;
          end
          default:begin active<=0;state<=WAIT;end
        endcase
      end
    end
endmodule
