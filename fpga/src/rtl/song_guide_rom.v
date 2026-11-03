// Two built-in seven-pad practice phrases. A correct new strike advances one
// step; wrong strikes and held pads never advance. No phone/storage required.
// ui_state: 0=normal play, 1=song list, 2=guide running, 3=guide paused.
module song_guide_rom (
    input wire clk,
    input wire rst_n,
    input wire [1:0] ui_state,
    input wire [7:0] song_index,
    input wire strike_valid,
    input wire [2:0] strike_channel,
    output reg [3:0] step_index,
    output reg [2:0] target_pad,
    output reg [3:0] song_length,
    output reg completed,
    output reg correct_pulse,
    output reg wrong_pulse,
    output wire [6:0] target_led
);
    reg [1:0] previous_state;
    reg [7:0] previous_song;
    reg [2:0] target_lookup;

    always @* begin
        // Song 0: ascending scale. Song 1: alternating pad exercise.
        song_length = song_index[0] ? 4'd8 : 4'd7;
        if (song_index[0]) begin
            case (step_index)
                4'd0: target_lookup = 3'd0;
                4'd1: target_lookup = 3'd2;
                4'd2: target_lookup = 3'd4;
                4'd3: target_lookup = 3'd6;
                4'd4: target_lookup = 3'd5;
                4'd5: target_lookup = 3'd3;
                4'd6: target_lookup = 3'd1;
                default: target_lookup = 3'd0;
            endcase
        end else begin
            case (step_index)
                4'd0: target_lookup = 3'd0;
                4'd1: target_lookup = 3'd1;
                4'd2: target_lookup = 3'd2;
                4'd3: target_lookup = 3'd3;
                4'd4: target_lookup = 3'd4;
                4'd5: target_lookup = 3'd5;
                default: target_lookup = 3'd6;
            endcase
        end
        target_pad = target_lookup;
    end

    assign target_led = ui_state == 2'd2 && !completed ?
                        (7'b0000001 << target_pad) : 7'd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            previous_state <= 2'd0;
            previous_song <= 8'd0;
            step_index <= 4'd0;
            completed <= 1'b0;
            correct_pulse <= 1'b0;
            wrong_pulse <= 1'b0;
        end else begin
            previous_state <= ui_state;
            previous_song <= song_index;
            correct_pulse <= 1'b0;
            wrong_pulse <= 1'b0;
            // Entering from pause retains progress. Starting after list or
            // normal play starts from the first note of the chosen song.
            if (ui_state == 2'd2 && previous_state != 2'd2 &&
                previous_state != 2'd3) begin
                step_index <= 4'd0;
                completed <= 1'b0;
            end else if (ui_state == 2'd1 && song_index != previous_song) begin
                step_index <= 4'd0;
                completed <= 1'b0;
            end else if (ui_state == 2'd2 && !completed && strike_valid &&
                         strike_channel < 3'd7) begin
                if (strike_channel == target_lookup) begin
                    correct_pulse <= 1'b1;
                    if (step_index == song_length - 1'b1) begin
                        completed <= 1'b1;
                        step_index <= song_length;
                    end else
                        step_index <= step_index + 1'b1;
                end else
                    wrong_pulse <= 1'b1;
            end
        end
    end
endmodule
