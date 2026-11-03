from pathlib import Path
R=Path(__file__).resolve().parents[1]
def edit(name, pairs):
 p=R/name;s=p.read_text('utf8')
 for a,b in pairs:
  assert a in s,(name,a[:80]);s=s.replace(a,b)
 p.write_text(s,encoding='utf8')
edit('rtl/product_tools_engine.v',[
 ('output reg[14:0] record_address,input wire[7:0] record_byte);','output wire[14:0] record_address,input wire[7:0] record_byte,\n input wire[6:0] bulk_index,output wire[7:0] bulk_byte,output reg response_bulk);\n reg bulk_mode;reg[14:0] ordinary_address;\n assign record_address=bulk_mode ? read_offset[14:0]+bulk_index:ordinary_address;\n assign bulk_byte=({1\'b0,read_offset}+bulk_index<record_bytes) ? record_byte:0;'),
 ('record_address<=','ordinary_address<='),
 ('response_valid<=0;response_payload<=0;','response_bulk<=0;bulk_mode<=0;response_valid<=0;response_payload<=0;'),
 ("32'd184320000","32'd737280000"),
 ('response_valid<=1;response_payload<=status_reply;','response_bulk<=0;bulk_mode<=0;response_valid<=1;response_payload<=status_reply;'),
 ("     8'h53:begin","     8'h55:begin\n      if(request_length!=4 || !record_ready || req_token!=stored_token || req_offset>=record_bytes)\n       response_payload<=error_reply(request_type,6);\n      else begin\n       bulk_mode<=1;response_bulk<=1;read_offset<=req_offset;\n       response_payload<=error_reply(request_type,0);response_payload[39:24]<=req_offset;\n      end\n     end\n     8'h53:begin")])
edit('rtl/ble_control_endpoint.v',[
 ('input wire[111:0] tools_response_payload','input wire[111:0] tools_response_payload,\n    input wire tools_response_bulk,input wire[7:0] tools_bulk_byte,output wire[6:0] tools_bulk_index'),
 ('reg [4:0] tx_index;','reg [7:0] tx_index;\n    assign tools_bulk_index=tx_index>=10 ? tx_index-10:0;'),
 ('else if (tx_index<5+response_len)\n                tx_byte=snapshot',"else if(response_type==8'h86 && tx_index>=10 && tx_index<133)tx_byte=tools_bulk_byte;\n            else if (tx_index<5+response_len)\n                tx_byte=snapshot"),
 ("frame_type<=8'h54","frame_type<=8'h55"),
 ("snapshot<=tools_response_payload;response_type<=8'h85;response_len<=14;\n                        response_crc<=crc_response(8'h85,response_seq,tools_response_payload,14);phase<=SEND;","snapshot<=tools_response_payload;response_type<=tools_response_bulk ? 8'h86:8'h85;response_len<=tools_response_bulk ? 128:14;\n                        response_crc<=tools_response_bulk ? 0:crc_response(8'h85,response_seq,tools_response_payload,14);phase<=SEND;"),
 ('SEND: if (tx_ready) begin',"SEND: if (tx_ready) begin\n                    if(response_type==8'h86 && !response_error && tx_index>=1 && tx_index<133)response_crc<=crc_next(response_crc,tx_byte);")])
edit('rtl/product_tools_subsystem.v',[
 ('output wire response_valid,output wire[111:0] response_payload,','output wire response_valid,output wire[111:0] response_payload,\n input wire[6:0] bulk_index,output wire[7:0] bulk_byte,output wire response_bulk,'),
 ('.response_valid(response_valid),.response_payload(response_payload),','.response_valid(response_valid),.response_payload(response_payload),.bulk_index(bulk_index),.bulk_byte(bulk_byte),.response_bulk(response_bulk),')])
edit('board/pressure_i2s_panel_oled_ble_experiment_top.v',[
 ('wire tools_request_valid,tools_response_valid;', 'wire tools_request_valid,tools_response_valid;\n    wire tools_response_bulk;wire[6:0] tools_bulk_index;wire[7:0] tools_bulk_byte;'),
 ('.response_valid(tools_response_valid),.response_payload(tools_response_payload),','.response_valid(tools_response_valid),.response_payload(tools_response_payload),\n          .response_bulk(tools_response_bulk),.bulk_index(tools_bulk_index),.bulk_byte(tools_bulk_byte),'),
 ('.tools_response_payload(tools_response_payload)', '.tools_response_payload(tools_response_payload),.tools_response_bulk(tools_response_bulk),.tools_bulk_index(tools_bulk_index),.tools_bulk_byte(tools_bulk_byte)')])
A='app/android/app/src/main/java/cn/soundcore/instrument/'
edit(A+'ProductTools.kt',[
 ('const val CANCEL=0x54','const val CANCEL=0x54;const val READ_RECORD_BULK=0x55'),
 ('type in STATUS..CANCEL','type in STATUS..READ_RECORD_BULK'),
 ('frame.type==RESPONSE && frame.payload.size==14','(frame.type==RESPONSE && frame.payload.size==14) || (request==READ_RECORD_BULK && frame.type==0x86 && frame.payload.size==128)')])
edit(A+'Protocol.kt',[
 ('ToolWire.READ_SNAPSHOT,ToolWire.READ_RECORD ->','ToolWire.READ_SNAPSHOT,ToolWire.READ_RECORD,ToolWire.READ_RECORD_BULK ->'),
 ('version != 1 || length > 14','version != 1 || length > (if((pending[2].toInt() and 255)==0x86)128 else 14)')])
