// Thirty-two independent note states serviced by one shared arithmetic path.
// At 12.288 MHz / 48 kHz there are 256 clocks per audio frame. This core
// processes each voice in four clocks (128 clocks total) and presents the next
// sample before the following I2S frame. No prerecorded waveform is read.
module poly_synth32_tm #(
    parameter integer MIX_SHIFT = 0,
    parameter integer RELEASE_SHIFT = 9,
    parameter integer EXPRESSION_TEXTURE = 0,
    parameter integer NORMALIZE_LEVEL = 1,
    parameter integer DIAGNOSTIC_AVAILABLE = 0
) (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               sample_tick,
    input  wire [31:0]        gate,
    input  wire [1023:0]      phase_step,
    input  wire [255:0]       velocity,
    input  wire [255:0]       expression,
    input  wire [223:0]       pitch_index,
    input  wire               timbre, // 1=harmonica-style, 0=erhu-style
    input wire diagnostic_sine,
    output reg[5:0] active_count,
    output reg  signed [15:0] sample_out,
    output reg                sample_valid
);
    localparam [1:0] OFF = 2'd0, ATTACK = 2'd1,
                     DECAY = 2'd2, SUSTAIN = 2'd3;
    reg [31:0] phase [0:31];
    reg [15:0] envelope [0:31];
    reg [1:0] state [0:31];
    reg gate_last [0:31];
    reg timbre_latched [0:31];
    reg [15:0] note_age [0:31];
    reg [15:0] attack_from [0:31];
    reg [23:0] expression_phase [0:31];
    reg [15:0] bow_noise;
    reg busy;
    reg [2:0] service_stage;
    reg gate_q,timbre_request_q,colour_active_q,colour_timbre_q;
    reg [31:0] step_q,colour_phase_q;
    reg [7:0] velocity_q,colour_velocity_q;
    reg [7:0] expression_q,colour_expression_q;
    reg [6:0] pitch_q,colour_pitch_q;
    reg [15:0] colour_age_q,colour_envelope_q;
    reg signed [17:0] modulation_q;
    reg [4:0] slot;
    reg signed [31:0] accumulator;
    reg signed [15:0] wave_reg;
    reg [15:0] amp_reg;
    reg [5:0] completed_voice_count;
    reg sine_latched[0:31];reg[5:0] audible_accumulator;
    reg [31:0] phase_next;
    wire signed[15:0] diagnostic_wave;
    generate if(DIAGNOSTIC_AVAILABLE)begin: diagnostic_lookup
        reg signed[15:0] sine_rom[0:1023];reg signed[15:0] wave_q;
        initial $readmemh("D:/FPGA/Projects/soundcore_2026/rtl/tools_sine.mem",sine_rom);
        always @(posedge clk)wave_q<=sine_rom[phase_next[31:22]];
        assign diagnostic_wave=wave_q;
    end else begin:no_diagnostic_lookup assign diagnostic_wave=0;end endgenerate
    integer i;

    function signed [15:0] triangle;
        input [31:0] p;
        reg [15:0] unsigned_triangle;
        begin
            unsigned_triangle = p[31] ? {~p[30:16], 1'b0} :
                                          {p[30:16], 1'b0};
            triangle = unsigned_triangle ^ 16'h8000;
        end
    endfunction

    function signed [15:0] soft_sine;
        input [31:0] p;
        reg signed [16:0] x;
        reg [16:0] magnitude;
        reg signed [17:0] curvature;
        reg signed [34:0] product;
        begin
            x=$signed(triangle(p));
            magnitude=x<0 ? -x : x;
            curvature=18'sd65536-$signed({1'b0,magnitude});
            product=x*curvature;
            soft_sine=product>>>15;
        end
    endfunction

    wire slot_gate = gate_q;
    wire [31:0] slot_step = step_q;
    wire [7:0] slot_velocity = velocity_q;
    wire signed [7:0] texture_drift;
    wire signed [15:0] expression_sine=soft_sine({expression_phase[slot],8'd0});
    wire signed [8:0] expression_round=(expression_sine>>>8)+texture_drift;
    wire [7:0] expression_strength = note_age[slot]<16'd4608 ? 0 :
        note_age[slot]>=16'd20928 ? 8'd255 : (note_age[slot]-16'd4608)>>6;
    wire signed [17:0] expression_depth=expression_round*$signed({1'b0,expression_strength});
    wire signed [50:0] expression_product = $signed({1'b0,slot_step})*modulation_q;
    wire signed [50:0] expression_delta = expression_product>>>(timbre_latched[slot] ? 23 : 21);
    wire [31:0] expressive_step = slot_step+expression_delta[31:0];
    wire [15:0] attack_target = timbre_latched[slot] ? 16'd30000 : 16'd28000;
    // A gentle real decay, not an accent boost: preserve the accepted attack,
    // then settle by 5% over about31ms/29ms. Each voice owns its ADSR state.
    wire [15:0] sustain_target = timbre_latched[slot] ? 16'd28500 : 16'd26600;
    // Same zero-slope, no-overshoot instrument onset as the offline voice.
    // The arithmetic is shared by all 32 slots, not replicated 32 times.
    `include "@FPGA_ROOT@/src/rtl/instrument_attack.vh"
    wire [15:0] release_step =
        (envelope[slot] >> RELEASE_SHIFT) != 0 ?
        (envelope[slot] >> RELEASE_SHIFT) : 16'd1;
    reg [15:0] envelope_next;
    reg [1:0] state_next;
    reg signed [15:0] wave_next;
    reg signed [17:0] harmonica_wave;
    reg signed [17:0] erhu_wave;
    reg signed [17:0] bowed_harmonics;
    wire signed [15:0] texture_wave,legacy_texture_wave,new_texture_wave;
    wire signed [7:0] legacy_texture_drift,new_texture_drift;
    assign texture_wave=EXPRESSION_TEXTURE ? new_texture_wave : legacy_texture_wave;
    assign texture_drift=EXPRESSION_TEXTURE ? new_texture_drift : legacy_texture_drift;
    instrument_texture #(.VOICES(32)) colour(.clk(clk),.rst_n(rst_n),
         .step_en(busy && service_stage==2 && !sample_tick),
        .active(colour_active_q),.slot(slot),.phase(colour_phase_q),
        .note_age(colour_age_q),.velocity(colour_velocity_q),.timbre(colour_timbre_q),
        .wave_out(legacy_texture_wave),.pitch_drift(legacy_texture_drift));
    generate if(EXPRESSION_TEXTURE)begin: expressive_colour
        expressive_texture #(.VOICES(32),.NORMALIZE_LEVEL(NORMALIZE_LEVEL)) colour(
            .clk(clk),.rst_n(rst_n),.step_en(busy && service_stage==2 && !sample_tick),
            .prepare_en(busy && service_stage==1 && !sample_tick),
            .active(colour_active_q),.slot(slot),.phase(colour_phase_q),.note_index(pitch_q),
            .note_age(colour_age_q),.expression(expression_q),
            .timbre(service_stage==1 ? timbre_latched[slot] : colour_timbre_q),
            .wave_out(new_texture_wave),.pitch_drift(new_texture_drift));
    end else begin: no_expressive_colour
        assign new_texture_wave=0;assign new_texture_drift=0;
    end endgenerate
    wire signed [31:0] voice_product =
        $signed(wave_reg) * $signed({1'b0, amp_reg});
    wire signed [31:0] scaled_voice = voice_product >>> 16;
    wire signed [31:0] sum_next = accumulator + scaled_voice;
    wire signed [31:0] output_wide = sum_next >>> MIX_SHIFT;

    always @* begin
        phase_next = phase[slot];
        if (slot_gate && !gate_last[slot] && state[slot] == OFF)
            phase_next = 32'd0;
        else if (slot_gate || state[slot] != OFF)
            phase_next = phase[slot] + (DIAGNOSTIC_AVAILABLE && sine_latched[slot] ? phase_step[slot*32 +: 32]:expressive_step);

        envelope_next = envelope[slot];
        state_next = state[slot];
        if (slot_gate && !gate_last[slot]) begin
            state_next = ATTACK;
        end else if (!slot_gate && state[slot] != OFF) begin
            if (envelope[slot] <= release_step) begin
                envelope_next = 16'd0;
                state_next = OFF;
            end else
                envelope_next = envelope[slot] - release_step;
        end else if (slot_gate) begin
            case (state[slot])
                OFF, ATTACK: begin
                    envelope_next = instrument_attack(note_age[slot],attack_from[slot],
                        attack_target,timbre_latched[slot]);
                    state_next = note_age[slot] >= instrument_attack_samples(timbre_latched[slot])
                        ? DECAY : ATTACK;
                end
                DECAY: begin
                    if(envelope[slot]<=sustain_target+16'd1)begin
                        envelope_next=sustain_target;state_next=SUSTAIN;
                    end else envelope_next=envelope[slot]-16'd1;
                end
                SUSTAIN: envelope_next = sustain_target;
                default: begin
                    envelope_next = 16'd0;
                    state_next = OFF;
                end
            endcase
        end

        wave_next = DIAGNOSTIC_AVAILABLE && sine_latched[slot] ? diagnostic_wave:texture_wave;

    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            service_stage <= 0;
            slot <= 5'd0;
            accumulator <= 32'sd0;
            wave_reg <= 16'sd0;
            amp_reg <= 16'd0;
            completed_voice_count <= 6'd0;
            active_count<=0;audible_accumulator<=0;
            sample_out <= 16'sd0;
            sample_valid <= 1'b0;
            bow_noise <= 16'hace1;
            gate_q<=0;timbre_request_q<=1;step_q<=0;velocity_q<=0;modulation_q<=0;
            colour_active_q<=0;colour_timbre_q<=1;colour_phase_q<=0;
            colour_age_q<=0;colour_velocity_q<=0;colour_envelope_q<=0;
            expression_q<=0;colour_expression_q<=0;pitch_q<=0;colour_pitch_q<=0;
            for (i = 0; i < 32; i = i + 1) begin
                phase[i] <= 32'd0;
                envelope[i] <= 16'd0;
                state[i] <= OFF;
                gate_last[i] <= 1'b0;
                sine_latched[i]<=0;
                timbre_latched[i] <= 1'b1;
                attack_from[i] <= 0;
                note_age[i] <= 0;
                expression_phase[i] <= 0;
            end
        end else begin
            sample_valid <= 1'b0;
            if (sample_tick) begin
                busy <= 1'b1;
                service_stage <= 0;
                slot <= 5'd0;
                accumulator <= 32'sd0;
                completed_voice_count <= 6'd0;
                audible_accumulator<=0;
                bow_noise <= {bow_noise[14:0],bow_noise[15]^bow_noise[13]^bow_noise[12]^bow_noise[10]};
            end else if (busy && service_stage==0) begin
                // Snapshot a slot and finish its LFO before the wide pitch
                // multiplication. No arithmetic chain crosses both stages.
                gate_q<=gate[slot];timbre_request_q<=timbre;
                step_q<=phase_step[slot*32 +: 32];velocity_q<=velocity[slot*8 +: 8];
                expression_q<=expression[slot*8 +: 8];pitch_q<=pitch_index[slot*7 +: 7];
                modulation_q<=expression_depth;
                service_stage<=1;
            end else if (busy && service_stage==1) begin
                phase[slot] <= phase_next;
                envelope[slot] <= envelope_next;
                state[slot] <= state_next;
                gate_last[slot] <= slot_gate;
                if (slot_gate && !gate_last[slot]) begin
                    sine_latched[slot]<=DIAGNOSTIC_AVAILABLE!=0 && diagnostic_sine;
                    note_age[slot] <= 0;
                    attack_from[slot] <= envelope[slot];
                    expression_phase[slot] <= 0;
                end else begin
                    if(slot_gate && note_age[slot]<16'd32768)note_age[slot]<=note_age[slot]+1'b1;
                    expression_phase[slot]<=expression_phase[slot]+(timbre_latched[slot] ? 24'd1643:24'd1922);
                end
                if (slot_gate && !gate_last[slot])
                    timbre_latched[slot] <= timbre_request_q;
                colour_active_q<=slot_gate || state[slot]!=OFF;
                colour_phase_q<=phase_next;colour_age_q<=note_age[slot];
                colour_timbre_q<=timbre_latched[slot];colour_velocity_q<=slot_velocity;
                colour_envelope_q<=envelope_next;
                colour_expression_q<=expression_q;colour_pitch_q<=pitch_q;
                service_stage<=2;
            end else if (busy && service_stage==2) begin
                // Harmonics, body and breath operate on registered pitch.
                if(!EXPRESSION_TEXTURE)wave_reg<=wave_next;
                amp_reg<=colour_envelope_q[15:8]*colour_velocity_q;
                service_stage<=3;
            end else if (busy && service_stage==3 && EXPRESSION_TEXTURE) begin
                wave_reg<=wave_next;service_stage<=4;
            end else if (busy && (service_stage==3 || service_stage==4)) begin
                accumulator <= sum_next;
                audible_accumulator<=audible_accumulator+(envelope[slot]!=0 && velocity_q!=0);
                completed_voice_count <= {1'b0, slot} + 6'd1;
                if (slot == 5'd31) begin
                    busy <= 1'b0;
                    sample_valid <= 1'b1;
                    active_count<=audible_accumulator+(envelope[slot]!=0 && velocity_q!=0);
                    if (output_wide > 32'sd32767)
                        sample_out <= 16'sh7fff;
                    else if (output_wide < -32'sd32768)
                        sample_out <= 16'sh8000;
                    else
                        sample_out <= output_wide[15:0];
                end else begin
                    slot <= slot + 5'd1;
                    service_stage <= 0;
                end
            end
        end
    end
endmodule
