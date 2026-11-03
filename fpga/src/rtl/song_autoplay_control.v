// BLE starts the self-running FPGA song; it continues after BLE disconnects.
// 0=stop, 1=start/restart, 2=pause, 3=resume for command 0x23.
module song_autoplay_control (
    input wire clk,
    input wire rst_n,
    input wire command_valid,
    input wire [7:0] command_type,
    input wire [7:0] command_value,
    input wire [7:0] song_index,
    input wire player_finished,
    output reg active,
    output reg paused,
    output reg restart_pulse,
    output wire [1:0] playback_state
);
    reg [7:0] previous_song;
    assign playback_state = !active ? 2'd0 :
                            player_finished ? 2'd3 :
                            paused ? 2'd2 : 2'd1;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 0;
            paused <= 0;
            restart_pulse <= 0;
            previous_song <= 0;
        end else begin
            restart_pulse <= 0;
            previous_song <= song_index;
            if (song_index != previous_song) begin
                active <= 0;
                paused <= 0;
            end
            if (command_valid && command_type == 8'h23) begin
                case (command_value)
                    8'd0: begin active<=0;paused<=0;end
                    8'd1: begin active<=1;paused<=0;restart_pulse<=1;end
                    8'd2: if (active) paused<=1;
                    8'd3: if (active) paused<=0;
                    8'd4: begin active<=1;paused<=1;restart_pulse<=1;end // local rewind/pause
                    default: ;
                endcase
            end
        end
    end
endmodule
