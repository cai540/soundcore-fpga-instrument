// Non-blocking rhythm hint: the next target is visible immediately after a
// correct strike. It stays dim during the previous lyric's written duration,
// flashes near its end, then becomes bright. Never delays/consumes a strike.
// Continuation notes and rests skipped by guidance contribute their duration.
module guide_rhythm_cue #(
 parameter integer CLOCKS_PER_MS=12288
)(input wire clk,rst_n,active,paused,correct,
 input wire[10:0] step_index,input wire[15:0] target_duration_ms,
 input wire[6:0] target_led,output wire[6:0] led);
 localparam CW=CLOCKS_PER_MS<2 ? 1:$clog2(CLOCKS_PER_MS);
 reg[CW-1:0] divider;reg[15:0] remaining,previous_duration;
 reg[10:0] previous_step;reg was_active,started;
 reg[7:0] pwm;reg[6:0] pulse_ms;
 wire changed=step_index!=previous_step;
 wire skipped=changed && target_led==0 && target_duration_ms!=0;
 wire[16:0] sum={1'b0,(correct ? previous_duration:remaining)}+
                  {1'b0,(skipped ? target_duration_ms:16'd0)};
 wire near_end=remaining!=0 && remaining<=80;
 wire[7:0] level=remaining==0 ? 8'd255:near_end ? (pulse_ms<40 ? 8'd240:8'd72):8'd80;
 assign led=target_led & {7{active && !paused && (level==255 || pwm<level)}};
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin divider<=0;remaining<=0;previous_duration<=0;previous_step<=0;
   was_active<=0;started<=0;pwm<=0;pulse_ms<=0;end
  else begin
   pwm<=pwm+1'b1;was_active<=active;previous_step<=step_index;previous_duration<=target_duration_ms;
   if(!active || !was_active)begin divider<=0;remaining<=0;started<=0;pulse_ms<=0;end
   else if(!paused)begin
    if(divider==CLOCKS_PER_MS-1)begin divider<=0;pulse_ms<=pulse_ms>=79 ? 0:pulse_ms+1'b1;
     if(remaining!=0)remaining<=remaining-1'b1;
    end else divider<=divider+1'b1;
    if(correct)begin remaining<=sum[16] ? 16'hffff:sum[15:0];started<=1;pulse_ms<=0;end
    else if(skipped && started)remaining<=sum[16] ? 16'hffff:sum[15:0];
   end
  end
 end
endmodule
