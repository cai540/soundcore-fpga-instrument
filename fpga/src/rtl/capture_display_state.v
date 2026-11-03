// Leased phone UI only; autonomous device playback always owns its own display.
module capture_display_state #(
 parameter integer LEASE_CYCLES=49152000
)(
 input wire clk,rst_n,link_active,summary_valid,
 input wire [87:0] summary_payload,
 input wire score_receiving,score_playing,score_guiding,score_paused,score_finished,
 input wire [9:0] score_step,score_count,score_received,score_expected,
 input wire [2:0] score_bank,score_pad,
 output wire [87:0] display_payload
);
 localparam integer W=$clog2(LEASE_CYCLES+1);
 reg [W-1:0] lease_left;
 reg [87:0] phone;
 reg finish_dismissed;
 wire engaged=score_playing || score_guiding;
 wire runtime_active=score_receiving || (engaged && (!score_finished || !finish_dismissed));
 wire [7:0] stage=score_receiving ? 8'd9 : runtime_active ?
   (score_finished ? 8'd13 : score_paused ? 8'd12 : score_guiding ? 8'd11 : 8'd10) :
   lease_left!=0 && link_active ? phone[15:8] : 8'd0;
 wire [15:0] position=score_receiving ? {6'd0,score_received} : {6'd0,score_step};
 wire [15:0] count=score_receiving ? {6'd0,score_expected} : {6'd0,score_count};
 wire [7:0] midi=score_pad<7 ? 8'd60+score_bank*8'd7+score_pad : 8'hff;
 assign display_payload=runtime_active ?
   {8'd0,midi,count,count,position,8'd0,stage,8'd1} : {phone[87:16],stage,8'd1};
 always @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin phone<=0;lease_left<=0;finish_dismissed<=0;end
   else begin
    if(!engaged || !score_finished)finish_dismissed<=0;
    else if(link_active && summary_valid && summary_payload[15:8]!=0 && summary_payload!=phone)finish_dismissed<=1;
    if(!link_active)lease_left<=0;
    else if(summary_valid)begin phone<=summary_payload;lease_left<=summary_payload[15:8]==0 ? 0 : LEASE_CYCLES;end
    else if(lease_left!=0)lease_left<=lease_left-1'b1;
   end
 end
endmodule
