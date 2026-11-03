// Small versioned tools protocol; bulk reads are repeatable and never generate sound.
// Every reply is14 bytes: schema,request,error plus command-specific data.
module product_tools_engine(
 input wire clk,rst_n,link_active,interrupt,
 input wire request_valid,input wire[7:0] request_type,request_length,
 input wire[111:0] request_payload,output reg response_valid,output reg[111:0] response_payload,
 input wire[5:0] active_voices,input wire deadline_fault,
 input wire[15:0] analysis_frame,input wire analysis_ready,input wire[511:0] wave_data,
 input wire[255:0] spectrum_data,input wire[511:0] phase_data,
 output reg diag_enabled,output reg[31:0] diag_gate,output reg[223:0] diag_notes,
 output reg[1:0] view_mode,output reg map_enabled,output reg[48:0] pad_map,output reg clear_voices,
 output reg record_start,record_stop,output reg[15:0] record_token,
 input wire recording,record_ready,input wire[16:0] record_samples,input wire[15:0] stored_token,record_crc,
 output wire[14:0] record_address,input wire[7:0] record_byte,
 input wire[6:0] bulk_index,output wire[7:0] bulk_byte,output reg response_bulk);
 reg bulk_mode;reg[14:0] ordinary_address;
 reg[511:0] frozen;reg[7:0] frozen_length;reg[15:0] snapshot_token;reg snapshot_valid;
 reg[31:0] silence_guard;reg[1:0] read_state;reg[3:0] byte_index;reg[15:0] read_offset;
 reg[7:0] read_command;reg[111:0] pending_reply;
 wire[7:0] value=request_payload[7:0];
 wire[15:0] req_token=request_payload[15:0],req_offset=request_payload[31:16];
 wire[16:0] record_bytes=(record_samples+1'b1)>>1;
 wire[5:0] snapshot_address=read_command==8'h48 ? bulk_index[5:0]-6'd5:read_offset[5:0]+byte_index;
 wire[7:0] snapshot_byte=frozen[snapshot_address*8 +: 8];
 reg[5:0] gates_count;
 wire[7:0] flags={1'b0,deadline_fault,analysis_ready,1'b0,map_enabled,1'b0,record_ready,recording};
 wire[6:0] live_address=bulk_index-5;
 wire[7:0] live_byte=bulk_index==0 ? {6'd0,view_mode-2'd1}:bulk_index==1 ? frozen_length:
  bulk_index==2 ? {2'd0,active_voices}:bulk_index==3 ? {2'd0,gates_count}:bulk_index==4 ? flags:
  live_address<frozen_length ? snapshot_byte:8'd0;
 assign record_address=bulk_mode ? read_offset[14:0]+bulk_index:ordinary_address;
 assign bulk_byte=read_command==8'h48 ? live_byte:({1'b0,read_offset}+bulk_index<record_bytes) ? record_byte:0;
 reg map_ok;integer p;
 always @* begin
  map_ok=request_length==8 && value<=2;
  for(p=0;p<7;p=p+1)if(request_payload[8+p*8 +: 8]>=(value==2 ? 7:72))map_ok=0;
  gates_count=0;for(p=0;p<32;p=p+1)gates_count=gates_count+diag_gate[p];
 end
 wire[111:0] status_reply={record_crc,stored_token,7'd0,record_samples,flags,
  6'd0,view_mode,2'd0,active_voices,2'd0,gates_count,8'd0,request_type,8'd1};
 function[111:0] error_reply;input[7:0] typ,error;begin error_reply={88'd0,error,typ,8'd1};end endfunction
 integer i;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   response_bulk<=0;bulk_mode<=0;response_valid<=0;response_payload<=0;diag_enabled<=0;diag_gate<=0;diag_notes<=0;
   view_mode<=0;map_enabled<=0;pad_map<=0;clear_voices<=0;record_start<=0;record_stop<=0;record_token<=0;
   frozen<=0;frozen_length<=0;snapshot_token<=0;snapshot_valid<=0;silence_guard<=0;
   read_state<=0;byte_index<=0;read_offset<=0;ordinary_address<=0;pending_reply<=0;read_command<=0;
   for(i=0;i<32;i=i+1)diag_notes[i*7 +: 7]<=24+i;
  end else begin
   response_valid<=0;clear_voices<=0;record_start<=0;record_stop<=0;
   if(!link_active || interrupt)view_mode<=0;
   if(diag_enabled)begin
    if(!link_active || interrupt || silence_guard>=32'd737280000)begin
     diag_enabled<=0;diag_gate<=0;clear_voices<=1;silence_guard<=0;
    end else silence_guard<=silence_guard+1'b1;
   end else silence_guard<=0;
   if(!link_active && recording)record_stop<=1;
   if(request_valid && read_state==0)begin
    response_bulk<=0;bulk_mode<=0;response_valid<=1;response_payload<=status_reply;
    case(request_type)
     8'h40,8'h52:if(request_length!=0)response_payload<=error_reply(request_type,3);
     8'h41:begin
      if(request_length!=1 || value>32)response_payload<=error_reply(request_type,3);
      else begin
       diag_enabled<=value!=0;diag_gate<=value==0?32'd0:32'hffffffff>>(32-value);silence_guard<=0;
       clear_voices<=diag_enabled || value!=0;
       for(i=0;i<32;i=i+1)diag_notes[i*7 +: 7]<=24+i;
      end
     end
     8'h42:begin
      if(request_length!=3 || value>31 || request_payload[15:8]>=72 || request_payload[23:16]>1 || !diag_enabled)
       response_payload<=error_reply(request_type,3);
      else begin diag_notes[value*7 +: 7]<=request_payload[14:8];diag_gate[value]<=request_payload[16];silence_guard<=0;end
     end
     8'h43:if(request_length!=1 || value>3)response_payload<=error_reply(request_type,3);else view_mode<=value[1:0];
     8'h44:begin
      if(request_length!=3 || value>2 || request_payload[23:8]==0)response_payload<=error_reply(request_type,3);
      else if(!analysis_ready)response_payload<=error_reply(request_type,7);
      else begin
       frozen<=value==0 ? wave_data:value==1?{256'd0,spectrum_data}:phase_data;
       frozen_length<=value==1?32:64;snapshot_token<=request_payload[23:8];snapshot_valid<=1;
       response_payload<={32'd0,request_payload[23:8],analysis_frame,8'd0,(value==1?8'd32:8'd64),value,8'd0,request_type,8'd1};
      end
     end
     8'h45:begin
      if(request_length!=4 || !snapshot_valid || req_token!=snapshot_token || req_offset>=frozen_length)
       response_payload<=error_reply(request_type,6);
      else begin
       // One shared byte mux, using the same bounded response assembler as
       // recording reads. Nine parallel variable selectors waste LUT/routing.
       response_valid<=0;read_offset<=req_offset;byte_index<=0;read_command<=request_type;
       pending_reply<=error_reply(request_type,0);pending_reply[39:24]<=req_offset;read_state<=1;
      end
     end
     8'h48:begin
      if(request_length!=1 || value>2)response_payload<=error_reply(request_type,3);
      else if(!analysis_ready)response_payload<=error_reply(request_type,7);
      else begin
       frozen<=value==0 ? wave_data:value==1 ? {256'd0,spectrum_data}:phase_data;
       frozen_length<=value==1 ? 32:64;view_mode<=value+1'b1;
       read_command<=request_type;bulk_mode<=0;response_bulk<=1;
       response_payload<=error_reply(request_type,0);response_payload[39:24]<=analysis_frame;
      end
     end
     8'h46:begin
      if(!map_ok)response_payload<=error_reply(request_type,3);
      else begin
       map_enabled<=value!=0;clear_voices<=1;
       for(i=0;i<7;i=i+1)pad_map[i*7 +: 7]<=value==2 ? 7'd120+request_payload[8+i*8 +: 3]:request_payload[8+i*8 +: 7];
      end
     end
     8'h47:begin
      if(request_length!=0)response_payload<=error_reply(request_type,3);
      else begin
       response_payload<=error_reply(request_type,0);response_payload[31:24]<={7'd0,map_enabled};
       for(i=0;i<7;i=i+1)response_payload[32+i*8 +: 8]<={1'b0,pad_map[i*7 +: 7]};
      end
     end
     8'h50:begin
      if(request_length!=2 || req_token==0)response_payload<=error_reply(request_type,3);
      else if(recording && req_token!=stored_token)response_payload<=error_reply(request_type,2);
      else if(!(stored_token==req_token && (recording || record_ready)))begin record_token<=req_token;record_start<=1;end
     end
     8'h51,8'h54:if(request_length!=0)response_payload<=error_reply(request_type,3);else record_stop<=1;
     8'h55:begin
      if(request_length!=4 || !record_ready || req_token!=stored_token || req_offset>=record_bytes)
       response_payload<=error_reply(request_type,6);
      else begin
       bulk_mode<=1;response_bulk<=1;read_offset<=req_offset;read_command<=request_type;
       response_payload<=error_reply(request_type,0);response_payload[39:24]<=req_offset;
      end
     end
     8'h53:begin
      if(request_length!=4 || !record_ready || req_token!=stored_token || req_offset>=record_bytes)
       response_payload<=error_reply(request_type,6);
      else begin
       response_valid<=0;read_offset<=req_offset;byte_index<=0;ordinary_address<=req_offset[14:0];
       pending_reply<=error_reply(request_type,0);pending_reply[39:24]<=req_offset;read_state<=1;read_command<=request_type;
      end
     end
     default:response_payload<=error_reply(request_type,2);
    endcase
   end
   case(read_state)
    1:read_state<=2;
    2:begin
     pending_reply[40+byte_index*8 +: 8]<=read_command==8'h45 ?
       (read_offset+byte_index<frozen_length ? snapshot_byte:8'd0):
       (read_offset+byte_index<record_bytes ? record_byte:8'd0);
     if(byte_index==8)read_state<=3;
     else begin byte_index<=byte_index+1'b1;if(read_command!=8'h45)ordinary_address<=read_offset+byte_index+1'b1;read_state<=1;end
    end
    3:begin response_payload<=pending_reply;response_valid<=1;read_state<=0;end
   endcase
  end
 end
endmodule
