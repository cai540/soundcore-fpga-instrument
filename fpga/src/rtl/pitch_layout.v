// Layout2: 35 manual diatonic pitches per key, 72 exact internal chromatic pitches.
module pitch_layout(input wire [2:0] bank,pad,input wire [3:0] key,
    output wire [6:0] note_index,output wire valid);
    reg [3:0] semitone;
    always @*case(pad)
        0:semitone=0;1:semitone=2;2:semitone=4;3:semitone=5;
        4:semitone=7;5:semitone=9;6:semitone=11;default:semitone=15;
    endcase
    assign note_index={4'd0,bank}*7'd12+{3'd0,key}+{3'd0,semitone};
    assign valid=bank<5 && pad<7 && key<12 && note_index<72;
endmodule

module pitch_projection(input wire [6:0] note_index,input wire [3:0] key,
    output wire [2:0] bank,output reg [2:0] pad,output reg sharp,output wire valid);
    wire [7:0] relative={1'b0,note_index}+8'd12-{4'd0,key};
    wire [3:0] pitch_class=relative%8'd12;
    wire [6:0] offset=note_index>={3'd0,key} ? note_index-{3'd0,key}:7'd0;
    wire [3:0] octave=offset/7'd12;
    assign bank=octave>4 ? 3'd4:octave[2:0];
    assign valid=note_index<72 && key<12;
    always @*begin
        sharp=0;
        case(pitch_class)
            0:pad=0;1:begin pad=0;sharp=1;end
            2:pad=1;3:begin pad=1;sharp=1;end
            4:pad=2;5:pad=3;6:begin pad=3;sharp=1;end
            7:pad=4;8:begin pad=4;sharp=1;end
            9:pad=5;10:begin pad=5;sharp=1;end
            11:pad=6;default:pad=7;
        endcase
        if(!valid)pad=7;
    end
endmodule
