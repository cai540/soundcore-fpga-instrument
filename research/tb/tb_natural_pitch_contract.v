`timescale 1ns/1ps
module tb_natural_pitch_contract;
    reg [2:0] bank=0,pad=0;
    reg [3:0] key=0;
    wire [6:0] note;
    wire valid,project_valid,sharp;
    wire [2:0] projected_bank,projected_pad;
    pitch_layout map(.bank(bank),.pad(pad),.key(key),.note_index(note),.valid(valid));
    pitch_projection project(.note_index(note),.key(key),.bank(projected_bank),.pad(projected_pad),.sharp(sharp),.valid(project_valid));
    reg[6:0] table_index=127;wire[31:0] step;
    note_step_table72 lookup(.note_index(table_index),.phase_step(step));
    integer k,b,p,n,checks=0,degree[0:6];real hz,error_cents;
    initial begin
        degree[0]=0;degree[1]=2;degree[2]=4;degree[3]=5;degree[4]=7;degree[5]=9;degree[6]=11;
        for(k=0;k<12;k=k+1)for(b=0;b<5;b=b+1)for(p=0;p<7;p=p+1)begin
            key=k;bank=b;pad=p;#2;
            if(!valid || note!=b*12+k+degree[p] || !project_valid || sharp || projected_pad!=p || projected_bank!=b)
                $fatal(1,"natural mapping key=%0d bank=%0d pad=%0d note=%0d",k,b,p,note);
            checks=checks+1;
        end
        for(n=0;n<128;n=n+1)begin
            table_index=n;#2;
            if(n<72)begin
                hz=440.0*(2.0**((36.0+n-69.0)/12.0));
                error_cents=1200*$ln((step*48000.0/4294967296.0)/hz)/$ln(2.0);
                if(error_cents>0.001 || error_cents< -0.001)$fatal(1,"phase precision %0d",n);
            end else if(step!=0)$fatal(1,"illegal pitch not muted %0d",n);
            checks=checks+1;
        end
        bank=5;#2;if(valid)$fatal(1,"invalid bank accepted");
        bank=0;pad=7;#2;if(valid)$fatal(1,"invalid pad accepted");
        pad=0;key=12;#2;if(valid)$fatal(1,"invalid key accepted");
        $display("PASS: %0d mapping/phase cases, 12 keys x 5 octaves x 7 natural degrees, 72 exact pitches",checks);$finish;
    end
endmodule
