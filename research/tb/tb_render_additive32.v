`timescale 1ns/1ps
// Digital-only audio capture; not a physical MAX98357A measurement.
module tb_render_additive32;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, sample_tick=0;
    reg [31:0] mask=32'hffffffff;
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer clocks=0, frames=0, written_all=0, written_off=0;
    integer file_all, file_off;
    additive32_tm dut(
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .gate(1'b1),.base_step(32'd23409859),.velocity(8'd180),
        .component_mask(mask),.sample_out(sample_out),
        .sample_valid(sample_valid));
    initial begin
        file_all=$fopen("build/additive32_all.txt","w");
        file_off=$fopen("build/additive32_no32.txt","w");
        if(file_all==0 || file_off==0)
            $fatal(1,"cannot open additive32 captures");
        #20 rst_n=1;
    end
    always @(negedge clk) if(rst_n) begin
        sample_tick=(clocks==0);
        clocks=(clocks+1)%80;
        if(sample_tick) frames=frames+1;
        if(frames==9200) mask[31]=0;
    end
    always @(posedge clk) if(rst_n && sample_valid) begin
        if(frames>1000 && frames<=9192) begin
            $fwrite(file_all,"%0d\n",sample_out);
            written_all=written_all+1;
        end
        if(frames>9300 && frames<=17492) begin
            $fwrite(file_off,"%0d\n",sample_out);
            written_off=written_off+1;
        end
        if(written_all==8192 && written_off==8192) begin
            $fclose(file_all); $fclose(file_off);
            $display("PASS: captured both 8192-sample 32-component renders");
            $finish;
        end
    end
endmodule
