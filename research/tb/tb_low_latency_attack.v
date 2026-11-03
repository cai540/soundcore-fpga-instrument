`timescale 1ns/1ps
module tb_low_latency_attack;
    reg clk=0,rst_n=0,tick=0,timbre=1;
    reg [31:0] gate=0;
    reg [7:0] velocity=176;
    wire signed [15:0] live_sound,song_sound;
    wire valid;
    integer n,k,kind,target,prev_live,prev_song,delta_live,delta_song;
    integer first_live,first_song,first_cold_ms,checks=0;
    reg [31:0] preserved_phase;
    reg [15:0] retained_live,retained_song;
    always #5 clk=~clk;
    poly_synth32_tm live(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),
        .phase_step({32{32'd23409859}}),.velocity({32{velocity}}),.expression({32{velocity}}),.pitch_index({32{7'd24}}),.timbre(timbre),
        .sample_out(live_sound),.sample_valid(valid));
    synth_voice #(.INSTRUMENT_PRESETS(1)) song(.clk(clk),.rst_n(rst_n),
        .sample_tick(tick),.gate(gate[0]),.phase_step(32'd23409859),
        .velocity(velocity),.expression(velocity),.pitch_index(7'd24),.timbre(timbre),.sample_out(song_sound));
    task frame;
        begin
            @(negedge clk);tick=1;@(negedge clk);tick=0;
            repeat(200)@(negedge clk);
            if(live.completed_voice_count!=32)$fatal(1,"32-voice frame missed deadline");
            if((^live_sound)===1'bx || (^song_sound)===1'bx)$fatal(1,"unknown audio");
        end
    endtask
    task reset;
        begin rst_n=0;gate=0;repeat(3)@(negedge clk);rst_n=1;frame();end
    endtask
    initial begin
        for(kind=0;kind<2;kind=kind+1)begin
            timbre=kind;target=kind ? 30000 : 28000;
            reset();gate=1;prev_live=0;prev_song=0;first_live=-1;first_song=-1;
            for(n=0;n<800;n=n+1)begin
                frame();checks=checks+1;
                if(live.envelope[0]!==song.envelope)$fatal(1,"live/offline attack mismatch");
                if(n==((kind ? 128:256)+2) && live.envelope[0]!=target)$fatal(1,"attack deadline missed");
                if(live.envelope[0]>target || song.envelope>target)
                    $fatal(1,"onset has an accent above the sustained level");
                if(live.envelope[0]<prev_live || song.envelope<prev_song)
                    $fatal(1,"held onset decays instead of smoothly rising");
                delta_live=live.envelope[0]-prev_live;delta_song=song.envelope-prev_song;
                if(delta_live>475 || delta_song>475)$fatal(1,"onset amplitude step too sharp");
                if(n<4 && (live.envelope[0]>16 || song.envelope>16))
                    $fatal(1,"onset does not start with zero slope");
                if(first_live<0 && live_sound!=0)first_live=n;
                if(first_song<0 && song_sound!=0)first_song=n;
                prev_live=live.envelope[0];prev_song=song.envelope;
            end
            if(first_live<0 || first_live>48 || first_song<0 || first_song>48)
                $fatal(1,"onset inserted more than 1ms event silence");
            if(live.envelope[0]!=target || song.envelope!=target)
                $fatal(1,"sustained volume changed");
            // A repeated gate during the tail must retain envelope and phase.
            gate=0;repeat(96)frame();retained_live=live.envelope[0];retained_song=song.envelope;
            preserved_phase=live.phase[0];gate=1;frame();
            if(live.envelope[0]!=retained_live || song.envelope!=retained_song)
                $fatal(1,"retrigger chopped its existing tail");
            if(live.phase[0]==0 || live.phase[0]==preserved_phase)
                $fatal(1,"retrigger restarted/stopped its running oscillator");
            prev_live=live.envelope[0];prev_song=song.envelope;
            repeat(600)begin frame();
                if(live.envelope[0]<prev_live || song.envelope<prev_song)
                    $fatal(1,"retrigger envelope is discontinuous");
                prev_live=live.envelope[0];prev_song=song.envelope;
            end
            // Repeated 4ms taps do not silence another sustained slot.
            gate=3;repeat(650)frame();
            for(k=0;k<12;k=k+1)begin
                gate[0]=0;repeat(192)frame();gate[0]=1;repeat(192)frame();
                if(live.envelope[1]!=target || !live.gate_last[1])
                    $fatal(1,"rapid repeats silenced another voice");
            end
            $display("PASS: timbre=%0d no onset accent; first live/song sample at %0d/%0d frames; sustain and retrigger intact",kind,first_live,first_song);
        end
        $display("PASS: %0d cold-onset checks, both engines, rapid tapping and independent held notes",checks);
        $finish;
    end
endmodule
