// Two rows of 16x16 Chinese status plus seven 24-pixel force meters.
// Glyph bitmaps are generated from SimHei 16px for this embedded display.
module oled_status_ssd1315 #(
    parameter integer I2C_DIV = 18,
    parameter integer REFRESH_CYCLES = 2457600,
    parameter integer PAD_HOLD_CYCLES = 3686400, // 0.3 s at 12.288 MHz
    parameter integer BLE_IDLE_CYCLES = 73728000, // 6 s packet-liveness timeout
    parameter integer LONG_SONG_UI = 0,
    parameter integer LYRIC_OVERLAY = 0,
    parameter integer CAPTURE_OVERLAY = 0,
    parameter integer PANEL_MENU = 0,
    parameter integer PRODUCT_PANEL = 0,
    parameter integer PRODUCT_TOOLS = 0
) (
    input wire clk,
    input wire rst_n,
    input wire [2:0] bank,
    input wire [3:0] key,
    input wire [1:0] timbre,
    input wire tone_edit,
    input wire [3:0] tone_drive,
    input wire [4:0] volume,
    input wire vibrato,
    input wire [1:0] ui_state,
    input wire [7:0] menu_song,
    input wire menu_mode_select,menu_mode_cursor,demo_mode,
    input wire [10:0] guide_step,
    input wire [2:0] guide_target,
    input wire [2:0] guide_target_bank,
    input wire [1:0] playback_state,
    input wire auth_pending,
    input wire remote_write_allowed,
    input wire ble_frame_seen,
    input wire [6:0] pad_active,
    input wire [55:0] force_levels,
    input wire [7:0] contrast,
    input wire lyric_mode,
    input wire [6:0] lyric_phrase,
    input wire [4:0] lyric_character,
    input wire [7:0] lyric_progress,
    input wire [87:0] capture_payload,
    input wire[1:0] analysis_mode,
    input wire analysis_valid,
    input wire[511:0] analysis_wave,
    input wire[255:0] analysis_spectrum,
    input wire analysis_phase_bank,
    input wire[7:0] analysis_phase_pixels,
    output wire[9:0] analysis_phase_address,
    output reg shown_analysis_bank,
    output wire analysis_frame_latch,
    inout wire oled_scl,
    inout wire oled_sda,
    output reg ready,
    output reg nack_seen
);
    localparam [2:0] INIT=0, PAGE=1, DATA=2, IDLE=3,
                     CONTRAST_CMD=4, CONTRAST_VALUE=5;
    localparam integer TIMER_BITS = REFRESH_CYCLES < 2 ? 1 :
                                    $clog2(REFRESH_CYCLES);
    localparam integer PAD_TIMER_BITS = PAD_HOLD_CYCLES < 2 ? 1 :
                                        $clog2(PAD_HOLD_CYCLES+1);
    localparam integer BLE_TIMER_BITS = BLE_IDLE_CYCLES < 2 ? 1 :
                                        $clog2(BLE_IDLE_CYCLES+1);
    reg [BLE_TIMER_BITS-1:0] ble_idle_left;
    wire ble_recent = ble_idle_left != 0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) ble_idle_left <= 0;
        else if (ble_frame_seen) ble_idle_left <= BLE_IDLE_CYCLES;
        else if (ble_idle_left != 0) ble_idle_left <= ble_idle_left-1'b1;
    end
    reg [PAD_TIMER_BITS-1:0] pad_hold_left [0:6];
    wire [6:0] pad_visible;
    genvar pad;
    generate for (pad=0;pad<7;pad=pad+1) begin: pad_linger
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) pad_hold_left[pad] <= 0;
            else if (pad_active[pad]) pad_hold_left[pad] <= PAD_HOLD_CYCLES;
            else if (pad_hold_left[pad] != 0)
                pad_hold_left[pad] <= pad_hold_left[pad]-1'b1;
        end
        assign pad_visible[pad] = pad_active[pad] || pad_hold_left[pad] != 0;
    end endgenerate
    reg [2:0] phase;
    reg [7:0] shown_contrast;
    reg [4:0] init_index;
    reg [1:0] page_cmd;
    reg [2:0] page_index;
    reg [6:0] column;
    reg [TIMER_BITS-1:0] refresh_count;
    reg [7:0] oled_address;
    reg [1:0] nack_count;
    reg [3:0] shown_key;
    reg [2:0] shown_bank, shown_guide_target, shown_guide_target_bank;
    wire [2:0] display_target_bank = LONG_SONG_UI ? guide_target_bank : 3'd0;
    wire [1:0] display_playback_state = LONG_SONG_UI ? playback_state : 2'd0;
    reg [1:0] shown_timbre;
    reg shown_tone_edit;
    reg [3:0] shown_tone_drive;
    wire live_tone_edit=timbre==3 && tone_edit;
    reg shown_vibrato, shown_auth_pending;
    reg shown_remote_write_allowed;
    reg shown_ble_recent;
    reg shown_lyric_mode;
    reg [6:0] shown_lyric_phrase;
    reg [4:0] shown_lyric_character;
    reg [7:0] shown_lyric_progress;
    reg [4:0] shown_volume;
    wire [4:0] shown_value=shown_tone_edit ? {1'b0,shown_tone_drive}:shown_volume;
    reg [1:0] shown_ui_state;
    reg [7:0] shown_menu_song;
    reg[1:0] shown_analysis_mode;
    reg[511:0] shown_analysis_wave;
    reg[255:0] shown_analysis_spectrum;
    wire[7:0] analysis_pixels;
    wire status_changed;
    assign analysis_phase_address={(page_index>=2 ? page_index-3'd2:3'd0),column};
    assign analysis_frame_latch=PRODUCT_TOOLS!=0 && phase==IDLE && contrast==shown_contrast &&
        (status_changed || refresh_count==REFRESH_CYCLES-1);
    generate if(PRODUCT_TOOLS!=0)begin: analysis_overlay
        oled_analysis_columns columns(.clk(clk),.mode(shown_analysis_mode),.page(page_index),.column(column),
          .wave_data(shown_analysis_wave),.spectrum_data(shown_analysis_spectrum),
          .phase_pixels(analysis_phase_pixels),.pixels(analysis_pixels));
    end else begin:no_analysis_overlay assign analysis_pixels=0;end endgenerate
    reg shown_mode_select,shown_mode_cursor,shown_demo_mode;
    wire menu_active = PANEL_MENU != 0 && shown_ui_state == 2'd1;
    wire [7:0] menu_pixels;
    generate if(PANEL_MENU != 0)begin: menu_layer
        if(PRODUCT_PANEL != 0)begin: product_menu
            oled_panel_product_menu_columns menu(.clk(clk),.song(shown_menu_song[0]),
                .demo_mode(shown_demo_mode),.mode_menu(shown_mode_select),.mode_cursor(shown_mode_cursor),
                .page(page_index[1:0]),.column(column),.pixels(menu_pixels));
        end else begin: legacy_menu
            oled_panel_menu_columns menu(.clk(clk),.song(shown_menu_song[0]),
                .page(page_index[1:0]),.column(column),.pixels(menu_pixels));
        end
    end else begin: no_menu_layer
        assign menu_pixels=0;
    end endgenerate
    reg [1:0] shown_playback_state;
    reg [10:0] shown_guide_step;
    reg [6:0] shown_pad_visible;
    wire [34:0] force_buckets;
    reg [34:0] shown_force_buckets;
    reg [87:0] shown_capture;
    wire [87:0] capture_live=CAPTURE_OVERLAY!=0 ? capture_payload : 88'd0;
    wire capture_active=CAPTURE_OVERLAY!=0 && shown_capture[15:8]!=0;
    wire [7:0] capture_pixels;
    generate if(CAPTURE_OVERLAY!=0)begin:capture_layer
        oled_capture_columns capture(.clk(clk),.payload(shown_capture),.timbre(shown_timbre[0]),
            .bank(shown_bank),.pad(shown_guide_target),.page(page_index),.column(column),.pixels(capture_pixels));
    end else begin:no_capture_layer
        assign capture_pixels=0;
    end endgenerate
    genvar force_i;
    generate for (force_i=0;force_i<7;force_i=force_i+1) begin: meter_input
        assign force_buckets[force_i*5 +: 5] =
            force_levels[force_i*8+3 +: 5];
    end endgenerate
    assign status_changed = (PRODUCT_TOOLS!=0 && analysis_mode!=shown_analysis_mode) || (PRODUCT_PANEL != 0 && (menu_mode_select!=shown_mode_select ||
        menu_mode_cursor!=shown_mode_cursor || demo_mode!=shown_demo_mode)) ||
        (PANEL_MENU != 0 && menu_song != shown_menu_song) ||
        capture_live!=shown_capture || (LYRIC_OVERLAY != 0 &&
        (lyric_mode!=shown_lyric_mode || (lyric_mode &&
         (lyric_phrase!=shown_lyric_phrase || lyric_character!=shown_lyric_character ||
          lyric_progress[7:4]!=shown_lyric_progress[7:4] ||
          (lyric_progress==255)!=(shown_lyric_progress==255))))) || bank != shown_bank || key != shown_key ||
                          timbre != shown_timbre ||
                          live_tone_edit != shown_tone_edit ||
                          (live_tone_edit && tone_drive!=shown_tone_drive) ||
                          volume != shown_volume ||
                          vibrato != shown_vibrato ||
                          ui_state != shown_ui_state ||
                          display_playback_state != shown_playback_state ||
                          guide_step != shown_guide_step ||
                          guide_target != shown_guide_target ||
                          display_target_bank != shown_guide_target_bank ||
                          auth_pending != shown_auth_pending ||
                          remote_write_allowed != shown_remote_write_allowed ||
                          ble_recent != shown_ble_recent ||
                          pad_visible != shown_pad_visible ||
                          force_buckets != shown_force_buckets;
    reg tx_start, waiting;
    wire tx_busy, tx_done, tx_ack;
    reg [7:0] tx_control, tx_payload;
    wire [7:0] char_code = character(page_index,column[6:3]);

    oled_i2c_write2 #(.CLK_DIV(I2C_DIV)) writer (
        .clk(clk), .rst_n(rst_n), .start(tx_start),
        .address_write(oled_address),
        .control_byte(tx_control), .payload_byte(tx_payload),
        .scl(oled_scl), .sda(oled_sda),
        .busy(tx_busy), .done(tx_done), .ack_ok(tx_ack)
    );

    function [7:0] decimal_digit;
        input [5:0] number;
        begin decimal_digit = 8'h30 + number; end
    endfunction

    function [7:0] character;
        input [2:0] page;
        input [3:0] pos;
        begin
            character = 8'h20;
            case (page)
                0: case (pos)
                    0: character="B"; 1: character="A";
                    2: character="N"; 3: character="K";
                    5: character=decimal_digit({3'b000,bank}+1'b1);
                    8: character="V"; 9: character="O";
                    10: character="L";
                    12: character=decimal_digit(volume/10);
                    13: character=decimal_digit(volume%10);
                    default: character=" ";
                endcase
                1: case (pos)
                    0: character=timbre ? "H" : "E";
                    1: character=timbre ? "A" : "R";
                    2: character=timbre ? "R" : "H";
                    3: character=timbre ? "M" : "U";
                    5: character="V"; 6: character="I";
                    7: character="B";
                    9: character=vibrato ? "O" : "O";
                    10: character=vibrato ? "N" : "F";
                    11: character=vibrato ? " " : "F";
                    default: character=" ";
                endcase
                2: if (auth_pending) case (pos)
                    0: character="B"; 1: character="T";
                    3: character="K"; 4: character="5";
                    6: character="Y"; 7: character="E";
                    8: character="S";
                    default: character=" ";
                endcase else if (remote_write_allowed) case (pos)
                    0: character="B"; 1: character="T";
                    3: character="O"; 4: character="P";
                    5: character="E"; 6: character="N";
                    default: character=" ";
                endcase else case (pos)
                    0: character=ui_state==0 ? "P" :
                                 ui_state==1 ? "L" :
                                 ui_state==2 ? "R" : "P";
                    1: character=ui_state==0 ? "L" :
                                 ui_state==1 ? "I" :
                                 ui_state==2 ? "U" : "A";
                    2: character=ui_state==0 ? "A" :
                                 ui_state==1 ? "S" :
                                 ui_state==2 ? "N" : "U";
                    3: character=ui_state==0 ? "Y" :
                                 ui_state==1 ? "T" :
                                 ui_state==2 ? " " : "S";
                    4: character=ui_state==3 ? "E" : " ";
                    default: character=" ";
                endcase
                3: case (pos)
                    0: character="S"; 1: character="T";
                    2: character="E"; 3: character="P";
                    5: character=decimal_digit((guide_step/100)%10);
                    6: character=decimal_digit((guide_step/10)%10);
                    7: character=decimal_digit(guide_step%10);
                    9: character="P"; 10: character="A";
                    11: character="D";
                    13: character=decimal_digit({3'b000,guide_target}+1'b1);
                    default: character=" ";
                endcase
                7: case (pos)
                    1: character="1"; 3: character="2";
                    5: character="3"; 7: character="4";
                    9: character="5"; 11: character="6";
                    13: character="7";
                    default: character=" ";
                endcase
                default: character=" ";
            endcase
        end
    endfunction

    // Pages 4..6 are 24-pixel meters, starting exactly below the second
    // status row. Page 7 is reserved for full-size, legible digits.
    function [7:0] force_column;
        input [2:0] page;
        input [6:0] col;
        input [34:0] levels;
        reg [2:0] pad_index;
        reg [5:0] height;
        reg [5:0] threshold;
        integer pixel;
        begin
            force_column=0;
            pad_index=col/7'd16;
            height=0;
            threshold=0;
            if (pad_index<7 && col%7'd16>=5 && col%7'd16<=14) begin
                // A near-maximum measured force fills the available meter.
                height=levels[pad_index*5 +: 5]>24 ? 6'd24 :
                       {1'b0,levels[pad_index*5 +: 5]};
                for (pixel=0;pixel<8;pixel=pixel+1) begin
                    case (page)
                        3'd4: threshold=6'd24-pixel[5:0];
                        3'd5: threshold=6'd16-pixel[5:0];
                        3'd6: threshold=6'd8-pixel[5:0];
                        default: threshold=6'd0;
                    endcase
                    if (page>=4 && page<=6 && height>=threshold)
                        force_column[pixel]=1'b1;
                end
            end
            if (page==7 && pad_index<7) begin
                if (col[3:0]>=7 && col[3:0]<=11)
                    force_column=glyph_column("1"+pad_index,
                                              col[3:0]-4'd7);
            end
        end
    endfunction

    function [7:0] glyph_column;
        input [7:0] ch;
        input [2:0] col;
        reg [39:0] glyph;
        begin
            case (ch)
                "0": glyph=40'h3E5149453E; "1": glyph=40'h00427F4000;
                "2": glyph=40'h4261514946; "3": glyph=40'h2141494D33;
                "4": glyph=40'h1814127F10; "5": glyph=40'h2745454539;
                "6": glyph=40'h3C4A494931; "7": glyph=40'h0171090503;
                "8": glyph=40'h3649494936; "9": glyph=40'h464949291E;
                "A": glyph=40'h7E1111117E; "B": glyph=40'h7F49494936;
                "D": glyph=40'h7F4141413E; "E": glyph=40'h7F49494941;
                "F": glyph=40'h7F09090901; "H": glyph=40'h7F0808087F;
                "I": glyph=40'h00417F4100; "K": glyph=40'h7F08142241;
                "L": glyph=40'h7F40404040; "M": glyph=40'h7F020C027F;
                "N": glyph=40'h7F0408107F; "O": glyph=40'h3E4141413E;
                "P": glyph=40'h7F09090906; "R": glyph=40'h7F09192946;
                "S": glyph=40'h2649494932; "T": glyph=40'h01017F0101;
                "U": glyph=40'h3F4040403F; "V": glyph=40'h1F2040201F;
                "Y": glyph=40'h0304087008;
                default: glyph=40'h0000000000;
            endcase
            case (col)
                0: glyph_column=glyph[39:32];
                1: glyph_column=glyph[31:24];
                2: glyph_column=glyph[23:16];
                3: glyph_column=glyph[15:8];
                4: glyph_column=glyph[7:0];
                default: glyph_column=0;
            endcase
        end
    endfunction

    // IDs 1..31 are Chinese characters; 32..41 are digits 0..9.
    function [255:0] hanzi_bitmap;
        input [6:0] id;
        begin
            case (id)
                7'd1: hanzi_bitmap=256'h00C0C8C8D8F8C8CECCC8F8D8C8C8C000000000FE7E4A4A4A4A4A4A7E7E000000;
                7'd2: hanzi_bitmap=256'h0004FE0606266646C686C6763606040000407F4040584C46434143464C484000;
                7'd3: hanzi_bitmap=256'h0040407C6C6868686868686C7C4040000040405F5F5B5B7F7F5B5B5F5F404000;
                7'd4: hanzi_bitmap=256'h004060F0584E4EC8E8785840C00000000000007F664242434342424247602000;
                7'd5: hanzi_bitmap=256'h0000F0F80808080808080808F8F8000000007F7F20202020202020207F7F0000;
                7'd6: hanzi_bitmap=256'h0084D4D47C5454808454547C54544400000C0C1416121115D5733216040C0C00;
                7'd7: hanzi_bitmap=256'h0000101810101010101010181800000000303030303030303030303030303000;
                7'd8: hanzi_bitmap=256'h10101090FE101010DCFC646464FC000000213F0909197F603F0F0242427F0000;
                7'd9: hanzi_bitmap=256'h00F414F4B6F414F404F434BCB4F4E400005F5F5B5B7B3F3FC06F301F00274F00;
                7'd10: hanzi_bitmap=256'h0080848484FCFC848484FC848484800000014161391F03010101FF0101010100;
                7'd11: hanzi_bitmap=256'h00003030303E38F0F0383E30303000000000426222321A0F071A323262634200;
                7'd12: hanzi_bitmap=256'h0004C4C404EEEC0484EE6EC444C4440000407B7B484B7B494978484F7A784000;
                7'd13: hanzi_bitmap=256'h000084E4F494848484FCFC84848480000000602030180C06C37F7F0000000000;
                7'd14: hanzi_bitmap=256'h00180C262C3C24F4F82C26243C14040001010D091939090909C97F7F090D0100;
                7'd15: hanzi_bitmap=256'h003018CC6620C8C8487E7EC8C8C8C000000603FF0002021A1A02427F7F020200;
                7'd16: hanzi_bitmap=256'h0000E4C4848484848484848CFC00000000003F7F404040404040404141703000;
                7'd17: hanzi_bitmap=256'h00808C980008C8F89ECEF888888808000040603F2064444444467F4444444400;
                7'd18: hanzi_bitmap=256'h001010FE1010C88CFCCC8EECFC8C8C000046C27F0101C24A5E77323E6E424200;
                7'd19: hanzi_bitmap=256'h0040C4CC08405454545C7E54545444000000303F1008007F15151515DF7F0000;
                7'd20: hanzi_bitmap=256'h001010FE3000303808EA6E08083838000006427F0141414D6F39313D27614100;
                7'd21: hanzi_bitmap=256'h0030DCCE4880EC9C00A4BCFEA4FC300000027F3F12447C3F604A5A7F4A4A4800;
                7'd22: hanzi_bitmap=256'h0004CCFC8C8C2038EC2EECFC2C60E00000037F18183F40781F097F7F09CD7F00;
                7'd23: hanzi_bitmap=256'h004040C60C08000000FEFE00000000000000003F184C64380E03031E38604000;
                7'd24: hanzi_bitmap=256'h003030FE3000B8C8682E0E2868C8B8000046437F0100424242427E4242424000;
                7'd25: hanzi_bitmap=256'h00F8DCD0FEFED0D0D800F8F800FEFE00003E3E027F7F02323E000F0F407F7F00;
                7'd26: hanzi_bitmap=256'h00F0F01010FEFE1010FEFE1010F0F000007F7F21213F3F21213F3F21217F7F00;
                7'd27: hanzi_bitmap=256'h000000FC6464646464646464FC0C00000000007F22222222222222227F400000;
                7'd28: hanzi_bitmap=256'h002020FE3020007ED89888888CC060000046427F030100FF6B2B2B2B6B7F0000;
                7'd29: hanzi_bitmap=256'h0000E4E42424243C3C000000FEFE000000000303C2C2427E0E0000007F7F0000;
                7'd30: hanzi_bitmap=256'h00C0C0C0F8F8C0C0FED8C8C8C8C8C0000000D8CC464240603F3030180C060000;
                7'd31: hanzi_bitmap=256'h000000FEFE202020203E3E20206020000040701F03020202020202FE00000000;
                7'd32: hanzi_bitmap=256'h80F018080838F0000000000000000000031F183030180F000000000000000000;
                7'd33: hanzi_bitmap=256'h002030F8F800000000000000000000000000001F3F0000000000000000000000;
                7'd34: hanzi_bitmap=256'h0030180808F8700000000000000000000030383E333130000000000000000000;
                7'd35: hanzi_bitmap=256'h0030180888F87000000000000000000000183031311B1E000000000000000000;
                7'd36: hanzi_bitmap=256'h000080E030F80000000000000000000004070504043F04040000000000000000;
                7'd37: hanzi_bitmap=256'h00F0F8C8C888080000000000000000000819303030190F000000000000000000;
                7'd38: hanzi_bitmap=256'h0080C0F0988880000000000000000000001F313020301F060000000000000000;
                7'd39: hanzi_bitmap=256'h0008080888E8380000000000000000000000301E030000000000000000000000;
                7'd40: hanzi_bitmap=256'h00F0988888F8700000000000000000000C1F313131331E000000000000000000;
                7'd41: hanzi_bitmap=256'hE0F0180808B8F00000000000000000000001233B0F0300000000000000000000;
                7'd42: hanzi_bitmap=256'h000888FF880092DE7212FE325F9790000021213F00017F7F25253F25257F0100;
                7'd43: hanzi_bitmap=256'h000404FD2724E404307E8504FC1C040000180E0310101F1010180F0609103000;
                7'd44: hanzi_bitmap=256'h00405C5C53FC5454C07E0AFAFA0B00000000003E2A2A2A2A2A2A2A2A3E000000;
                7'd45: hanzi_bitmap=256'h00300CFF00C15D55555555555D41C1000000001F0000010131111F0101010000;
                7'd46: hanzi_bitmap=256'h004E4E4252D2D25353D25252424E4E00001010180C070000001F101010180800;
                7'd47: hanzi_bitmap=256'h0000FC3C2424E42404FF8484E525040000180F00080C1F10080C070D18101C00;
                7'd48: hanzi_bitmap=256'h00000000e0f01808080818100000000000000000070f18101010180800000000; // C
                7'd49: hanzi_bitmap=256'h00e0f018080808181040c07840c0780000070f1810101018081e03021e030200; // C#
                7'd50: hanzi_bitmap=256'h00000000f8f8080818f0e00000000000000000001f1f1010180f070000000000; // D
                7'd51: hanzi_bitmap=256'h00f8f8080818f0e00040c07840c07800001f1f1010180f07001e03021e030200; // D#
                7'd52: hanzi_bitmap=256'h0000000000f8f888888888000000000000000000001f1f101010100000000000; // E
                7'd53: hanzi_bitmap=256'h0000000000f8f808080808000000000000000000001f1f010101010000000000; // F
                7'd54: hanzi_bitmap=256'h00f8f8080808080040c07840c0780000001f1f01010101001e03021e03020000; // F#
                7'd55: hanzi_bitmap=256'h00000000e0f01808080818100000000000000000070f181011111f0f00000000; // G
                7'd56: hanzi_bitmap=256'he0f01808080818100040c07840c07800070f181011111f0f001e03021e030200; // G#
                7'd57: hanzi_bitmap=256'h0000000000e0f818f8e0000000000000000000181f07040404071f1800000000; // A
                7'd58: hanzi_bitmap=256'h0000e0f818f8e0000040c07840c07800181f07040404071f181e03021e030200; // A#
                7'd59: hanzi_bitmap=256'h00000000f8f8888888f8700000000000000000001f1f1010101f0f0000000000; // B
                7'd60: hanzi_bitmap=256'h002022e6040000fe52527e525202fe000000001f0c361e03000f09096f203f00; // 调
                7'd61: hanzi_bitmap=256'h0000202424242626fe2222222222000000010101010121213f01010101010100; // 手
                7'd62: hanzi_bitmap=256'h00c4f45c44c4047f4444ff64647fc40000003f08081f00321a0e7f060a123200; // 碟
                7'd63: hanzi_bitmap=256'h00406030706866e3e36c687030206000000020232f3b233f3f23332f27202000; // 金
                7'd64: hanzi_bitmap=256'h000001ff0beb6b6bebfb5b5bdb0f000000301f013c3d15151f1f151d753c3c00; // 属
                7'd65: hanzi_bitmap=256'h0080e09c949090ffff909090909080000021213111190d030305091911312100; // 失
                7'd66: hanzi_bitmap=256'h00000202faaaaaafabaaaafafa02000000042424371616060606161737240400; // 真
                default: hanzi_bitmap=257'd0;
            endcase
        end
    endfunction

    function [6:0] hanzi_at;
        input [1:0] row;
        input [2:0] slot;
        begin
            hanzi_at=0;
            case (row)
                0: case (slot)
                    0:hanzi_at=48+shown_key; 1:hanzi_at=60; // C调 / C#调
                    2:hanzi_at=33+shown_bank; // 1..5
                    3:hanzi_at=shown_tone_edit ? 65:1; 4:hanzi_at=shown_tone_edit ? 66:3;
                    5:hanzi_at=32+shown_value/10;
                    6:hanzi_at=32+shown_value%10;
                    7:hanzi_at=shown_vibrato ? 10 : 11; // 开/关
                    default:hanzi_at=0;
                endcase
                1: case (slot)
                    0:hanzi_at=shown_timbre==3 ? 63:shown_timbre==2 ? 61:(shown_timbre[0] ? 5:7);
                    1:hanzi_at=shown_timbre==3 ? 64:shown_timbre==2 ? 62:(shown_timbre[0] ? 6:8);
                    3:hanzi_at=12; 4:hanzi_at=13; // 蓝牙
                    5:hanzi_at=shown_ble_recent ? 16 : 14; // 已/等
                    6:hanzi_at=shown_ble_recent ? 17 : 15; // 连/待
                    7:hanzi_at=shown_ble_recent ? 18 : 0;  // 接
                    default:hanzi_at=0;
                endcase
                2: if (shown_auth_pending) case (slot)
                    0:hanzi_at=19; 1:hanzi_at=20; // 请按键确认
                    2:hanzi_at=21; 3:hanzi_at=22; 4:hanzi_at=23;
                    default:hanzi_at=0;
                endcase else if (shown_ble_recent) case (slot)
                    0:hanzi_at=12; 1:hanzi_at=13; // 蓝牙已连接
                    2:hanzi_at=16; 3:hanzi_at=17; 4:hanzi_at=18;
                    default:hanzi_at=0;
                endcase else case (slot)
                    0:hanzi_at=12; 1:hanzi_at=13; // 蓝牙等待
                    2:hanzi_at=14; 3:hanzi_at=15;
                    default:hanzi_at=0;
                endcase
                default:hanzi_at=0;
            endcase
        end
    endfunction

    wire [255:0] selected_hanzi =
        hanzi_bitmap(hanzi_at(page_index[2:1],column[6:4]));
    wire [7:0] hanzi_byte = page_index[0] ?
        selected_hanzi[127-8*column[3:0] -: 8] :
        selected_hanzi[255-8*column[3:0] -: 8];
    wire [7:0] lyric_byte;
    wire lyric_byte_ready;
    generate if(LYRIC_OVERLAY != 0)begin: lyric_layer
        oled_lyric_columns lyrics(.clk(clk),.rst_n(rst_n),.phrase(shown_lyric_phrase),
            .character(shown_lyric_character),.progress(shown_lyric_progress),
            .page(page_index[1:0]),.column(column),.pixels(lyric_byte),.ready(lyric_byte_ready));
    end else begin: no_lyric_layer
        assign lyric_byte=0;assign lyric_byte_ready=1;
    end endgenerate

    function [7:0] init_command;
        input [4:0] index;
        begin
            case (index)
                0:init_command=8'hAE; 1:init_command=8'hD5;
                2:init_command=8'h80; 3:init_command=8'hA8;
                4:init_command=8'h3F; 5:init_command=8'hD3;
                6:init_command=8'h00; 7:init_command=8'h40;
                8:init_command=8'h8D; 9:init_command=8'h14;
                10:init_command=8'h20; 11:init_command=8'h02;
                12:init_command=8'hA1; 13:init_command=8'hC8;
                14:init_command=8'hDA; 15:init_command=8'h12;
                16:init_command=8'h81; 17:init_command=contrast;
                18:init_command=8'hD9; 19:init_command=8'hF1;
                20:init_command=8'hDB; 21:init_command=8'h40;
                22:init_command=8'hA4; 23:init_command=8'hA6;
                default:init_command=8'hAF;
            endcase
        end
    endfunction

    always @(*) begin
        tx_control = 8'h00;
        tx_payload = 8'h00;
        case (phase)
            INIT: tx_payload=init_command(init_index);
            PAGE: case (page_cmd)
                0: tx_payload=8'hB0 | {5'b0,page_index};
                1: tx_payload=8'h00;
                default: tx_payload=8'h10;
            endcase
            DATA: begin
                tx_control=8'h40;
                tx_payload=menu_active ? (page_index<4 ? menu_pixels :
                    force_column(page_index,column,shown_force_buckets)) :
                    capture_active && (page_index<4 || shown_capture[15:8]<10) ? capture_pixels : (page_index>=4) ?
                           force_column(page_index,column,shown_force_buckets) :
                           ((LYRIC_OVERLAY != 0 && shown_lyric_mode) ? lyric_byte:hanzi_byte);
                // A play/pause mark uses only the unused right margin of the meters.
                if(PANEL_MENU != 0 && !menu_active && !capture_active && page_index==4 &&
                    column>=116 && column<124 && (shown_ui_state==2 || shown_ui_state==3 ||
                    shown_playback_state==1 || shown_playback_state==2)) begin
                    if(PRODUCT_PANEL != 0 && shown_playback_state==3)
                        tx_payload=8'h3c;
                    else if(shown_ui_state==3 || shown_playback_state==2)
                        tx_payload=(column<119 || column>=121) ? 8'h7e : 8'h00;
                    else case(column)
                        116:tx_payload=8'h7e;117:tx_payload=8'h3c;118:tx_payload=8'h3c;
                        119:tx_payload=8'h18;120:tx_payload=8'h18;121:tx_payload=8'h00;
                        default:tx_payload=8'h00;
                    endcase
                end
                if(PRODUCT_TOOLS!=0 && shown_analysis_mode!=0)tx_payload=analysis_pixels;
            end
            CONTRAST_CMD: tx_payload=8'h81;
            CONTRAST_VALUE: tx_payload=contrast;
            default: tx_payload=8'h00;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase <= INIT;
            init_index <= 0;
            page_cmd <= 0;
            page_index <= 0;
            column <= 0;
            refresh_count <= 0;
            oled_address <= 8'h78;
            nack_count <= 0;
            shown_bank <= 2;
            shown_key<=0;
            shown_timbre <= 0;
            shown_tone_edit<=0;shown_tone_drive<=0;
            shown_volume <= 0;
            shown_vibrato <= 0;
            shown_ui_state <= 0;
            shown_menu_song <= 0;
            shown_mode_select<=0;shown_mode_cursor<=0;shown_demo_mode<=0;
            shown_playback_state <= 0;
            shown_guide_step <= 0;
            shown_guide_target <= 0;
            shown_guide_target_bank <= 0;
            shown_auth_pending <= 0;
            shown_remote_write_allowed <= 0;
            shown_ble_recent <= 0;
            shown_lyric_mode<=0;shown_lyric_phrase<=0;shown_lyric_character<=0;shown_lyric_progress<=0;
            shown_pad_visible <= 0;
            shown_force_buckets <= 0;
            shown_capture<=0;
            shown_analysis_mode<=0;shown_analysis_wave<=0;shown_analysis_spectrum<=0;shown_analysis_bank<=0;
            shown_contrast <= 8'h7f;
            tx_start <= 0;
            waiting <= 0;
            ready <= 0;
            nack_seen <= 0;
        end else begin
            tx_start <= 0;
            if (phase == IDLE) begin
                if (contrast != shown_contrast) begin
                    phase <= CONTRAST_CMD;
                    shown_contrast <= contrast;
                end else if (status_changed || refresh_count == REFRESH_CYCLES-1) begin
                    refresh_count <= 0;
                    phase <= PAGE;
                    page_cmd <= 0;
                    page_index <= 0;
                    shown_bank <= bank;
                    shown_key<=key;
                    shown_timbre <= timbre;
                    shown_tone_edit<=live_tone_edit;shown_tone_drive<=tone_drive;
                    shown_volume <= volume;
                    shown_vibrato <= vibrato;
                    shown_ui_state <= ui_state;
                    shown_menu_song <= PANEL_MENU != 0 ? menu_song : 8'd0;
                    shown_mode_select<=PRODUCT_PANEL != 0 && menu_mode_select;
                    shown_mode_cursor<=PRODUCT_PANEL != 0 && menu_mode_cursor;
                    shown_demo_mode<=PRODUCT_PANEL != 0 && demo_mode;
                    shown_playback_state <= display_playback_state;
                    shown_guide_step <= guide_step;
                    shown_lyric_mode<=LYRIC_OVERLAY != 0 && lyric_mode;
                    shown_lyric_phrase<=lyric_phrase;shown_lyric_character<=lyric_character;
                    shown_lyric_progress<=lyric_progress==255 ? 8'd255:{lyric_progress[7:4],4'd0};
                    shown_guide_target <= guide_target;
                    shown_guide_target_bank <= display_target_bank;
                    shown_auth_pending <= auth_pending;
                    shown_remote_write_allowed <= remote_write_allowed;
                    shown_ble_recent <= ble_recent;
                    shown_pad_visible <= pad_visible;
                    shown_force_buckets <= force_buckets;
                    shown_capture<=capture_live;
                    if(PRODUCT_TOOLS!=0)begin
                        shown_analysis_mode<=analysis_mode;
                        if(analysis_valid)begin
                            shown_analysis_wave<=analysis_wave;shown_analysis_spectrum<=analysis_spectrum;
                            shown_analysis_bank<=analysis_phase_bank;
                        end
                    end
                end else
                    refresh_count <= refresh_count + 1'b1;
            end else if (!waiting && !tx_busy &&
                !(LYRIC_OVERLAY != 0 && shown_lyric_mode && phase==DATA && page_index<4 && !lyric_byte_ready)) begin
                tx_start <= 1;
                waiting <= 1;
            end else if (waiting && tx_done) begin
                waiting <= 0;
                if (!tx_ack) begin
                    nack_seen <= 1; // retry same byte on next transaction
                    if (phase != INIT) ready <= 0;
                    if (nack_count == 2) begin
                        // The display may have lost power or reset mid-frame.
                        // Probe the other address and replay initialization.
                        oled_address <= oled_address == 8'h78 ? 8'h7A : 8'h78;
                        nack_count <= 0;
                        phase <= INIT;
                        init_index <= 0;
                        page_cmd <= 0;
                        page_index <= 0;
                        column <= 0;
                    end else nack_count <= nack_count + 1'b1;
                end else begin
                    nack_count <= 0;
                    case (phase)
                    INIT: if (init_index == 24) begin
                        // The first frame uses the same atomic snapshot as
                        // every later frame, including tonic and octave.
                        phase <= IDLE;
                        refresh_count <= REFRESH_CYCLES-1;
                        page_cmd <= 0;
                    end else init_index <= init_index + 1'b1;
                    PAGE: if (page_cmd == 2) begin
                        phase <= DATA;
                        column <= 0;
                    end else page_cmd <= page_cmd + 1'b1;
                    DATA: if (column == 127) begin
                        if (page_index == 7) begin
                            ready <= 1;
                            phase <= IDLE;
                            refresh_count <= 0;
                        end else begin
                            page_index <= page_index + 1'b1;
                            page_cmd <= 0;
                            phase <= PAGE;
                        end
                    end else column <= column + 1'b1;
                    CONTRAST_CMD: phase <= CONTRAST_VALUE;
                    CONTRAST_VALUE: phase <= IDLE;
                    default: phase <= IDLE;
                    endcase
                end
            end
        end
    end
endmodule
