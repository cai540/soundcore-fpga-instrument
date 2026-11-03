// ROM [22] marks a melisma continuing the same lyric word. Guidance asks for
// its first note only; autoplay still renders every event with its full time.
// pad=7 is a rest: it is skipped in guide mode but timed in playback mode.
module song_guide_long #(
    parameter integer MAX_STEPS = 1024,
    parameter integer LENGTH0 = 0,
    parameter integer LENGTH1 = 0,
    parameter ROM0_FILE = "",
    parameter ROM1_FILE = ""
) (
    input wire clk,
    input wire rst_n,
    input wire restart,
    input wire [1:0] ui_state,
    input wire song_select,
    input wire [3:0] key,
    output wire [6:0] target_note,
    input wire strike_valid,
    input wire [2:0] strike_bank,
    input wire [2:0] strike_pad,
    output reg [10:0] step_index,
    output wire [10:0] song_length,
    output wire [2:0] target_bank,
    output wire [2:0] target_pad,
    output wire [15:0] target_duration_ms,
    output reg completed,
    output reg correct_pulse,
    output reg wrong_pulse,
    output wire [6:0] target_led
);
    // $readmemh input uses six hex digits; bit 23 is reserved.
    reg [23:0] rom0 [0:MAX_STEPS-1];
    reg [23:0] rom1 [0:MAX_STEPS-1];
    initial begin
        if (LENGTH0 > 0) $readmemh(ROM0_FILE, rom0, 0, LENGTH0-1);
        if (LENGTH1 > 0) $readmemh(ROM1_FILE, rom1, 0, LENGTH1-1);
    end
    reg [1:0] previous_state;
    reg previous_song;
    wire [23:0] target_word = song_select ? rom1[step_index[9:0]] :
                                           rom0[step_index[9:0]];
    assign song_length = song_select ? LENGTH1 : LENGTH0;
    assign target_note=7'd24+{4'd0,target_word[5:3]}*7'd7+{4'd0,target_word[2:0]};
    wire [2:0] projected_bank,projected_pad;
    pitch_projection project(.note_index(target_note),.key(key),.bank(projected_bank),.pad(projected_pad),.sharp(),.valid());
    assign target_bank=completed || song_length==0 ? 3'd0 : projected_bank;
    assign target_pad=completed || song_length==0 || target_word[2:0]==7 || target_word[22] ? 3'd7 : projected_pad;
    assign target_duration_ms = completed || song_length == 0 ? 16'd0 : target_word[21:6];
    assign target_led = ui_state == 2'd2 && !completed && song_length != 0 &&
                        target_pad < 3'd7 && !target_word[22] ?
                        (7'b0000001 << target_pad) : 7'd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            previous_state <= 0;
            previous_song <= 0;
            step_index <= 0;
            completed <= 0;
            correct_pulse <= 0;
            wrong_pulse <= 0;
        end else begin
            previous_state <= ui_state;
            previous_song <= song_select;
            correct_pulse <= 0;
            wrong_pulse <= 0;
            if (restart) begin
                step_index <= 0;completed <= 0;previous_state <= 2'd3;
            end else if (ui_state == 2'd2 && previous_state != 2'd2 &&
                previous_state != 2'd3) begin
                step_index <= 0;
                completed <= 0;
            end else if (ui_state == 2'd1 && song_select != previous_song) begin
                step_index <= 0;
                completed <= 0;
            end else if (ui_state == 2'd2 && !completed && song_length != 0 &&
                         (target_word[2:0] == 3'd7 || target_word[22])) begin
                if (step_index == song_length - 1'b1) begin
                    completed <= 1;
                    step_index <= song_length;
                end else step_index <= step_index + 1'b1;
            end else if (ui_state == 2'd2 && !completed && song_length != 0 &&
                         strike_valid && strike_pad < 3'd7) begin
                if (strike_bank == target_bank && strike_pad == target_pad) begin
                    correct_pulse <= 1;
                    if (step_index == song_length - 1'b1) begin
                        completed <= 1;
                        step_index <= song_length;
                    end else step_index <= step_index + 1'b1;
                end else wrong_pulse <= 1;
            end
        end
    end
endmodule
