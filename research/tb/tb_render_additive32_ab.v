`timescale 1ns/1ps
// Same C4 and post-compensation velocity for ordinary piano and additive AI0.
module tb_render_additive32_ab;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, sample_tick=0;
    reg [6:0] clocks=0;
    integer frames=0, written=0;
    integer ordinary_file, additive_file;
    wire signed [15:0] ordinary_sample, additive_sample;
    wire signed [15:0] additive_balanced = additive_sample >>> 2;
    wire ordinary_valid, additive_valid;
    playable_synth32 ordinary (
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .gate(32'd1),.note_index(192'd0),
        .velocity({248'd0,8'd90}),.bend(8'd128),.timbre(1'b1),
        .sample_out(ordinary_sample),.sample_valid(ordinary_valid)
    );
    additive32_tm additive (
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .gate(1'b1),.base_step(32'd23409859),.velocity(8'd90),
        .component_mask(32'hffffffff),
        .sample_out(additive_sample),.sample_valid(additive_valid)
    );
    initial begin
        ordinary_file=$fopen("build/additive32_ab_ordinary.txt","w");
        additive_file=$fopen("build/additive32_ab_new.txt","w");
        if (ordinary_file==0 || additive_file==0)
            $fatal(1,"cannot open A/B output files");
        #20 rst_n=1;
    end
    always @(negedge clk) if (rst_n) begin
        sample_tick=(clocks==0);
        clocks=(clocks+1)%80;
        if (sample_tick) frames=frames+1;
    end
    always @(posedge clk) if (rst_n && ordinary_valid && additive_valid) begin
        if (frames>1000 && written<8192) begin
            $fwrite(ordinary_file,"%0d\n",ordinary_sample);
            $fwrite(additive_file,"%0d\n",additive_balanced);
            written=written+1;
        end
        if (written==8192) begin
            $fclose(ordinary_file);
            $fclose(additive_file);
            $display("PASS: captured matched ordinary/additive C4 streams");
            $finish;
        end
    end
endmodule
