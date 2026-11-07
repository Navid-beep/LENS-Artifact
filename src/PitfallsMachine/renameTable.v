`include "param.v"

module renameTable (
    input clk, 
    input rst, 

    // Commit Signals
    input                      C_squash,
    input                      C_valid, 
    input                      C_wen,
    input [`RF_SIZE_LOG-1  :0] C_rd, 

    // ROB
    input                       ROB_full, 
    input [`ROB_SIZE_LOG-1 :0]  ROB_tail,
    input [`ROB_SIZE_LOG-1 :0]  ROB_head,


    // Fetch
    input                      F_wen, 
    input [`RF_SIZE_LOG-1  :0] F_rd,

    // Rename Table
    output reg [`RF_SIZE-1           :0]    renameTB_valid,
    output  [`ROB_SIZE_LOG*`RF_SIZE-1:0]    renameTB_ROBlink_w


);


    /*---------------------------------------
    |       Un-packed Array Work Around      |
    ----------------------------------------*/
    genvar p_idx;

    generate
        for (p_idx=0; p_idx < `RF_SIZE; p_idx++) begin
            assign renameTB_ROBlink_w[p_idx*`ROB_SIZE_LOG +: `ROB_SIZE_LOG]  = renameTB_ROBlink[p_idx];
        end
    endgenerate


    /*-------------------------
    |       Rename Table       |
    --------------------------*/

  // Rename Table Signals
  reg  [`ROB_SIZE_LOG-1:0] renameTB_ROBlink [`RF_SIZE-1:0];

  wire renameTB_clearEntry, renameTB_addEntry, renameTB_clearAddConflict;

  assign renameTB_clearEntry       = C_valid && C_wen && (renameTB_ROBlink[C_rd]==ROB_head);
  assign renameTB_addEntry         = !ROB_full && F_wen;
  assign renameTB_clearAddConflict = renameTB_addEntry && renameTB_clearEntry && F_rd==C_rd;



  always @(posedge clk) begin
      integer i;
    if (rst)        begin 
      for (i=0; i<`RF_SIZE; i++) begin
        renameTB_valid[i]         <= 1'b0;
      end
    end

    else if (C_squash && C_valid)
      for (i=0; i<`RF_SIZE; i++) begin
        renameTB_valid[i]         <= 1'b0;
      end else begin
      // TODO: make visible point earlier
      if (renameTB_clearEntry && !renameTB_clearAddConflict) begin
        renameTB_valid        [C_rd] <= 1'b0;
      end

      if (renameTB_addEntry) begin
        renameTB_valid[F_rd]         <= 1'b1;
      end
    end
  end



  always @(posedge clk) begin
  integer j;
    if (rst) begin
      for (j=0; j<`RF_SIZE; j++) begin
        renameTB_ROBlink[j]  <= `RF_SIZE_LOG'd0;  
      end
    end else if (!ROB_full && F_wen) begin
      renameTB_ROBlink[F_rd] <= ROB_tail;
    end
  end  
endmodule
