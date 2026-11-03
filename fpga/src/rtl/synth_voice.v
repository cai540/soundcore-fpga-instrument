// One independently controlled oscillator with a four-stage amplitude envelope.
// phase_step = round(note_hz * 2^32 / sample_rate_hz).
module synth_voice #(
    parameter integer RELEASE_SHIFT = 0,
    parameter integer INSTRUMENT_PRESETS = 0,
    parameter integer NATURAL_VIBRATO = 0,
    parameter integer EXPRESSION_TEXTURE = 0
) (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               sample_tick,
    input  wire               gate,
    input  wire [31:0]        phase_step,
    input  wire [7:0]         velocity,
    input  wire [7:0]         expression,
    input  wire [6:0]         pitch_index,
    input  wire               timbre,       // 0=saw, 1=triangle
    output reg  signed [15:0] sample_out
);
    localparam [1:0] OFF = 2'd0, ATTACK = 2'd1,
                     DECAY = 2'd2, SUSTAIN = 2'd3;
    localparam [15:0] SUSTAIN_LEVEL = 16'd20000;

    reg [31:0] phase;
    reg [15:0] envelope;
    reg [1:0]  state;
    reg        gate_last;
    reg        timbre_latched;
    reg [15:0] note_age;
    reg [15:0] attack_from;
    reg [23:0] expression_phase;
    reg [15:0] bow_noise;
    wire signed [7:0] texture_drift;
    wire signed [15:0] expression_sine=soft_sine({expression_phase,8'd0});
    wire signed [8:0] expression_round=(expression_sine>>>8)+texture_drift;
    wire [7:0] expression_strength = note_age<16'd4608 ? 0 :
        note_age>=16'd20928 ? 8'd255 : (note_age-16'd4608)>>6;
    wire signed [17:0] expression_depth=expression_round*$signed({1'b0,expression_strength});
    wire signed [50:0] expression_product = $signed({1'b0,phase_step})*expression_depth;
    wire signed [50:0] expression_delta = expression_product >>> (timbre_latched ? 23 : 21);
    wire [31:0] expressive_step = NATURAL_VIBRATO ? phase_step+expression_delta[31:0] : phase_step;
    wire selected_timbre = INSTRUMENT_PRESETS ? timbre_latched : timbre;
    // Both algorithmic instrument presets sustain while held. The reed-like
    // harmonica rises without a hammer transient; the erhu blooms more slowly.
    // The quadratic S curve has zero slope at both ends. Keep the envelope on
    // a legato/repeated gate, then rise to sustain without an accent/decay bump.
    `include "@FPGA_ROOT@/src/rtl/instrument_attack.vh"
    wire [15:0] sustain_target;
    wire [15:0] attack_peak;
    wire [15:0] attack_step;
    wire [15:0] decay_step;
    wire [4:0] release_shift_selected;
    generate if (INSTRUMENT_PRESETS) begin: instrument_envelopes
        assign sustain_target = timbre_latched ? 16'd28500 : 16'd26600;
        assign attack_peak = timbre_latched ? 16'd30000 : 16'd28000;
        assign attack_step = timbre_latched ? 16'd256 : 16'd96;
        assign decay_step = 16'd1;
        assign release_shift_selected = 5'd9;
    end else begin: legacy_envelope
        assign sustain_target = SUSTAIN_LEVEL;
        assign attack_peak = 16'hffff;
        assign attack_step = 16'd256;
        assign decay_step = 16'd32;
        assign release_shift_selected = RELEASE_SHIFT;
    end endgenerate

    wire [15:0] triangle_unsigned = phase[31]
        ? {~phase[30:16], 1'b0} : {phase[30:16], 1'b0};
    wire [31:0] harmonic_phase_double = phase << 1;
    wire [31:0] harmonic_phase_triple = harmonic_phase_double + phase;
    wire [15:0] harmonic_two_bits = harmonic_phase_double[31]
        ? {~harmonic_phase_double[30:16], 1'b0}
        : {harmonic_phase_double[30:16], 1'b0};
    wire [15:0] harmonic_three_bits = harmonic_phase_triple[31]
        ? {~harmonic_phase_triple[30:16], 1'b0}
        : {harmonic_phase_triple[30:16], 1'b0};
    wire signed [15:0] fundamental_triangle = triangle_unsigned ^ 16'h8000;
    wire signed [15:0] harmonic_two = harmonic_two_bits ^ 16'h8000;
    wire signed [15:0] harmonic_three = harmonic_three_bits ^ 16'h8000;
    function signed [15:0] soft_sine;
        input [31:0] p;
        reg [15:0] t;
        reg signed [16:0] x;
        reg [16:0] magnitude;
        reg signed [17:0] curvature;
        reg signed [34:0] product;
        begin
            t=p[31] ? {~p[30:16],1'b0} : {p[30:16],1'b0};
            x=$signed({t[15]^1'b1,t^16'h8000});
            magnitude=x<0 ? -x : x;
            curvature=18'sd65536-$signed({1'b0,magnitude});
            product=x*curvature;
            soft_sine=product>>>15;
        end
    endfunction
    wire signed [15:0] texture_wave;
    generate if(INSTRUMENT_PRESETS && EXPRESSION_TEXTURE)begin: expressive_instrument
        expressive_texture #(.VOICES(1)) colour(.clk(clk),.rst_n(rst_n),.step_en(sample_tick),
            .prepare_en(1'b1),
            .active(gate || state!=OFF),.slot(5'd0),.phase(phase),.note_index(pitch_index),
            .note_age(note_age),.expression(expression),.timbre(timbre_latched),
            .wave_out(texture_wave),.pitch_drift(texture_drift));
    end else if(INSTRUMENT_PRESETS)begin: organic_instrument
        instrument_texture colour(.clk(clk),.rst_n(rst_n),.step_en(sample_tick),
            .active(gate || state!=OFF),.slot(5'd0),.phase(phase),
            .note_age(note_age),.velocity(velocity),.timbre(timbre_latched),
            .wave_out(texture_wave),.pitch_drift(texture_drift));
    end else begin: no_instrument_texture
        assign texture_wave=0;assign texture_drift=0;
    end endgenerate
    wire signed [15:0] wave=INSTRUMENT_PRESETS ? texture_wave :
        (selected_timbre ? fundamental_triangle : $signed(phase[31:16]));
    wire signed [16:0] envelope_signed = $signed({1'b0, envelope});
    wire signed [8:0] velocity_signed = $signed({1'b0, velocity});
    wire signed [32:0] envelope_product = wave * envelope_signed;
    wire signed [41:0] scaled_product = envelope_product * velocity_signed;
    // Zero preserves the original fast release for existing demos. The
    // pressure instrument selects a longer level-dependent release.
    wire [15:0] release_step = release_shift_selected == 0 ? 16'd256 :
        ((envelope >> release_shift_selected) != 0 ?
         (envelope >> release_shift_selected) : 16'd1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase      <= 32'd0;
            envelope   <= 16'd0;
            state      <= OFF;
            gate_last  <= 1'b0;
            timbre_latched <= 1'b1;
            attack_from <= 0;
            note_age <= 0; expression_phase <= 0; bow_noise <= 16'hace1;
            sample_out <= 16'sd0;
        end else if (sample_tick) begin
            gate_last <= gate;
            bow_noise <= {bow_noise[14:0],bow_noise[15]^bow_noise[13]^bow_noise[12]^bow_noise[10]};
            if (gate && !gate_last) begin
                note_age <= 0;
                attack_from <= envelope;
                expression_phase <= 0;
            end else begin
                if(gate && note_age<16'd32768)note_age<=note_age+1'b1;
                expression_phase<=expression_phase+(timbre_latched ? 24'd1643 : 24'd1922);
            end
            if (gate && !gate_last)
                timbre_latched <= timbre;

            if (gate && !gate_last && state == OFF)
                phase <= 32'd0;
            else if (gate || state != OFF)
                phase <= phase + expressive_step;

            if (gate && !gate_last)
                state <= ATTACK;
            else if (!gate && state != OFF) begin
                if (envelope <= release_step) begin
                    envelope <= 16'd0;
                    state <= OFF;
                end else
                    envelope <= envelope - release_step;
            end else if (gate) begin
                if (INSTRUMENT_PRESETS) begin
                    case (state)
                        OFF, ATTACK: begin
                            envelope <= instrument_attack(note_age,attack_from,
                                attack_peak,timbre_latched);
                            state <= note_age >= instrument_attack_samples(timbre_latched)
                                ? DECAY : ATTACK;
                        end
                        DECAY: begin
                            if(envelope<=sustain_target+decay_step)begin
                                envelope<=sustain_target;state<=SUSTAIN;
                            end else envelope<=envelope-decay_step;
                        end
                        default: begin
                            envelope <= sustain_target;
                            state <= SUSTAIN;
                        end
                    endcase
                end else begin
                case (state)
                    OFF, ATTACK: begin
                        if (envelope >= attack_peak - attack_step) begin
                            envelope <= attack_peak;
                            state <= DECAY;
                        end else begin
                            envelope <= envelope + attack_step;
                            state <= ATTACK;
                        end
                    end
                    DECAY: begin
                        if (envelope <= sustain_target + decay_step) begin
                            envelope <= sustain_target;
                            state <= SUSTAIN;
                        end else
                            envelope <= envelope - decay_step;
                    end
                    SUSTAIN: envelope <= sustain_target;
                    default: begin
                        envelope <= 16'd0;
                        state <= OFF;
                    end
                endcase
                end
            end

            // 16-bit wave x 16-bit envelope x 8-bit velocity, then normalize.
            sample_out <= scaled_product[39:24];
        end
    end
endmodule
