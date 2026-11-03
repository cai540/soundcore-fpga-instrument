// 32 independent voices with shared pitch preparation. One 256-clock audio
// frame captures all controls, prepares 32 steps in 64 clocks, then services
// the unchanged 128-clock voice engine. In-frame control changes apply to the
// next sample_tick, never to only the later voices of the current frame.
module playable_synth32 #(
    parameter integer EXPRESSION_TEXTURE=0,
    parameter integer NORMALIZE_LEVEL=1,
    parameter integer DIAGNOSTIC_AVAILABLE=0
) (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               sample_tick,
    input  wire [31:0]        gate,
    input  wire [223:0]       note_index,
    input  wire [255:0]       velocity,
    input  wire [255:0]       expression,
    input  wire [7:0]         bend,
    input  wire               timbre,
    input wire diagnostic_sine,
    output wire[5:0] active_count,
    output reg deadline_fault,
    output reg[8:0] max_frame_cycles,
    output wire signed [15:0] sample_out,
    output wire               sample_valid
);
    wire signed [8:0] bend_delta = $signed({1'b0, bend}) - 9'sd128;
    wire signed [17:0] bend_ratio_signed =
        18'sd65536 + bend_delta * 9'sd30;
    wire [16:0] bend_ratio = bend_ratio_signed[16:0];
    reg [223:0] note_frame;
    reg [31:0] gate_frame;
    reg [255:0] velocity_frame;
    reg [255:0] expression_frame;
    reg timbre_frame;
    reg [16:0] ratio_frame;
    reg [1023:0] steps;
    reg [31:0] effective_gate;
    reg preparing,store_stage,core_tick,product_gate;
    reg [4:0] pitch_slot;
    reg [48:0] bent_product;
    wire [31:0] base_step;
    reg frame_busy;reg[8:0] frame_cycles;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin frame_busy<=0;frame_cycles<=0;deadline_fault<=0;max_frame_cycles<=0;end
        else begin
            if(sample_tick)begin if(frame_busy)deadline_fault<=1;frame_busy<=1;frame_cycles<=0;end
            else if(frame_busy)begin
                if(frame_cycles!=511)frame_cycles<=frame_cycles+1'b1;
                if(sample_valid)begin frame_busy<=0;if(frame_cycles>max_frame_cycles)max_frame_cycles<=frame_cycles;end
            end
        end
    end
    note_step_table72 lookup (
        .note_index(note_frame[pitch_slot*7 +: 7]),.phase_step(base_step)
    );

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            note_frame<=0;gate_frame<=0;velocity_frame<=0;timbre_frame<=1;
            expression_frame<=0;
            ratio_frame<=17'd65536;steps<=0;effective_gate<=0;
            preparing<=0;store_stage<=0;core_tick<=0;product_gate<=0;
            pitch_slot<=0;bent_product<=0;
        end else begin
            core_tick<=0;
            if(sample_tick)begin
                note_frame<=note_index;gate_frame<=gate;
                velocity_frame<=velocity;timbre_frame<=timbre;
                expression_frame<=expression;
                ratio_frame<=bend_ratio;
                preparing<=1;store_stage<=0;pitch_slot<=0;
            end else if(preparing && !store_stage)begin
                // The only wide pitch multiplication; do not duplicate this
                // expression in per-voice generate blocks.
                bent_product<=base_step*ratio_frame;
                product_gate<=gate_frame[pitch_slot] && base_step!=32'd0;
                store_stage<=1;
            end else if(preparing)begin
                // Preserve the legacy fixed-point truncation exactly.
                steps[pitch_slot*32 +: 32]<=bent_product[47:16];
                effective_gate[pitch_slot]<=product_gate;
                store_stage<=0;
                if(pitch_slot==31)begin
                    preparing<=0;core_tick<=1;
                end else pitch_slot<=pitch_slot+1'b1;
            end
        end
    end

    poly_synth32_tm #(.EXPRESSION_TEXTURE(EXPRESSION_TEXTURE),.NORMALIZE_LEVEL(NORMALIZE_LEVEL),.DIAGNOSTIC_AVAILABLE(DIAGNOSTIC_AVAILABLE)) synth (
        .clk(clk), .rst_n(rst_n), .sample_tick(core_tick),
        .gate(effective_gate), .phase_step(steps),
        .velocity(velocity_frame), .timbre(timbre_frame),
        .expression(expression_frame),.pitch_index(note_frame),
        .diagnostic_sine(DIAGNOSTIC_AVAILABLE!=0 && diagnostic_sine),.active_count(active_count),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );
endmodule
