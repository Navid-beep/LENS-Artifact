`include "param.v"


module memd (
    input clk, 
    input rst, 

    input C_valid, 
    input C_mem_valid, 
    input C_mem_rdwt, 

    input [`MEMD_SIZE_LOG-1:0] C_mem_addr,
    input [`REG_LEN-1      :0] C_mem_data,

    output [`REG_LEN*`MEMD_SIZE-1:0] memd_w
    
);

    /*---------------------------------------
    |       Un-packed Array Work Around      |
    ----------------------------------------*/
    genvar p_idx;

    generate
    // INPUT
    for (p_idx=0; p_idx < `MEMD_SIZE; p_idx++) begin
      assign memd_w[p_idx*`REG_LEN +: `REG_LEN]  = memd[p_idx];
    end
    endgenerate

    /*---------------
    |      MEMD     |
    ----------------*/

    reg [`REG_LEN-1:0] memd [`MEMD_SIZE-1:0];

    // integer i;

    wire memd_symbolic;

    always @(posedge clk) begin
        if (rst) begin
                memd[0] <= 6;
                memd[1] <= 7;
                memd[2] <= memd_symbolic;
                memd[3] <= 9;
        end else if (C_valid && C_mem_valid && !C_mem_rdwt) begin
            memd[C_mem_addr] <= C_mem_data;
        end
    end
    
endmodule