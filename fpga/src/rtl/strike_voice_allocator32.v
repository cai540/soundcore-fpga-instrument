// Seven pressure pads allocate into a pool of 32 independent audio voices.
// Retriggering one pad releases its previous voice into the audio tail and
// allocates a fresh slot; it never cuts an unrelated held pad when free slots
// exist. Retired slots cool down long enough for the synth release envelope.
module strike_voice_allocator32 #(
    parameter integer HOLD_SAMPLES = 480,
    parameter integer RELEASE_SAMPLES = 16384,
    parameter integer BANKED_MODE = 0,
    parameter integer REMOTE_ENABLE = 0,
    parameter integer CUSTOM_MAP_AVAILABLE = 0
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         sample_tick,
    input  wire         strike_valid,
    input  wire [2:0]   strike_channel,
    input  wire [7:0]   strike_velocity,
    input  wire         level_valid,
    input  wire [2:0]   level_channel,
    input  wire [7:0]   level_velocity,
    input  wire [6:0]   pressed,
    input  wire         remote_strike_valid,
    input  wire [2:0]   remote_strike_channel,
    input  wire [7:0]   remote_strike_velocity,
    input  wire [6:0]   remote_pressed,
    // Used only by the banked-32 variant. Legacy instances keep BANKED_MODE=0.
    input  wire [2:0]   bank,
    input wire [3:0] key,
    input wire guide_override,
    input wire [2:0] guide_pad,
    input wire [6:0] guide_note,
    input wire remote_absolute,
    input wire [6:0] remote_note,
    input wire custom_map_enabled,
    input wire[48:0] custom_map,
    input  wire         banked_enable,
    input  wire         sustain,
    input  wire         clear_all,
    output wire [31:0]  gate,
    output wire [223:0] note_index,
    output wire [255:0] velocity,
    output wire [95:0]  voice_zone,
    output wire         remote_voice_ready,
    output wire [31:0]  remote_owner
);
    localparam integer HOLD_BITS = (HOLD_SAMPLES < 2) ? 1 :
                                   $clog2(HOLD_SAMPLES + 1);
    localparam integer RELEASE_BITS = (RELEASE_SAMPLES < 2) ? 1 :
                                      $clog2(RELEASE_SAMPLES + 1);
    reg [HOLD_BITS-1:0] hold [0:31];
    reg [RELEASE_BITS-1:0] cooldown [0:31];
    reg [6:0] active_note [0:31];
    reg [2:0] active_channel [0:31];
    reg [7:0] active_velocity [0:31];
    reg active_remote [0:31];
    reg [6:0] queued_note [0:31];
    reg [2:0] queued_channel [0:31];
    reg [7:0] queued_velocity [0:31];
    reg queued_remote [0:31];
    reg [31:0] pending;
    reg [31:0] voice_valid;
    reg [6:0] pad_owner_note [0:6];
    reg [6:0] remote_owner_note [0:6];
    reg [4:0] next_voice;
    reg [4:0] chosen_voice;
    reg free_found;
    reg [4:0] candidate;
    integer search_i;
    integer i;
    integer p;
    wire banked_now = (BANKED_MODE != 0) && banked_enable;
    wire [6:0] natural_note,remote_natural_note;
    wire natural_ok,remote_natural_ok;
    wire[6:0] physical_entry=custom_map[strike_channel*7 +: 7];
    wire[6:0] phone_entry=custom_map[remote_strike_channel*7 +: 7];
    wire[2:0] physical_degree=CUSTOM_MAP_AVAILABLE && custom_map_enabled && physical_entry>=120 ? physical_entry-7'd120:strike_channel;
    wire[2:0] phone_degree=CUSTOM_MAP_AVAILABLE && custom_map_enabled && phone_entry>=120 ? phone_entry-7'd120:remote_strike_channel;
    pitch_layout physical_map(.bank(bank),.pad(physical_degree),.key(key),.note_index(natural_note),.valid(natural_ok));
    pitch_layout phone_map(.bank(bank),.pad(phone_degree),.key(key),.note_index(remote_natural_note),.valid(remote_natural_ok));
    wire [6:0] physical_base=CUSTOM_MAP_AVAILABLE && custom_map_enabled && physical_entry<72 ? physical_entry:natural_note;
    wire [6:0] phone_base=CUSTOM_MAP_AVAILABLE && custom_map_enabled && phone_entry<72 ? phone_entry:remote_natural_note;
    wire [6:0] mapped_note=guide_override && strike_channel==guide_pad ? guide_note : physical_base;
    wire banked_strike_ok=natural_ok && mapped_note<72;
    wire [6:0] remote_mapped_note=remote_absolute ? remote_note :
        guide_override && remote_strike_channel==guide_pad ? guide_note : phone_base;
    wire remote_strike_ok=remote_absolute ? remote_note<72 : remote_natural_ok && remote_mapped_note<72;

    function [6:0] note_for_zone;
        input [2:0] zone;
        case (zone)
            3'd0: note_for_zone = 7'd24;
            3'd1: note_for_zone = 7'd26;
            3'd2: note_for_zone = 7'd28;
            3'd3: note_for_zone = 7'd31;
            3'd4: note_for_zone = 7'd33;
            3'd5: note_for_zone = 7'd36;
            3'd6: note_for_zone = 7'd38;
            default: note_for_zone = 7'd24;
        endcase
    endfunction

    always @* begin
        chosen_voice = next_voice;
        free_found = 1'b0;
        candidate = next_voice;
        for (search_i = 0; search_i < 32; search_i = search_i + 1) begin
            candidate = next_voice + search_i[4:0];
            if (!free_found && !voice_valid[candidate] &&
                !pending[candidate] && cooldown[candidate] == 0) begin
                chosen_voice = candidate;
                free_found = 1'b1;
            end
        end
    end
    assign remote_voice_ready = free_found;

    genvar g;
    wire [31:0] held_slot;
    generate for (g = 0; g < 32; g = g + 1) begin: outputs
        assign remote_owner[g]=active_remote[g];
        assign held_slot[g] = active_remote[g] ?
            ((REMOTE_ENABLE != 0) && remote_pressed[active_channel[g]] &&
             remote_owner_note[active_channel[g]] == active_note[g]) :
            (banked_now ?
             (sustain || (pressed[active_channel[g]] &&
              pad_owner_note[active_channel[g]] == active_note[g])) :
             pressed[active_channel[g]]);
        assign gate[g] = voice_valid[g] && !pending[g] &&
            ((hold[g] != 0) || held_slot[g]);
        assign note_index[g*7 +: 7] = active_note[g];
        assign velocity[g*8 +: 8] = active_velocity[g];
        assign voice_zone[g*3 +: 3] = active_channel[g];
    end endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pending <= 32'd0;
            voice_valid <= 32'd0;
            next_voice <= 5'd0;
            for (p = 0; p < 7; p = p + 1) begin
                pad_owner_note[p] <= 7'd0;
                remote_owner_note[p] <= 7'd0;
            end
            for (i = 0; i < 32; i = i + 1) begin
                hold[i] <= {HOLD_BITS{1'b0}};
                cooldown[i] <= {RELEASE_BITS{1'b0}};
                active_note[i] <= 7'd0;
                active_channel[i] <= 3'd0;
                active_velocity[i] <= 8'd0;
                active_remote[i] <= 1'b0;
                queued_note[i] <= 7'd0;
                queued_channel[i] <= 3'd0;
                queued_velocity[i] <= 8'd0;
                queued_remote[i] <= 1'b0;
            end
        end else begin
            if (BANKED_MODE != 0 && clear_all) begin
                pending <= 32'd0;
                voice_valid <= 32'd0;
                for (i = 0; i < 32; i = i + 1) begin
                    hold[i] <= {HOLD_BITS{1'b0}};
                    cooldown[i] <= {RELEASE_BITS{1'b0}};
                end
            end else begin
            if (sample_tick) begin
                for (i = 0; i < 32; i = i + 1) begin
                    if (cooldown[i] != 0)
                        cooldown[i] <= cooldown[i] - 1'b1;
                    if (pending[i]) begin
                        active_note[i] <= queued_note[i];
                        active_channel[i] <= queued_channel[i];
                        active_velocity[i] <= queued_velocity[i];
                        active_remote[i] <= queued_remote[i];
                        hold[i] <= HOLD_SAMPLES;
                        pending[i] <= 1'b0;
                        voice_valid[i] <= 1'b1;
                        cooldown[i] <= {RELEASE_BITS{1'b0}};
                    end else if (hold[i] != 0)
                        hold[i] <= hold[i] - 1'b1;
                    else if (voice_valid[i] && !held_slot[i]) begin
                        voice_valid[i] <= 1'b0;
                        cooldown[i] <= RELEASE_SAMPLES;
                    end
                end
            end
            if (strike_valid && strike_channel < 3'd7 &&
                (!banked_now || banked_strike_ok)) begin
                // Drop the old gate for this pad while its phase/envelope
                // continue to ring; all other held pads are untouched.
                for (i = 0; i < 32; i = i + 1) begin
                    if (i != chosen_voice && voice_valid[i] && !active_remote[i] &&
                        (banked_now ?
                         active_note[i] == mapped_note :
                         active_channel[i] == strike_channel)) begin
                        voice_valid[i] <= 1'b0;
                        cooldown[i] <= RELEASE_SAMPLES;
                    end
                end
                queued_note[chosen_voice] <= banked_now ?
                    mapped_note : note_for_zone(strike_channel);
                queued_channel[chosen_voice] <= strike_channel;
                queued_velocity[chosen_voice] <= strike_velocity;
                queued_remote[chosen_voice] <= 1'b0;
                hold[chosen_voice] <= {HOLD_BITS{1'b0}};
                pending[chosen_voice] <= 1'b1;
                if (banked_now)
                    pad_owner_note[strike_channel] <= mapped_note;
                next_voice <= chosen_voice + 5'd1;
            end
            // Phone notes have their own owner and held bits. A physical pad
            // can never retire a phone slot, or vice versa. The top buffers
            // remote NOTE_ON until a cycle without a physical strike.
            if (REMOTE_ENABLE != 0 && remote_strike_valid && !strike_valid &&
                free_found &&
                remote_strike_channel < 3'd7 &&
                (!banked_now || remote_strike_ok)) begin
                for (i = 0; i < 32; i = i + 1)
                    if (i != chosen_voice && voice_valid[i] && active_remote[i] &&
                        active_channel[i] == remote_strike_channel) begin
                        voice_valid[i] <= 1'b0;
                        cooldown[i] <= RELEASE_SAMPLES;
                    end
                queued_note[chosen_voice] <= banked_now ?
                    remote_mapped_note : note_for_zone(remote_strike_channel);
                queued_channel[chosen_voice] <= remote_strike_channel;
                queued_velocity[chosen_voice] <= remote_strike_velocity;
                queued_remote[chosen_voice] <= 1'b1;
                hold[chosen_voice] <= {HOLD_BITS{1'b0}};
                pending[chosen_voice] <= 1'b1;
                remote_owner_note[remote_strike_channel] <= banked_now ?
                    remote_mapped_note : note_for_zone(remote_strike_channel);
                next_voice <= chosen_voice + 5'd1;
            end
            if (level_valid && level_channel < 3'd7) begin
                for (i = 0; i < 32; i = i + 1)
                    if (voice_valid[i] && !pending[i] && !active_remote[i] &&
                        active_channel[i] == level_channel &&
                        (!banked_now ||
                         active_note[i] == pad_owner_note[level_channel]) &&
                        pressed[level_channel] &&
                        level_velocity > active_velocity[i])
                        active_velocity[i] <= level_velocity;
            end
            end
        end
    end
endmodule
