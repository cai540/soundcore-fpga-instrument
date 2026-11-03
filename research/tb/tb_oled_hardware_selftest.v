`timescale 1ns/1ps
// Independent pin-level slave: no acknowledgement derived from DUT state.
module tb_oled_hardware_selftest #(parameter integer CASE_ID=0,parameter integer INTERNAL_IREF=0);
    reg clk=0,rst_n=0;always #5 clk=~clk;
    tri1 scl,sda;
    reg slave_low=0,receiving=0,selected=0;
    reg [7:0] shift=0,control=0;
    integer bit_count=0,byte_count=0;
    integer ae_count=0,af_count=0,a5_count=0,zero_bytes=0,stripe_bytes=0;
    reg [7:0] previous_command=0;
    integer iref_count=0;
    wire [4:0] passed;wire fault,boot_test;wire [2:0] fault_code;wire [1:0] pattern;
    wire [7:0] active_address=CASE_ID==1 ? 8'h7A:8'h78;
    assign sda=(slave_low || CASE_ID==3) ? 1'b0:1'bz;
    assign scl=CASE_ID==4 ? 1'b0:1'bz;
    oled_hardware_selftest #(.I2C_DIV(2),.BOOT_CYCLES(80),
        .LINE_STABLE_CYCLES(8),.LINE_TIMEOUT_CYCLES(80),.HOLD_CYCLES(32),.INTERNAL_IREF(INTERNAL_IREF)) dut(
        .clk(clk),.rst_n(rst_n),.scl(scl),.sda(sda),.passed(passed),.fault(fault),
        .fault_code(fault_code),.boot_lamp_test(boot_test),.pattern(pattern));
    always @(negedge sda) if(scl===1'b1)begin
        receiving=1;selected=0;bit_count=0;byte_count=0;shift=0;
    end
    always @(posedge sda) if(scl===1'b1)begin
        receiving=0;selected=0;bit_count=0;byte_count=0;
    end
    always @(posedge scl)if(receiving)begin
        if(bit_count<8)begin
            shift={shift[6:0],sda};bit_count=bit_count+1;
            if(bit_count==8)begin
                if(byte_count==0)selected=CASE_ID!=2 && (CASE_ID==5 || shift==active_address);
                else if(selected)begin
                    if(byte_count==1)control=shift;
                    if(byte_count==2)begin
                        if(CASE_ID==6 && control==0 && shift==8'hA8)selected=0;
                        if(CASE_ID==7 && control==8'h40)selected=0;
                        if(selected && control==0)begin
                            if(previous_command==8'hAD)begin
                                if(shift!=8'h10)$fatal(1,"unexpected internal current reference argument");
                                iref_count=iref_count+1;
                            end
                            previous_command=shift;
                            if(shift==8'hAE)ae_count=ae_count+1;
                            if(shift==8'hAF)af_count=af_count+1;
                            if(shift==8'hA5)a5_count=a5_count+1;
                        end
                        if(selected && control==8'h40)begin
                            if(pattern==1)begin
                                if(shift!==0)$fatal(1,"black pattern has nonzero data");
                                zero_bytes=zero_bytes+1;
                            end
                            if(pattern==2)begin
                                if(shift!==(stripe_bytes%2 ? 8'h55:8'hAA))$fatal(1,"stripe data order wrong");
                                stripe_bytes=stripe_bytes+1;
                            end
                        end
                    end
                end
            end
        end else begin bit_count=0;byte_count=byte_count+1;end
    end
    always @(negedge scl)slave_low=receiving && selected && bit_count==8;
    integer expected_fault;
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        if(CASE_ID<2)begin
            wait(a5_count>=2);
            if(fault || passed!=31 || ae_count!=1 || af_count!=1 || zero_bytes!=1024 || stripe_bytes!=1024)
                $fatal(1,"normal selftest incomplete pass=%b fault=%b AE=%0d AF=%0d zero=%0d stripe=%0d",passed,fault,ae_count,af_count,zero_bytes,stripe_bytes);
            if(dut.address!=active_address)$fatal(1,"wrong discovered address");
            if(INTERNAL_IREF && iref_count!=1)$fatal(1,"internal IREF not configured on actual bus");
        end else begin
            wait(fault);
            case(CASE_ID)
                2:expected_fault=3;
                3,4:expected_fault=1;
                5:expected_fault=2;
                6:expected_fault=4;
                7:expected_fault=5;
            endcase
            if(fault_code!=expected_fault)$fatal(1,"wrong fault code case=%0d got=%0d",CASE_ID,fault_code);
            if((CASE_ID==3 || CASE_ID==4) && passed!=0)$fatal(1,"stuck line accepted");
            if(CASE_ID==5 && passed[1])$fatal(1,"false ACK accepted");
        end
        $display("PASS: OLED independent selftest case %0d pass=%b fault=%0d",CASE_ID,passed,fault_code);$finish;
    end
    initial begin #15000000;$fatal(1,"selftest timeout phase=%0d pass=%b",dut.phase,passed);end
endmodule
