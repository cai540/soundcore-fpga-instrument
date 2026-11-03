// Timed, device-side playback of the same ROM used by song_guide_long.
// A rest has pad=7. The player never depends on a BLE connection or phone.
// run rising or restart begins at event zero; pause freezes the position.
module song_event_player #(
    parameter integer CLK_HZ = 12288000,
    parameter integer MAX_STEPS = 1024,
    parameter integer LENGTH0 = 0,
    parameter integer LENGTH1 = 0,
    parameter integer TEMPO0_NUM = 1,
    parameter integer TEMPO1_NUM = 1,
    parameter integer TEMPO_DEN = 1,
    parameter integer ARTICULATION_GAP_MS = 10,
    parameter integer ARTICULATION0_GAP_MS = ARTICULATION_GAP_MS,
    parameter integer ARTICULATION1_GAP_MS = ARTICULATION_GAP_MS,
    parameter ROM0_FILE = "",
    parameter ROM1_FILE = ""
) (
    input wire clk,
    input wire rst_n,
    input wire run,
    input wire pause,
    input wire restart,
    input wire song_select,
    input wire [3:0] key,
    output reg [10:0] event_index,
    output wire [10:0] song_length,
    output wire [2:0] event_bank,
    output wire [2:0] event_pad,
    output wire [6:0] note_index,
    output wire note_gate,
    output reg finished,
    output reg [17:0] playback_ms
);
    localparam integer CYCLES_PER_MS = CLK_HZ / 1000;
    localparam integer MS_BITS = CYCLES_PER_MS < 2 ? 1 : $clog2(CYCLES_PER_MS);
    // $readmemh input uses six hex digits; upper two bits are zero.
    reg [23:0] rom0 [0:MAX_STEPS-1];
    reg [23:0] rom1 [0:MAX_STEPS-1];
    initial begin
        if (LENGTH0 > 0) $readmemh(ROM0_FILE, rom0, 0, LENGTH0-1);
        if (LENGTH1 > 0) $readmemh(ROM1_FILE, rom1, 0, LENGTH1-1);
    end
    reg [MS_BITS-1:0] cycle_count;
    reg [15:0] elapsed_ms;
    reg run_last;
    reg song_last;
    wire [23:0] word_now = song_select ? rom1[event_index[9:0]] :
                                          rom0[event_index[9:0]];
    wire [31:0] stretched_duration =
        (word_now[21:6] * (song_select ? TEMPO1_NUM : TEMPO0_NUM)) /
        TEMPO_DEN;
    wire [15:0] duration_ms = stretched_duration>65535 ? 16'hffff :
                              stretched_duration[15:0];
    assign song_length = song_select ? LENGTH1 : LENGTH0;
    wire [6:0] exact_note=7'd24+{4'd0,word_now[5:3]}*7'd7+{4'd0,word_now[2:0]};
    wire [2:0] projected_pad;
    pitch_projection project(.note_index(exact_note),.key(key),.bank(event_bank),.pad(projected_pad),.sharp(),.valid());
    assign event_pad=word_now[2:0]==7 ? 3'd7 : projected_pad;
    assign note_index=exact_note;
    // Per-song release/re-attack: song 0 separates repeated sung syllables;
    // song 1 keeps its previously reviewed legato articulation.
    wire [31:0] articulation_gap = song_select ?
        ARTICULATION1_GAP_MS : ARTICULATION0_GAP_MS;
    assign note_gate = run && !pause && !finished &&
        event_index < song_length && event_pad < 3'd7 &&
        {1'b0,elapsed_ms} + articulation_gap < {1'b0,duration_ms};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            event_index <= 0;
            cycle_count <= 0;
            elapsed_ms <= 0;
            run_last <= 0;
            song_last <= 0;
            finished <= 0;
            playback_ms <= 0;
        end else begin
            run_last <= run;
            song_last <= song_select;
            if (!run || restart || (run && !run_last) || song_select != song_last) begin
                event_index <= 0;
                cycle_count <= 0;
                elapsed_ms <= 0;
                finished <= 0;
                playback_ms <= 0;
            end else if (!pause && !finished && song_length != 0) begin
                if (cycle_count == CYCLES_PER_MS - 1) begin
                    playback_ms <= playback_ms+1'b1;
                    cycle_count <= 0;
                    if (elapsed_ms + 16'd1 >= duration_ms) begin
                        elapsed_ms <= 0;
                        if (event_index + 11'd1 >= song_length) begin
                            event_index <= song_length;
                            finished <= 1;
                        end else event_index <= event_index + 11'd1;
                    end else elapsed_ms <= elapsed_ms + 16'd1;
                end else cycle_count <= cycle_count + 1'b1;
            end
        end
    end
endmodule
