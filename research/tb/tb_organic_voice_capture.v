`timescale 1ns/1ps
module tb_organic_voice_capture;
    reg clk=0,rst_n=0,gate=0,timbre=1;
    reg [7:0] velocity=176;
    reg [31:0] step=32'd23409859;
    wire signed [15:0] sound;
    integer n,local_n,note_number,fd,unused;
    reg [2047:0] output_path;
    always #5 clk=~clk;
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(1'b1),.gate(gate),
        .phase_step(step),.velocity(velocity),.timbre(timbre),.sample_out(sound));
    initial begin
        output_path="build/organic_20261027/new.hex";
        unused=$value$plusargs("OUT=%s",output_path);
        fd=$fopen(output_path,"w");if(!fd)$fatal(1,"cannot open capture");
        repeat(3)@(negedge clk);rst_n=1;
`ifdef TEXTURE_ABLATION
        // Controlled comparison: remove only the air/bow contribution.
        // Drift and tonal/body states still run identically.
        force voice.organic_instrument.colour.texture_product=27'sd0;
`endif
        for(n=0;n<576000;n=n+1)begin
            timbre=n<288000;local_n=n%288000;
            note_number=(local_n-9600)/21600;
            gate=local_n>=9600 && local_n<182400 ? ((local_n-9600)%21600)<20160 :
                 local_n>=201600 && local_n<278400;
            velocity=local_n<96000 ? 8'd104 : 8'd208;
            case(note_number)
                0,7:step=32'd23409859; // C4
                1,5:step=32'd29494575; // E4
                2,4:step=32'd35075158; // G4
                3:step=32'd39370534;   // A4
                6:step=32'd26276679;   // D4
                default:step=32'd46819719; // held C5
            endcase
            @(negedge clk);
            if((^sound)===1'bx)$fatal(1,"unknown audio at %0d",n);
            $fdisplay(fd,"%04x",sound);
        end
        $fclose(fd);$display("PASS: actual RTL organic timbre phrase and held notes captured");$finish;
    end
endmodule
