// Algorithmic six-harmonic source with stored spectral parameters (not PCM).
// Coefficients are prepared one cycle before the wave is captured.
module expressive_texture #(
    parameter integer VOICES=32,
    parameter integer NORMALIZE_LEVEL=1,
    parameter integer NOISE_ENABLE=1
)(
    input wire clk,rst_n,prepare_en,step_en,active,
    input wire [4:0] slot,
    input wire [31:0] phase,
    input wire [6:0] note_index,
    input wire [15:0] note_age,
    input wire [7:0] expression,
    input wire timbre,
    output wire signed [15:0] wave_out,
    output wire signed [7:0] pitch_drift
);
    localparam integer INDEX_BITS=VOICES>1 ? $clog2(VOICES) : 1;
    wire [INDEX_BITS-1:0] index=slot[INDEX_BITS-1:0];
    reg [31:0] random_state[0:VOICES-1];
    reg signed [17:0] air_fast[0:VOICES-1],air_slow[0:VOICES-1];
    reg signed [25:0] wander[0:VOICES-1];
    reg [11:0] weight[0:5];
    integer i;
    // Six12-bit coefficients per entry,1296 entries; no waveform samples.
    reg [71:0] coefficient_rom[0:1295];
    reg [71:0] lower_weights,upper_weights;
    wire [10:0] address=(timbre ? 11'd648 : 11'd0)+{4'd0,note_index}*11'd9+{8'd0,expression[7:5]};
    initial begin
        if(NORMALIZE_LEVEL)$readmemh("@FPGA_ROOT@/src/assets/e6a906e6_expression_normalized.mem",coefficient_rom);
        else $readmemh("@FPGA_ROOT@/src/assets/92fa240f_expression_raw.mem",coefficient_rom);
    end
    always @(posedge clk)if(prepare_en)begin
        lower_weights<=note_index<72 ? coefficient_rom[address] : 72'd0;
        upper_weights<=note_index<72 ? coefficient_rom[address+11'd1] : 72'd0;
    end
    // Oscillator leakage is calibrated in the spectral coefficients offline;
    // retain the shared fast source with no additional runtime multipliers.
    function signed [15:0] sine;
        input [31:0] p;
        reg [31:0] q;reg [15:0] t;reg signed [16:0] x;
        reg [16:0] magnitude;reg signed [17:0] curvature;reg signed [34:0] product;
        begin
            q=p+32'h40000000;t=q[31] ? {~q[30:16],1'b0} : {q[30:16],1'b0};
            x=$signed({t[15]^1'b1,t^16'h8000});magnitude=x<0 ? -x : x;
            curvature=18'sd65536-$signed({1'b0,magnitude});product=x*curvature;sine=product>>>15;
        end
    endfunction
    wire [4:0] fraction=expression[4:0];
    wire signed [15:0] harmonic[0:5];
    assign harmonic[0]=sine(phase);assign harmonic[1]=sine(phase<<1);
    assign harmonic[2]=sine((phase<<1)+phase);assign harmonic[3]=sine(phase<<2);
    assign harmonic[4]=sine((phase<<2)+phase);assign harmonic[5]=sine((phase<<2)+(phase<<1));
    wire signed [28:0] part[0:5];
    genvar g;
    generate for(g=0;g<6;g=g+1)begin: partials
        wire [11:0] a=lower_weights[g*12 +: 12],b=upper_weights[g*12 +: 12];
        wire signed [12:0] delta=$signed({1'b0,b})-$signed({1'b0,a});
        wire signed [18:0] product=delta*$signed({1'b0,fraction});
        always @(posedge clk or negedge rst_n)
            if(!rst_n)weight[g]<=0;
            else if(step_en)weight[g]<=a+(product>>>5);
        assign part[g]=harmonic[g]*$signed({1'b0,weight[g]});
    end endgenerate
    wire signed [31:0] tone=($signed(part[0])+$signed(part[1])+$signed(part[2])+
        $signed(part[3])+$signed(part[4])+$signed(part[5]))>>>12;
    wire signed [17:0] random_input=$signed(random_state[index][15:0]);
    wire signed [17:0] fast_next=air_fast[index]+((random_input-air_fast[index])>>>1);
    wire signed [17:0] slow_next=air_slow[index]+((random_input-air_slow[index])>>>3);
    wire signed [18:0] air_band=$signed(air_fast[index])-$signed(air_slow[index]);
    // Reuse the existing slow/DC states for a soft low/mid air component.
    // Keep both state updates unchanged, so switching to the bow does not
    // inherit a different random/filter history.
    wire signed [18:0] reed_air=$signed(air_slow[index])-(wander[index]>>>8);
    wire [5:0] settle=note_age>=4096 ? 0 : (16'd4095-note_age)>>6;
    wire [6:0] noise_gain=timbre ? 7'd8+{4'd0,expression[7:5]}+{4'd0,settle[5:3]} :
        7'd16+{3'd0,expression[7:4]};
    wire signed [18:0] air_source=timbre ? reed_air:air_band;
    wire signed [26:0] noise_product=air_source*$signed({1'b0,noise_gain});
    wire signed [31:0] combined=tone+(NOISE_ENABLE ? (noise_product>>>14):32'sd0);
    assign wave_out=!active ? 16'sd0 : combined>32767 ? 16'sh7fff : combined< -32768 ? 16'sh8000 : combined[15:0];
    wire signed [25:0] wander_input=$signed(random_input)<<<8;
    wire signed [25:0] drift_wide=wander[index]>>>14;
    assign pitch_drift=drift_wide>8 ? 8'sd8 : drift_wide< -8 ? -8'sd8 : drift_wide[7:0];
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)for(i=0;i<VOICES;i=i+1)begin
            random_state[i]<=32'h9e3779b9^(32'h045d9f3b*(i+1));air_fast[i]<=0;air_slow[i]<=0;wander[i]<=0;
        end else if(step_en)begin
            random_state[index]<={random_state[index][30:0],random_state[index][31]^random_state[index][21]^random_state[index][1]^random_state[index][0]};
            air_fast[index]<=fast_next;air_slow[index]<=slow_next;
            wander[index]<=wander[index]+((wander_input-wander[index])>>>12);
        end
    end
endmodule
