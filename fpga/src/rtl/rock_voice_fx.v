// Shared 2x nonlinear stage, then two low-pass poles at the 96 kHz subrate.
// Nine clocks per 48 kHz sample; the 224-clock modal source leaves 32 clocks.
// This is an original fixed-point implementation of standard soft saturation.
module rock_voice_fx #(
    parameter CURVE_FILE="D:/FPGA/Projects/soundcore_2026/rtl/rock_softclip.mem"
) (
    input wire clk,rst_n,enabled,input_valid,
    input wire signed [15:0] sample_in,
    input wire [3:0] drive,
    input wire [7:0] tone,
    output reg signed [15:0] sample_out,
    output reg sample_valid,
    output reg overflow
);
    reg [15:0] curve[0:1023];
    initial $readmemh(CURVE_FILE,curve);
    reg [3:0] stage;
    reg busy;
    reg signed [15:0] previous,current,midpoint;
    reg signed [31:0] scaled;
    reg [7:0] drive_smooth;
    reg [9:0] gain_q;
    reg [15:0] alpha_q;
    reg signed [23:0] low1,low2;
    wire [31:0] magnitude=scaled[31] ? -scaled:scaled;
    wire [9:0] curve_index=magnitude>32736 ? 10'd1023:magnitude[14:5];
    reg [15:0] curve_q;
    always @(posedge clk)curve_q<=curve[curve_index];
    wire signed [16:0] clipped=scaled[31] ? -$signed({1'b0,curve_q}):
        $signed({1'b0,curve_q});
    wire signed [24:0] target=$signed(clipped)<<<8;
    // One multiplier is shared by the two poles and the two subrate samples.
    wire second_pole=stage==4 || stage==8;
    wire signed [24:0] delta=second_pole ? $signed(low1)-$signed(low2):target-$signed(low1);
    wire signed [41:0] filter_product=delta*$signed({1'b0,alpha_q});
    wire signed [24:0] filtered=(second_pole ? $signed(low2):$signed(low1))+(filter_product>>>15);
    wire signed [31:0] input_for_drive=stage==1 ? $signed(midpoint):$signed(current);
    wire signed [31:0] driven=input_for_drive*$signed({1'b0,gain_q});
    wire signed [16:0] pair_sum=$signed(previous)+$signed(sample_in);
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            stage<=0;busy<=0;previous<=0;current<=0;midpoint<=0;scaled<=0;
            drive_smooth<=64;gain_q<=64;alpha_q<=4096;low1<=0;low2<=0;
            sample_out<=0;sample_valid<=0;overflow<=0;
        end else begin
            sample_valid<=0;
            if(!enabled)begin
                busy<=0;stage<=0;previous<=0;low1<=0;low2<=0;sample_out<=0;overflow<=0;
            end else if(input_valid && !busy)begin
                previous<=sample_in;current<=sample_in;midpoint<=pair_sum>>>1;
                if(drive_smooth<{drive,4'd0})drive_smooth<=drive_smooth+1'b1;
                else if(drive_smooth>{drive,4'd0})drive_smooth<=drive_smooth-1'b1;
                gain_q<=10'd64+{1'b0,drive_smooth,1'b0};
                alpha_q<=16'd512+{3'd0,tone,5'd0};
                busy<=1;stage<=1;
            end else if(busy)begin
                if(input_valid)overflow<=1;
                case(stage)
                    1:begin scaled<=driven>>>6;stage<=2;end
                    2:stage<=3; // Synchronous ROM read for the midpoint.
                    3:begin low1<=filtered[23:0];stage<=4;end
                    4:begin low2<=filtered[23:0];stage<=5;end
                    5:begin scaled<=driven>>>6;stage<=6;end
                    6:stage<=7; // Synchronous ROM read for the full sample.
                    7:begin low1<=filtered[23:0];stage<=8;end
                    8:begin
                        low2<=filtered[23:0];sample_out<=(filtered+25'sd128)>>>8;
                        sample_valid<=1;busy<=0;
                    end
                    default:begin busy<=0;overflow<=1;end
                endcase
            end
        end
    end
endmodule
