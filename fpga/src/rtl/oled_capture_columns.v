// Generated 16px Chinese tiles and paired 8px ASCII. Full glyph baseline.
module oled_capture_columns(
 input wire clk,input wire [87:0] payload,
 input wire timbre,input wire [2:0] bank,pad,
 input wire [2:0] page,input wire [6:0] column,output wire [7:0] pixels
);
 wire [7:0] stage=payload[15:8],progress=payload[23:16],midi=payload[79:72],level=payload[87:80];
 wire [15:0] position=payload[39:24],duration=payload[55:40],count=payload[71:56];
 wire [1:0] row=page[2:1];wire [2:0] slot=column[6:4];
 reg [31:0] tile;
 function [7:0] digit;input integer v;begin digit=8'd48+v%10;end endfunction
 function [31:0] pair;input [7:0] a,b;begin pair={16'hffff,a,b};end endfunction
 function [7:0] pitch_letter;input [7:0] m;begin case(m%12)
 0,1:pitch_letter="C";2,3:pitch_letter="D";4:pitch_letter="E";5,6:pitch_letter="F";
 7,8:pitch_letter="G";9,10:pitch_letter="A";default:pitch_letter="B";endcase end endfunction
 function sharp;input [7:0] m;begin case(m%12)1,3,6,8,10:sharp=1;default:sharp=0;endcase end endfunction
 always @* begin
  tile=0;
  if(row==0)begin case(stage)
8'd1: case(slot) 3'd0: tile=32'h0000624b; 3'd1: tile=32'h0000673a; 3'd2: tile=32'h00005f55; 3'd3: tile=32'h000097f3; default:tile=0;endcase
8'd2: case(slot) 3'd0: tile=32'h00009009; 3'd1: tile=32'h000062e9; 3'd2: tile=32'h00007247; 3'd3: tile=32'h00006bb5; default:tile=0;endcase
8'd3: case(slot) 3'd0: tile=32'h00008bc6; 3'd1: tile=32'h0000522b; 3'd2: tile=32'h000065cb; 3'd3: tile=32'h00005f8b; default:tile=0;endcase
8'd4: case(slot) 3'd0: tile=32'h000065cb; 3'd1: tile=32'h00005f8b; 3'd2: tile=32'h00005df2; 3'd3: tile=32'h00008bc6; 3'd4: tile=32'h0000522b; default:tile=0;endcase
8'd5: case(slot) 3'd0: tile=32'h0000539f; 3'd1: tile=32'h000058f0; 3'd2: tile=32'h00008bd5; 3'd3: tile=32'h0000542c; default:tile=0;endcase
8'd6: case(slot) 3'd0: tile=32'h000065cb; 3'd1: tile=32'h00005f8b; 3'd2: tile=32'h00008bd5; 3'd3: tile=32'h0000542c; default:tile=0;endcase
8'd7: case(slot) 3'd0: tile=32'h00004fee; 3'd1: tile=32'h00006b63; 3'd2: tile=32'h000065cb; 3'd3: tile=32'h00005f8b; default:tile=0;endcase
8'd8: case(slot) 3'd0: tile=32'h00008bfb; 3'd1: tile=32'h000053d6; 3'd2: tile=32'h000097f3; 3'd3: tile=32'h00009891; default:tile=0;endcase
8'd9: case(slot) 3'd0: tile=32'h00004f20; 3'd1: tile=32'h00005165; 3'd2: tile=32'h00008bbe; 3'd3: tile=32'h00005907; default:tile=0;endcase
8'd10: case(slot) 3'd0: tile=32'h000065cb; 3'd1: tile=32'h00005f8b; 3'd2: tile=32'h00006f14; 3'd3: tile=32'h0000594f; default:tile=0;endcase
8'd11: case(slot) 3'd0: tile=32'h00004eae; 3'd1: tile=32'h0000706f; 3'd2: tile=32'h00006307; 3'd3: tile=32'h00005f15; default:tile=0;endcase
8'd12: case(slot) 3'd0: tile=32'h000065cb; 3'd1: tile=32'h00005f8b; 3'd2: tile=32'h00006682; 3'd3: tile=32'h0000505c; default:tile=0;endcase
8'd13: case(slot) 3'd0: tile=32'h000065cb; 3'd1: tile=32'h00005f8b; 3'd2: tile=32'h00007ed3; 3'd3: tile=32'h0000675f; default:tile=0;endcase
   default:tile=0;
  endcase
  if(stage>=10 && slot>=4)case(slot)
   4:tile=pair(digit(position/100),digit(position/10));
   5:tile=pair(digit(position),"/");
   6:tile=pair(digit(duration/100),digit(duration/10));
   7:tile=pair(digit(duration)," ");default:tile=0;endcase
  end
  else if(row==1)begin
   if(stage==1 || stage==2 || stage==5 || stage==6)case(slot)
    0:tile=pair(digit(position/6000),digit(position/600));
    1:tile=pair(":",digit(position/100));2:tile=pair(digit(position/10),"/");
    3:tile=pair(digit(duration/6000),digit(duration/600));
    4:tile=pair(":",digit(duration/100));5:tile=pair(digit(duration/10)," ");
    6:tile=stage!=1 ? 0 : level>240 ? 32'h8fc7 : level<8 ? 32'h504f : 32'h6b63;
    7:tile=stage!=1 ? 0 : level>240 ? 32'h5f3a : level<8 ? 32'h5f31 : 32'h5e38;
    default:tile=0;endcase
   else if(stage==3)case(slot)
    0:tile=32'h8fdb;1:tile=32'h5ea6;2:tile=pair(digit(progress/100),digit(progress/10));
    3:tile=pair(digit(progress),"%");default:tile=0;endcase
   else if(stage==4)case(slot)
    0:tile=32'h5171;1:tile=pair(digit(count/100),digit(count/10));2:tile=pair(digit(count)," ");
    3:tile=32'h4e2a;4:tile=32'h97f3;5:tile=32'h5f85;6:tile=32'h4f20;7:tile=32'h5165;default:tile=0;endcase
   else if(stage==7)case(slot)
    0:tile=32'h5f53;1:tile=32'h524d;
    2:tile=midi==255 ? pair("-","-") : pair(pitch_letter(midi),sharp(midi)?"#":" ");
    3:tile=midi==255 ? 0 : pair(digit(midi/12-1)," ");default:tile=0;endcase
   else if(stage==8)case(slot)0:tile=32'h8bf7;1:tile=32'h7a0d;2:tile=32'h5019;default:tile=0;endcase
   else if(stage==9)case(slot)
    0:tile=pair(digit(position/100),digit(position/10));1:tile=pair(digit(position),"/");
    2:tile=pair(digit(duration/100),digit(duration/10));3:tile=pair(digit(duration)," ");
    4:tile=32'h4e2a;5:tile=32'h97f3;default:tile=0;endcase
   else if(stage>=10)case(slot)
    0:tile=timbre ? 32'h53e3:32'h4e8c;1:tile=timbre ? 32'h7434:32'h80e1;
    3:tile=32'h533a;4:tile=pair(digit(bank+1)," ");
    5:tile=32'h952e;6:tile=pair(pad<7 ? digit(pad+1):"-"," ");default:tile=0;endcase
  end
  else if(row==3)begin case(stage)
8'd1: case(slot) 3'd0: tile=32'h00005bf9; 3'd1: tile=32'h0000624b; 3'd2: tile=32'h0000673a; 3'd3: tile=32'h00006e05; 3'd4: tile=32'h00006670; 3'd5: tile=32'h000054fc; 3'd6: tile=32'h00005531; default:tile=0;endcase
8'd2: case(slot) 3'd0: tile=32'h0000624b; 3'd1: tile=32'h0000673a; 3'd2: tile=32'h00009009; 3'd3: tile=32'h00006bb5; 3'd4: tile=32'h0000540e; 3'd5: tile=32'h00008bc6; 3'd6: tile=32'h0000522b; default:tile=0;endcase
8'd3: case(slot) 3'd0: tile=32'h00006b63; 3'd1: tile=32'h00005728; 3'd2: tile=32'h00006574; 3'd3: tile=32'h00007406; 3'd4: tile=32'h000097f3; 3'd5: tile=32'h00009ad8; 3'd6: tile=32'h00008282; 3'd7: tile=32'h0000594f; default:tile=0;endcase
8'd4: case(slot) 3'd0: tile=32'h0000624b; 3'd1: tile=32'h0000673a; 3'd2: tile=32'h00006838; 3'd3: tile=32'h00005bf9; 3'd4: tile=32'h0000540e; 3'd5: tile=32'h00004f20; 3'd6: tile=32'h00005165; default:tile=0;endcase
8'd5: case(slot) 3'd0: tile=32'h0000539f; 3'd1: tile=32'h000058f0; 3'd2: tile=32'h00005bf9; 3'd3: tile=32'h00007167; 3'd4: tile=32'h0000540c; 3'd5: tile=32'h000065f6; 3'd6: tile=32'h000095f4; 3'd7: tile=32'h00008f74; default:tile=0;endcase
8'd6: case(slot) 3'd0: tile=32'h000053c2; 3'd1: tile=32'h00008003; 3'd2: tile=32'h000097f3; 3'd3: tile=32'h000053ef; 3'd4: tile=32'h00004fee; 3'd5: tile=32'h00006b63; 3'd6: tile=32'h000097f3; 3'd7: tile=32'h00007b26; default:tile=0;endcase
8'd7: case(slot) 3'd0: tile=32'h0000624b; 3'd1: tile=32'h0000673a; 3'd2: tile=32'h00004fee; 3'd3: tile=32'h00006b63; 3'd4: tile=32'h0000652f; 3'd5: tile=32'h00006301; 3'd6: tile=32'h000064a4; 3'd7: tile=32'h00009500; default:tile=0;endcase
8'd8: case(slot) 3'd0: tile=32'h00006587; 3'd1: tile=32'h00004ef6; 3'd2: tile=32'h00006700; 3'd3: tile=32'h0000957f; 3'd4: tile=32'h00004e09; 3'd5: tile=32'h00005206; 3'd6: tile=32'h0000949f; default:tile=0;endcase
8'd9: case(slot) 3'd0: tile=32'h00005b8c; 3'd1: tile=32'h00006210; 3'd2: tile=32'h0000540e; 3'd3: tile=32'h000053ef; 3'd4: tile=32'h00006f14; 3'd5: tile=32'h0000594f; 3'd6: tile=32'h00006307; 3'd7: tile=32'h00005f15; default:tile=0;endcase
   default:tile=0;
  endcase end
 end
 wire paired=tile[31:16]==16'hffff;
 wire [15:0] unicode=paired ? (column[3] ? {8'd0,tile[7:0]} : {8'd0,tile[15:8]}) : tile[15:0];
 reg [7:0] font_id;
 always @*begin case(unicode)
16'h624b: font_id=8'd1;
16'h673a: font_id=8'd2;
16'h5f55: font_id=8'd3;
16'h97f3: font_id=8'd4;
16'h9009: font_id=8'd5;
16'h62e9: font_id=8'd6;
16'h7247: font_id=8'd7;
16'h6bb5: font_id=8'd8;
16'h8bc6: font_id=8'd9;
16'h522b: font_id=8'd10;
16'h65cb: font_id=8'd11;
16'h5f8b: font_id=8'd12;
16'h5df2: font_id=8'd13;
16'h539f: font_id=8'd14;
16'h58f0: font_id=8'd15;
16'h8bd5: font_id=8'd16;
16'h542c: font_id=8'd17;
16'h4fee: font_id=8'd18;
16'h6b63: font_id=8'd19;
16'h8bfb: font_id=8'd20;
16'h53d6: font_id=8'd21;
16'h9891: font_id=8'd22;
16'h4f20: font_id=8'd23;
16'h5165: font_id=8'd24;
16'h8bbe: font_id=8'd25;
16'h5907: font_id=8'd26;
16'h6f14: font_id=8'd27;
16'h594f: font_id=8'd28;
16'h4eae: font_id=8'd29;
16'h706f: font_id=8'd30;
16'h6307: font_id=8'd31;
16'h5f15: font_id=8'd32;
16'h6682: font_id=8'd33;
16'h505c: font_id=8'd34;
16'h7ed3: font_id=8'd35;
16'h675f: font_id=8'd36;
16'h5bf9: font_id=8'd37;
16'h6e05: font_id=8'd38;
16'h6670: font_id=8'd39;
16'h54fc: font_id=8'd40;
16'h5531: font_id=8'd41;
16'h540e: font_id=8'd42;
16'h5728: font_id=8'd43;
16'h6574: font_id=8'd44;
16'h7406: font_id=8'd45;
16'h9ad8: font_id=8'd46;
16'h8282: font_id=8'd47;
16'h6838: font_id=8'd48;
16'h7167: font_id=8'd49;
16'h540c: font_id=8'd50;
16'h65f6: font_id=8'd51;
16'h95f4: font_id=8'd52;
16'h8f74: font_id=8'd53;
16'h53c2: font_id=8'd54;
16'h8003: font_id=8'd55;
16'h53ef: font_id=8'd56;
16'h7b26: font_id=8'd57;
16'h652f: font_id=8'd58;
16'h6301: font_id=8'd59;
16'h64a4: font_id=8'd60;
16'h9500: font_id=8'd61;
16'h6587: font_id=8'd62;
16'h4ef6: font_id=8'd63;
16'h6700: font_id=8'd64;
16'h957f: font_id=8'd65;
16'h4e09: font_id=8'd66;
16'h5206: font_id=8'd67;
16'h949f: font_id=8'd68;
16'h5b8c: font_id=8'd69;
16'h6210: font_id=8'd70;
16'h8fdb: font_id=8'd71;
16'h5ea6: font_id=8'd72;
16'h5171: font_id=8'd73;
16'h4e2a: font_id=8'd74;
16'h5f85: font_id=8'd75;
16'h5f53: font_id=8'd76;
16'h524d: font_id=8'd77;
16'h53e3: font_id=8'd78;
16'h7434: font_id=8'd79;
16'h4e8c: font_id=8'd80;
16'h80e1: font_id=8'd81;
16'h533a: font_id=8'd82;
16'h952e: font_id=8'd83;
16'h6536: font_id=8'd84;
16'h504f: font_id=8'd85;
16'h5f31: font_id=8'd86;
16'h5e38: font_id=8'd87;
16'h8fc7: font_id=8'd88;
16'h5f3a: font_id=8'd89;
16'h8d77: font_id=8'd90;
16'h6b62: font_id=8'd91;
16'h8bf7: font_id=8'd92;
16'h7a0d: font_id=8'd93;
16'h5019: font_id=8'd94;
16'h0020: font_id=8'd95;
16'h0021: font_id=8'd96;
16'h0022: font_id=8'd97;
16'h0023: font_id=8'd98;
16'h0024: font_id=8'd99;
16'h0025: font_id=8'd100;
16'h0026: font_id=8'd101;
16'h0027: font_id=8'd102;
16'h0028: font_id=8'd103;
16'h0029: font_id=8'd104;
16'h002a: font_id=8'd105;
16'h002b: font_id=8'd106;
16'h002c: font_id=8'd107;
16'h002d: font_id=8'd108;
16'h002e: font_id=8'd109;
16'h002f: font_id=8'd110;
16'h0030: font_id=8'd111;
16'h0031: font_id=8'd112;
16'h0032: font_id=8'd113;
16'h0033: font_id=8'd114;
16'h0034: font_id=8'd115;
16'h0035: font_id=8'd116;
16'h0036: font_id=8'd117;
16'h0037: font_id=8'd118;
16'h0038: font_id=8'd119;
16'h0039: font_id=8'd120;
16'h003a: font_id=8'd121;
16'h003b: font_id=8'd122;
16'h003c: font_id=8'd123;
16'h003d: font_id=8'd124;
16'h003e: font_id=8'd125;
16'h003f: font_id=8'd126;
16'h0040: font_id=8'd127;
16'h0041: font_id=8'd128;
16'h0042: font_id=8'd129;
16'h0043: font_id=8'd130;
16'h0044: font_id=8'd131;
16'h0045: font_id=8'd132;
16'h0046: font_id=8'd133;
16'h0047: font_id=8'd134;
16'h0048: font_id=8'd135;
16'h0049: font_id=8'd136;
16'h004a: font_id=8'd137;
16'h004b: font_id=8'd138;
16'h004c: font_id=8'd139;
16'h004d: font_id=8'd140;
16'h004e: font_id=8'd141;
16'h004f: font_id=8'd142;
16'h0050: font_id=8'd143;
16'h0051: font_id=8'd144;
16'h0052: font_id=8'd145;
16'h0053: font_id=8'd146;
16'h0054: font_id=8'd147;
16'h0055: font_id=8'd148;
16'h0056: font_id=8'd149;
16'h0057: font_id=8'd150;
16'h0058: font_id=8'd151;
16'h0059: font_id=8'd152;
16'h005a: font_id=8'd153;
16'h005b: font_id=8'd154;
16'h005c: font_id=8'd155;
16'h005d: font_id=8'd156;
16'h005e: font_id=8'd157;
16'h005f: font_id=8'd158;
16'h0060: font_id=8'd159;
16'h0061: font_id=8'd160;
16'h0062: font_id=8'd161;
16'h0063: font_id=8'd162;
16'h0064: font_id=8'd163;
16'h0065: font_id=8'd164;
16'h0066: font_id=8'd165;
16'h0067: font_id=8'd166;
16'h0068: font_id=8'd167;
16'h0069: font_id=8'd168;
16'h006a: font_id=8'd169;
16'h006b: font_id=8'd170;
16'h006c: font_id=8'd171;
16'h006d: font_id=8'd172;
16'h006e: font_id=8'd173;
16'h006f: font_id=8'd174;
16'h0070: font_id=8'd175;
16'h0071: font_id=8'd176;
16'h0072: font_id=8'd177;
16'h0073: font_id=8'd178;
16'h0074: font_id=8'd179;
16'h0075: font_id=8'd180;
16'h0076: font_id=8'd181;
16'h0077: font_id=8'd182;
16'h0078: font_id=8'd183;
16'h0079: font_id=8'd184;
16'h007a: font_id=8'd185;
16'h007b: font_id=8'd186;
16'h007c: font_id=8'd187;
16'h007d: font_id=8'd188;
16'h007e: font_id=8'd189;
 default:font_id=0;endcase end
 wire [12:0] address={font_id,page[0],4'd0}+(paired ? {10'd0,column[2:0]} : {9'd0,column[3:0]});
 reg [7:0] font [0:8191];reg [7:0] glyph;
 initial $readmemh("@FPGA_ROOT@/src/assets/6b755b18_capture_font.mem",font);
 always @(posedge clk)glyph<=font[address];
 wire [6:0] x=column;
 wire progress_fill=stage==1 ? {1'b0,x} < level[7:1] : stage==9 ?
  ({9'd0,x}*duration < {16'd0,position}*16'd128) : stage==2 ?
  ({9'd0,x}*duration >= {16'd0,position}*16'd128) : x < progress*8'd127/100;
 wire bar=(column>=2 && column<=125);
 assign pixels=row==2 && stage<=9 ?
   (page[0]==0 ? (bar ? (progress_fill ? 8'hfc : 8'h84):0) : 0) : glyph;
endmodule
