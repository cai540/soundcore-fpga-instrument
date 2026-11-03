// Isolates BLE-held notes from the physical pressure-pad detector.
// A pending phone strike waits for a free voice and for a cycle without a
// physical strike, so physical playing retains priority under contention.
module remote_note_bridge #(
    parameter LEASE_CYCLES = 18432000, // 1.5 s at 12.288 MHz
    parameter REALTIME_ENABLED = 0,
    parameter PENDING_LIMIT_CYCLES = 491520 // 40 ms, never queue old strikes
) (
    input wire clk,
    input wire rst_n,
    input wire write_allowed,
    input wire command_valid,
    input wire [7:0] command_type,
    input wire [7:0] command_value,
    input wire [7:0] command_value2,
    input wire [111:0] command_payload,
    input wire physical_strike,
    input wire voice_ready,
    output reg [6:0] remote_pressed,
    output wire remote_strike_valid,
    output wire [2:0] remote_strike_channel,
    output wire [7:0] remote_strike_velocity,
    output reg remote_absolute,
    output wire [6:0] remote_strike_note,
    output wire [48:0] remote_notes
);
    reg pending;
    reg [2:0] legacy_channel;
    reg [7:0] legacy_velocity,realtime_velocity;
    reg [6:0] pending_mask;
    reg [19:0] pending_age;
    wire pending_expired=(|pending_mask) && pending_age>=PENDING_LIMIT_CYCLES-1;
    reg [2:0] selected;
    integer j;
    reg [6:0] absolute_note[0:6];
    reg [6:0] pitch_changed;
    genvar n;
    generate for(n=0;n<7;n=n+1)begin: held_notes
        assign remote_notes[n*7 +: 7]=absolute_note[n];
    end endgenerate
    always @* begin
        pitch_changed=0;
        for(j=0;j<7;j=j+1)
            pitch_changed[j]=!remote_absolute || absolute_note[j]!=command_payload[24+j*8 +: 7];
    end
    integer k;
    integer q;
    always @* begin
        selected=0;
        for(k=6;k>=0;k=k-1)if(pending_mask[k])selected=k;
    end
    assign remote_strike_channel=(|pending_mask) ? selected : legacy_channel;
    assign remote_strike_velocity=(|pending_mask) ? realtime_velocity : legacy_velocity;
    assign remote_strike_note=absolute_note[remote_strike_channel];
    reg [24:0] lease_count;
    assign remote_strike_valid = (pending || ((|pending_mask) && !pending_expired)) && !physical_strike &&
                                 voice_ready && write_allowed && !command_valid;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            remote_pressed <= 0;
            pending <= 0;
            legacy_channel <= 0;legacy_velocity<=0;realtime_velocity<=176;
            pending_mask<=0;pending_age<=0;
            lease_count <= 0;
            remote_absolute<=0;
            for(q=0;q<7;q=q+1)absolute_note[q]<=0;
        end else if (!write_allowed) begin
            remote_pressed <= 0;
            pending <= 0;
            pending_mask<=0;pending_age<=0;
            lease_count <= 0;
        end else begin
            if (pending_mask!=0) begin
                if(pending_expired)begin pending_mask<=0;pending_age<=0;end
                else pending_age<=pending_age+1'b1;
            end else pending_age<=0;
            if (remote_pressed != 0 || pending || pending_mask!=0) begin
                if (lease_count >= LEASE_CYCLES-1) begin
                    remote_pressed <= 0;
                    pending <= 0;
                    pending_mask<=0;
                    lease_count <= 0;
                end else lease_count <= lease_count + 1'b1;
            end else lease_count <= 0;
            if (remote_strike_valid) begin
                if(pending_mask!=0)pending_mask[selected]<=0;
                else pending <= 0;
            end
            if (command_valid) begin
                case (command_type)
                    8'h16: if (command_value <= 6 && command_value2 != 0) begin
                        remote_absolute<=0;
                        remote_pressed[command_value[2:0]] <= 1;
                        pending <= 1;
                        legacy_channel <= command_value[2:0];
                        legacy_velocity <= command_value2;
                        lease_count <= 0;
                    end
                    8'h17: if (command_value <= 6) begin
                        remote_pressed[command_value[2:0]] <= 0;
                        pending_mask[command_value[2:0]]<=0;
                        if (pending && remote_strike_channel == command_value[2:0])
                            pending <= 0;
                    end
                    8'h18: begin
                        remote_pressed <= 0;
                        pending <= 0;
                        pending_mask<=0;
                        lease_count <= 0;
                    end
                    8'h21: begin // lease refresh; mask is authoritative, no new attack
                        remote_pressed <= command_value[6:0];
                        pending_mask<=pending_mask & command_value[6:0];
                        if (pending && !command_value[remote_strike_channel])
                            pending <= 0;
                        lease_count <= 0;
                    end
                    8'h24: if(REALTIME_ENABLED != 0)begin
                        remote_absolute<=0;
                        remote_pressed<=command_value[6:0];
                        pending<=0;
                        // Release is authoritative. Keep only current held
                        // attacks; a late mailbox cannot replay old taps.
                        pending_mask<=(((pending_expired || remote_absolute ? 7'd0:pending_mask) &
                            ~(remote_strike_valid ? (7'b1<<selected) : 7'd0)) |
                            command_value2[6:0] | (command_value[6:0] & ~remote_pressed)) & command_value[6:0];
                        realtime_velocity<=command_payload[23:16];
                        // A stream of held-state refreshes cannot keep an old
                        // voice request alive indefinitely under contention.
                        if(pending_expired || pending_mask==0)pending_age<=0;
                        lease_count<=0;
                    end
                    8'h25: if(REALTIME_ENABLED != 0)begin
                        remote_absolute<=1;remote_pressed<=command_value[6:0];pending<=0;
                        pending_mask<=((pending_expired ? 7'd0:pending_mask) |
                            command_value2[6:0] | pitch_changed |
                            (command_value[6:0] & ~remote_pressed)) & command_value[6:0];
                        for(q=0;q<7;q=q+1)absolute_note[q]<=command_payload[24+q*8 +: 7];
                        realtime_velocity<=command_payload[23:16];
                        if(pending_expired || pending_mask==0)pending_age<=0;
                        lease_count<=0;
                    end
                    default: ;
                endcase
            end
        end
    end
endmodule
