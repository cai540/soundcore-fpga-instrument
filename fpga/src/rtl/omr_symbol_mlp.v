// Binary 256 -> uint8 ReLU 64 -> signed scores 11. Native Gowin RTL.
// No floating point, CPU, softmax or API. Weight/bias files are trained exports.
module omr_symbol_mlp #(
    parameter W1_FILE="omr_w1.hex", parameter B1_FILE="omr_b1.hex",
    parameter W2_FILE="omr_w2.hex", parameter B2_FILE="omr_b2.hex",
    parameter integer SHIFT1=4
)(
    input wire clk,input wire rst_n,
    input wire load_valid,input wire [4:0] load_address,input wire [7:0] load_byte,
    input wire start,output wire load_ready,output reg busy,
    output reg score_valid,output reg [3:0] score_index,output reg signed [31:0] score,
    output reg result_valid,output reg [3:0] result_class,output reg [31:0] result_margin
);
    reg signed [7:0] weights1[0:16383];
    reg signed [7:0] weights2[0:703];
    reg signed [31:0] biases1[0:63],biases2[0:10];
    initial begin
        $readmemh(W1_FILE,weights1);$readmemh(W2_FILE,weights2);
        $readmemh(B1_FILE,biases1);$readmemh(B2_FILE,biases2);
    end
    localparam IDLE=0,B1_ADDR=1,B1_LOAD=2,F1_FETCH=3,F1_MAC=4,
               B2_ADDR=5,B2_LOAD=6,F2_FETCH=7,F2_MAC=8;
    reg [3:0] state;
    reg [7:0] bitmap[0:31],hidden[0:63];
    reg [5:0] neuron,feature2;
    reg [7:0] feature1;
    reg [3:0] class_id,best_class;
    reg signed [31:0] accumulator,best,second;
    reg signed [7:0] weight1_q,weight2_q;
    reg signed [31:0] bias1_q,bias2_q;
    wire [9:0] address2={class_id,feature2};
    // Synchronous ROM reads are deliberate: large weights infer block RAM.
    always @(posedge clk) begin
        weight1_q<=weights1[{neuron,feature1}];
        weight2_q<=weights2[address2];
        bias1_q<=biases1[neuron];bias2_q<=biases2[class_id];
        if(load_valid&&load_ready)bitmap[load_address]<=load_byte;
    end
    assign load_ready=!busy;
    wire pixel=bitmap[feature1[7:3]][feature1[2:0]];
    wire signed [31:0] sum1=accumulator+(pixel?{{24{weight1_q[7]}},weight1_q}:32'sd0);
    wire signed [8:0] activation2=$signed({1'b0,hidden[feature2]});
    wire signed [16:0] product2=activation2*$signed(weight2_q);
    wire signed [31:0] sum2=accumulator+{{15{product2[16]}},product2};
    wire [31:0] rounded1=sum1[31]?32'd0:($unsigned(sum1)+(SHIFT1>0?(32'd1<<(SHIFT1-1)):32'd0));
    wire [31:0] shifted1=rounded1>>SHIFT1;
    wire signed [31:0] next_best=sum2>best?sum2:best;
    wire signed [31:0] next_second=sum2>best?best:(sum2>second?sum2:second);
    wire [3:0] next_class=sum2>best?class_id:best_class;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            state<=IDLE;busy<=0;score_valid<=0;result_valid<=0;
            neuron<=0;feature1<=0;feature2<=0;class_id<=0;accumulator<=0;
            best<=32'sh80000000;second<=32'sh80000000;best_class<=0;
            result_class<=0;result_margin<=0;score_index<=0;score<=0;
        end else begin
            score_valid<=0;result_valid<=0;
            case(state)
                IDLE:if(start)begin busy<=1;neuron<=0;feature1<=0;state<=B1_ADDR;end
                B1_ADDR:state<=B1_LOAD;
                B1_LOAD:begin accumulator<=bias1_q;feature1<=0;state<=F1_FETCH;end
                F1_FETCH:state<=F1_MAC;
                F1_MAC:if(feature1==255)begin
                    hidden[neuron]<=shifted1>255?8'd255:shifted1[7:0];
                    if(neuron==63)begin
                        class_id<=0;feature2<=0;best<=32'sh80000000;second<=32'sh80000000;best_class<=0;state<=B2_ADDR;
                    end else begin neuron<=neuron+1'b1;state<=B1_ADDR;end
                end else begin accumulator<=sum1;feature1<=feature1+1'b1;state<=F1_FETCH;end
                B2_ADDR:state<=B2_LOAD;
                B2_LOAD:begin accumulator<=bias2_q;feature2<=0;state<=F2_FETCH;end
                F2_FETCH:state<=F2_MAC;
                F2_MAC:if(feature2==63)begin
                    score_valid<=1;score_index<=class_id;score<=sum2;
                    best<=next_best;second<=next_second;best_class<=next_class;
                    if(class_id==10)begin
                        result_valid<=1;result_class<=next_class;result_margin<=$unsigned(next_best)-$unsigned(next_second);
                        busy<=0;state<=IDLE;
                    end else begin class_id<=class_id+1'b1;state<=B2_ADDR;end
                end else begin accumulator<=sum2;feature2<=feature2+1'b1;state<=F2_FETCH;end
                default:begin busy<=0;state<=IDLE;end
            endcase
        end
    end
endmodule
