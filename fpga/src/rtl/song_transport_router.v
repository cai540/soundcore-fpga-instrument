// One arbitration point for the native panel, BLE and runtime-score takeover.
module song_transport_router(
    input wire local_valid,
    input wire [7:0] local_value,
    input wire remote_valid,
    input wire [7:0] remote_type,remote_value,
    input wire score_start,
    output reg command_valid,
    output reg [7:0] command_value
);
    always @*begin
        command_valid=local_valid;command_value=local_value;
        if(remote_valid && remote_type==8'h23)begin command_valid=1;command_value=remote_value;end
        else if(remote_valid && (remote_type==8'h14 || remote_type==8'h15))begin command_valid=1;command_value=0;end
        if(score_start)begin command_valid=1;command_value=0;end
    end
endmodule
