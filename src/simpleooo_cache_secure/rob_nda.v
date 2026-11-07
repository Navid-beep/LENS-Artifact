`include "param.v"

module rob (

    input   clk, 
    input   rst, 

    input[`INST_LEN-1:0] F_inst,

    // Fetched Signals
    input [`MEMI_SIZE_LOG-1:0]           F_pc,
    input [`INST_SIZE_LOG-1:0]           F_opcode,
    input [`RF_SIZE_LOG-1  :0]           F_rs1,
    input                                F_rs1_stall, 
    input [`REG_LEN-1      :0]           F_rs1_imm,
    input [`REG_LEN-1      :0]           F_rs1_data,
    input [`MEMI_SIZE_LOG-1:0]           F_rs1_br_offset,
    input [`ROB_SIZE_LOG*`RF_SIZE-1 :0]  renameTB_ROBlink_w,
    input [`RF_SIZE_LOG-1  :0]           F_rs2, 
    input                                F_rs2_stall,
    input [`REG_LEN-1      :0]           F_rs2_data,
    input                                F_rd_data_use_execute,
    input                                F_wen, 
    input [`RF_SIZE_LOG-1  :0]           F_rd,
    input                                F_mem_valid,
    input                                F_mem_rdwt, 
    input                                F_is_br, 
    input                                F_taken, 

    // ROB wire signals
    input [`REG_LEN-1      :0]  ROB_rd_data_wire,
    input [`MEMD_SIZE_LOG-1:0]  ROB_mem_addr_wire,
    input [`REG_LEN-1      :0]  ROB_mem_data_wire,
    input                       ROB_taken_wire,
    input [`MEMI_SIZE_LOG-1:0]  ROB_next_pc_wire,

    // ROB Input to ALU
    output reg [`INST_LEN-1:0] ROB_inst_wire, // formal

    output reg [`MEMI_SIZE_LOG-1:0] ROB_pc_wire,
    output reg [`INST_SIZE_LOG-1:0] ROB_op_wire,
    output reg [`REG_LEN-1      :0] ROB_rs1_imm_wire,
    output reg [`REG_LEN-1      :0] ROB_rs1_data_wire,
    output reg [`MEMI_SIZE_LOG-1:0] ROB_rs1_br_offset_wire,
    output reg [`REG_LEN-1      :0] ROB_rs2_data_wire,
    output reg                     ROB_rd_data_use_execute_wire,
    output reg                     ROB_is_br_wire,

    output reg [`ROB_SIZE-1     :0] ROB_exe_this_cycle,

    // ROB output signals
    output [`ROB_STATE_LEN*`ROB_SIZE-1 :0] ROB_state_w,
    output [`REG_LEN*`ROB_SIZE-1       :0] ROB_rd_data_w,

    output reg [`ROB_SIZE_LOG-1            :0] ROB_head,
    output reg [`ROB_SIZE_LOG-1            :0] ROB_tail,

    output                      ROB_full,
    output                      ROB_empty,

    // Commit Signals
    output                      C_valid,
    output                      C_mem_valid,
    output                      C_mem_rdwt,
    output [`MEMD_SIZE_LOG-1:0] C_mem_addr,
    output [`REG_LEN-1      :0] C_mem_data,
    output                      C_is_br,
    output                      C_taken,
    output                      C_squash,
    output [`MEMI_SIZE_LOG-1:0] C_next_pc,
    output                      C_wen,
    output [`RF_SIZE_LOG-1  :0] C_rd,
    output [`REG_LEN-1      :0] C_rd_data

`ifdef FORMAL
    ,
    output [`MEMD_SIZE_LOG-1:0] ld_addr,

    output [`INST_SIZE_LOG*`ROB_SIZE-1:0]    ROB_op_w, 
    output  [`MEMI_SIZE_LOG*`ROB_SIZE-1:0]   ROB_pc_w,
    output  [`RF_SIZE_LOG*`ROB_SIZE-1  :0]   ROB_rs1_w,
    output  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rs1_imm_w,
    output  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rs1_data_w,
    output  [`ROB_SIZE_LOG*`ROB_SIZE-1 :0]   ROB_rs1_ROBlink_w,
    output  [`MEMI_SIZE_LOG*`ROB_SIZE-1:0]   ROB_rs1_br_offset_w,
    output  [`RF_SIZE_LOG*`ROB_SIZE-1  :0]   ROB_rs2_w,
    output  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rs2_data_w,
    output  [`ROB_SIZE_LOG*`ROB_SIZE-1 :0]   ROB_rs2_ROBlink_w,
    output  [`RF_SIZE_LOG*`ROB_SIZE-1  :0]   ROB_rd_w,
    output  [`MEMD_SIZE_LOG*`ROB_SIZE-1:0]   ROB_mem_addr_w,
    output  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_mem_data_w,
    output  [`MEMI_SIZE_LOG*`ROB_SIZE-1:0]   ROB_next_pc_w,

    output  [`ROB_SIZE-1     :0]             ROB_rs1_stall_o,
    output  [`ROB_SIZE-1     :0]             ROB_rs2_stall_o,
    output  [`ROB_SIZE-1     :0]             ROB_rd_data_use_execute_o,
    output  [`ROB_SIZE-1     :0]             ROB_wen_o,
    output  [`ROB_SIZE-1     :0]             ROB_mem_valid_o,
    output  [`ROB_SIZE-1     :0]             ROB_mem_rdwt_o,
    output  [`ROB_SIZE-1     :0]             ROB_is_br_o,
    output  [`ROB_SIZE-1     :0]             ROB_predicted_taken_o,
    output  [`ROB_SIZE-1     :0]             ROB_taken_o,
    output  [`ROB_SIZE-1     :0]             ROB_STORE_stall_o


  `endif

);

    /*------------------------------
    |       Formal Work Around      |
    -------------------------------*/
    `ifdef FORMAL
    assign ROB_rs1_stall_o            = ROB_rs1_stall;
    assign ROB_rs2_stall_o            = ROB_rs2_stall;
    assign ROB_rd_data_use_execute_o  = ROB_rd_data_use_execute;
    assign ROB_wen_o                  = ROB_wen;
    assign ROB_mem_valid_o            = ROB_mem_valid;
    assign ROB_mem_rdwt_o             = ROB_mem_rdwt;
    assign ROB_is_br_o                = ROB_is_br;
    assign ROB_predicted_taken_o      = ROB_predicted_taken;
    assign ROB_taken_o                = ROB_taken;
    assign ROB_STORE_stall_o          = ROB_STORE_stall;

    `endif
    wire [`MEMD_SIZE_LOG-1:0] ld_addr;


    /*---------------------------------------
    |       Un-packed Array Work Around      |
    ----------------------------------------*/
    genvar p_idx;

    generate
    // INPUT
    for (p_idx=0; p_idx < `RF_SIZE; p_idx++) begin
      assign renameTB_ROBlink[p_idx]  = renameTB_ROBlink_w[p_idx*`ROB_SIZE_LOG +: `ROB_SIZE_LOG];
    end

    // OUTPUT
    for (p_idx=0; p_idx < `ROB_SIZE; p_idx++) begin
      assign ROB_state_w    [p_idx*`ROB_STATE_LEN +: `ROB_STATE_LEN]    = ROB_state     [p_idx];
      assign ROB_rd_data_w  [p_idx*`REG_LEN +: `REG_LEN]                = ROB_rd_data   [p_idx];

      `ifdef FORMAL

      assign ROB_op_w           [p_idx*`INST_SIZE_LOG +: `INST_SIZE_LOG] = ROB_op[p_idx];
      assign ROB_pc_w           [p_idx*`MEMI_SIZE_LOG +: `MEMI_SIZE_LOG] = ROB_pc[p_idx];
      assign ROB_rs1_w          [p_idx*`RF_SIZE_LOG +: `RF_SIZE_LOG]     = ROB_rs1[p_idx];
      assign ROB_rs1_imm_w      [p_idx*`REG_LEN +: `REG_LEN]             = ROB_rs1_imm[p_idx];
      assign ROB_rs1_data_w     [p_idx*`REG_LEN +: `REG_LEN]             = ROB_rs1_data[p_idx];
      assign ROB_rs1_ROBlink_w  [p_idx*`ROB_SIZE_LOG +: `ROB_SIZE_LOG]   = ROB_rs1_ROBlink[p_idx];
      assign ROB_rs1_br_offset_w[p_idx*`MEMI_SIZE_LOG +: `MEMI_SIZE_LOG] = ROB_rs1_br_offset[p_idx];
      assign ROB_rs2_w          [p_idx*`RF_SIZE_LOG +: `RF_SIZE_LOG]     = ROB_rs2[p_idx];
      assign ROB_rs2_data_w     [p_idx*`REG_LEN +: `REG_LEN]             = ROB_rs2_data[p_idx];
      assign ROB_rs2_ROBlink_w  [p_idx*`ROB_SIZE_LOG +: `ROB_SIZE_LOG]   = ROB_rs2_ROBlink[p_idx];
      assign ROB_rd_w           [p_idx*`RF_SIZE_LOG +: `RF_SIZE_LOG]     = ROB_rd[p_idx];
      assign ROB_mem_addr_w     [p_idx*`MEMD_SIZE_LOG +: `MEMD_SIZE_LOG] = ROB_mem_addr[p_idx];
      assign ROB_mem_data_w     [p_idx*`REG_LEN +: `REG_LEN]             = ROB_mem_data[p_idx];
      assign ROB_next_pc_w      [p_idx*`MEMI_SIZE_LOG +: `MEMI_SIZE_LOG] = ROB_next_pc[p_idx];


      `endif
    end
    endgenerate  
    
    /*---------------
    |       ROB      |
    ----------------*/

  // STEP: ROB
  reg  [`ROB_STATE_LEN-1:0] ROB_state [`ROB_SIZE-1:0];
  reg  [`INST_LEN-1:0]      ROB_inst [`ROB_SIZE-1:0]; // formal
  
  reg  [`MEMI_SIZE_LOG-1:0] ROB_pc [`ROB_SIZE-1:0];
  reg  [`INST_SIZE_LOG-1:0] ROB_op [`ROB_SIZE-1:0];

  reg  [`RF_SIZE_LOG-1  :0] ROB_rs1           [`ROB_SIZE-1:0];
  reg  [`ROB_SIZE-1     :0] ROB_rs1_stall;
  reg  [`REG_LEN-1      :0] ROB_rs1_imm       [`ROB_SIZE-1:0];
  reg  [`REG_LEN-1      :0] ROB_rs1_data      [`ROB_SIZE-1:0];
  reg  [`ROB_SIZE_LOG-1 :0] ROB_rs1_ROBlink   [`ROB_SIZE-1:0];
  reg  [`MEMI_SIZE_LOG-1:0] ROB_rs1_br_offset [`ROB_SIZE-1:0];
  reg  [`RF_SIZE_LOG-1  :0] ROB_rs2           [`ROB_SIZE-1:0];
  reg  [`ROB_SIZE-1     :0] ROB_rs2_stall;
  reg  [`REG_LEN-1      :0] ROB_rs2_data      [`ROB_SIZE-1:0];
  reg  [`ROB_SIZE_LOG-1 :0] ROB_rs2_ROBlink   [`ROB_SIZE-1:0];
  reg  [`ROB_SIZE-1     :0] ROB_rd_data_use_execute;

  reg  [`ROB_SIZE-1     :0] ROB_wen;
  reg  [`RF_SIZE_LOG-1  :0] ROB_rd      [`ROB_SIZE-1:0];
  reg  [`REG_LEN-1      :0] ROB_rd_data [`ROB_SIZE-1:0];

  reg  [`ROB_SIZE-1     :0] ROB_mem_valid;
  reg  [`ROB_SIZE-1     :0] ROB_mem_rdwt;
  reg  [`MEMD_SIZE_LOG-1:0] ROB_mem_addr[`ROB_SIZE-1:0];
  reg  [`REG_LEN-1      :0] ROB_mem_data[`ROB_SIZE-1:0];

  reg  [`ROB_SIZE-1     :0] ROB_is_br;
  reg  [`ROB_SIZE-1     :0] ROB_predicted_taken;
  reg  [`ROB_SIZE-1     :0] ROB_taken;
  reg  [`MEMI_SIZE_LOG-1:0] ROB_next_pc [`ROB_SIZE-1:0];

  // ST-LD Hazards
  reg  [`ROB_SIZE-1     :0] ROB_STORE_stall;


// Rename Table
wire [`ROB_SIZE_LOG-1 :0]  renameTB_ROBlink [`RF_SIZE-1:0];


`ifdef USE_CACHE
  reg [`MEMD_SIZE_LOG-1:0] cached_addr;
`endif

  // ST-LD Hazards
  always @(*) begin
    integer m;
    for (m=0; m<`ROB_SIZE; m++) begin
      if (ROB_op[m] == `INST_OP_ST) begin
        ROB_STORE_stall[m] <= !(ROB_state[m] == `FINISHED && m == ROB_head);
      end else begin
        ROB_STORE_stall[m] <= 0;
      end
    end
  end


  always@(posedge clk) begin
    integer i, k;
    if (rst) begin
      for (i=0; i<`ROB_SIZE; i=i+1) begin
        ROB_state[i] <= `IDLE;
        ROB_pc[i] <= 0;
        ROB_op[i] <= 0;
        ROB_inst[i] <= 0;

        ROB_rs1                [i] <= 0;
        ROB_rs1_stall          [i] <= 0;
        ROB_rs1_imm            [i] <= 0;
        ROB_rs1_data           [i] <= 0;
        ROB_rs1_br_offset      [i] <= 0;
        ROB_rs1_ROBlink        [i] <= 0;
        ROB_rs2                [i] <= 0;
        ROB_rs2_stall          [i] <= 0;
        ROB_rs2_data           [i] <= 0;
        ROB_rs2_ROBlink        [i] <= 0;
        ROB_rd_data_use_execute[i] <= 0;

        ROB_wen                [i] <= 0;
        ROB_rd                 [i] <= 0;
        ROB_rd_data            [i] <= 0;

        ROB_mem_valid[i] <= 0;
        ROB_mem_rdwt [i] <= 0;

        ROB_mem_addr[i]         <= 0;
        ROB_mem_data[i]         <= 0;

        ROB_is_br          [i] <= 0;
        ROB_predicted_taken[i] <= 0;
        ROB_taken          [i]        <= 0;
        ROB_next_pc        [i]        <= 0;

      end
      ROB_head <= 0;
      ROB_tail <= 0;

      
`ifdef USE_CACHE
      cached_addr <= 0;
`endif
    end

    // STEP.1: squash
    else if (C_valid && C_squash) begin
      for (i=0; i<`ROB_SIZE; i=i+1) begin
        ROB_state[i] <= `IDLE;
        ROB_rd_data[i] <= 0;
      end
      ROB_head <= 0;
      ROB_tail <= 0;
    end

    else begin
      // STEP.2: push
      if (!ROB_full) begin
        ROB_state[ROB_tail] <= `STALLED;

        ROB_inst[ROB_tail] <= F_inst;

        ROB_pc[ROB_tail] <= F_pc;
        ROB_op[ROB_tail] <= F_opcode;

        ROB_rs1                [ROB_tail] <= F_rs1;
        ROB_rs1_stall          [ROB_tail] <= F_rs1_stall;
        ROB_rs1_imm            [ROB_tail] <= F_rs1_imm;
        ROB_rs1_data           [ROB_tail] <= F_rs1_data;
        ROB_rs1_br_offset      [ROB_tail] <= F_rs1_br_offset;
        ROB_rs1_ROBlink        [ROB_tail] <= renameTB_ROBlink[F_rs1];
        ROB_rs2                [ROB_tail] <= F_rs2;
        ROB_rs2_stall          [ROB_tail] <= F_rs2_stall;
        ROB_rs2_data           [ROB_tail] <= F_rs2_data;
        ROB_rs2_ROBlink        [ROB_tail] <= renameTB_ROBlink[F_rs2];
        ROB_rd_data_use_execute[ROB_tail] <= F_rd_data_use_execute;

        ROB_wen                [ROB_tail] <= F_wen;
        ROB_rd                 [ROB_tail] <= F_rd;

        ROB_mem_valid[ROB_tail] <= F_mem_valid;
        ROB_mem_rdwt [ROB_tail] <= F_mem_rdwt;

        ROB_is_br          [ROB_tail] <= F_is_br;
        ROB_predicted_taken[ROB_tail] <= F_taken;
        ROB_tail <= ROB_tail + 1;
      end

      for (i=0; i<`ROB_SIZE; i=i+1) begin
        if (ROB_state[i]==`STALLED && !ROB_rs1_stall[i] && !ROB_rs2_stall[i]) begin

          if (!(|ROB_STORE_stall)) begin
            if (!( ROB_op[i]==`INST_OP_LD && !(ROB_head==i))) begin
              ROB_state [i] <= `READY;
            end
          end else begin
            if (!(ROB_op[i]==`INST_OP_LD && !(ROB_head==i))) begin
              ROB_state [i] <= `READY;
            end 
          end
        end
      end

      // STEP.4: execute
      for (i=0; i<`ROB_SIZE; i=i+1) begin
        if (ROB_state[i]==`READY && ROB_exe_this_cycle[i]) begin
          ROB_rd_data [i] <= ROB_rd_data_wire;
          ROB_mem_addr[i] <= ROB_mem_addr_wire;
          ROB_mem_data[i] <= ROB_mem_data_wire;
          ROB_taken   [i] <= ROB_taken_wire;
          ROB_next_pc [i] <= ROB_next_pc_wire;

`ifdef USE_CACHE
          if (ROB_op[i]==`INST_OP_LD && ROB_mem_addr_wire!=cached_addr)
            ROB_state [i] <= `EXECUTING_1;
          else
            ROB_state [i] <= `FINISHED;
`else
          ROB_state [i] <= `FINISHED;
`endif
        end

`ifdef USE_CACHE
        if (ROB_state[i]==`EXECUTING_1) begin
            ROB_state [i] <= `EXECUTING_0;
        end

        if (ROB_state[i]==`EXECUTING_0) begin
          ROB_state [i] <= `FINISHED;
          if (ROB_op[i]==`INST_OP_LD)
            cached_addr <= ROB_mem_addr[i];
        end
`endif
      end


      // STEP.5: forward
      for (i=0; i<`ROB_SIZE; i=i+1) begin
          if (ROB_state[i]==`FINISHED) begin
            for (k=0; k<`ROB_SIZE; k=k+1) begin
              if (ROB_state[k]==`STALLED && ROB_rs1_stall[k] && ROB_rs1_ROBlink[k]==i[`ROB_SIZE_LOG-1:0]) begin
                ROB_rs1_stall[k] <= 1'b0;
                ROB_rs1_data[k] <= ROB_rd_data[i];
              end

              if (ROB_state[k]==`STALLED && ROB_rs2_stall[k] && ROB_rs2_ROBlink[k]==i[`ROB_SIZE_LOG-1:0]) begin
                ROB_rs2_stall[k] <= 1'b0;
                ROB_rs2_data[k] <= ROB_rd_data[i];
              end
            end
          end
      end


      // STEP.6: pop
      if (C_valid) begin

        ROB_state[ROB_head] <= `IDLE;
        ROB_rd_data[ROB_head] <= 0;
        ROB_head <= ROB_head + 1;

      end
    end
  end

  assign ROB_full  = ROB_state[ROB_tail] != `IDLE;
  assign ROB_empty = ROB_state[ROB_head] == `IDLE;


  // STEP: Execute + Memory Read
  // STEP.X: arbitor to choose an entry in ROB

  always @(*) begin
    integer j;
    ROB_exe_this_cycle = 0;
    for (j=`ROB_SIZE-1; j >= 0; j=j-1) begin
      if (ROB_state[j]==`READY) begin
        ROB_exe_this_cycle = (1 << j);
      end
    end
  end


  // STEP.X: choose an input to alu

  always @(*) begin
    integer l;
    ROB_pc_wire                  = 0;
    ROB_op_wire                  = 0;
    ROB_rs1_imm_wire             = 0;
    ROB_rs1_data_wire            = 0;
    ROB_rs1_br_offset_wire       = 0;
    ROB_rs2_data_wire            = 0;
    ROB_rd_data_use_execute_wire = 0;
    ROB_is_br_wire               = 0;
    for (l=0; l < `ROB_SIZE; l=l+1) begin
      ROB_pc_wire                  = ROB_pc_wire                  | {`MEMI_SIZE_LOG{ROB_exe_this_cycle[l]}} & ROB_pc[l];
      ROB_op_wire                  = ROB_op_wire                  | {`INST_SIZE_LOG{ROB_exe_this_cycle[l]}} & ROB_op[l];
      ROB_rs1_imm_wire             = ROB_rs1_imm_wire             | {`REG_LEN      {ROB_exe_this_cycle[l]}} & ROB_rs1_imm[l];
      ROB_rs1_data_wire            = ROB_rs1_data_wire            | {`REG_LEN      {ROB_exe_this_cycle[l]}} & ROB_rs1_data[l];
      ROB_rs1_br_offset_wire       = ROB_rs1_br_offset_wire       | {`MEMI_SIZE_LOG{ROB_exe_this_cycle[l]}} & ROB_rs1_br_offset[l];
      ROB_rs2_data_wire            = ROB_rs2_data_wire            | {`REG_LEN      {ROB_exe_this_cycle[l]}} & ROB_rs2_data[l];
      ROB_rd_data_use_execute_wire = ROB_rd_data_use_execute_wire |                 ROB_exe_this_cycle[l]   & ROB_rd_data_use_execute[l];
      ROB_is_br_wire               = ROB_is_br_wire               |                 ROB_exe_this_cycle[l]   & ROB_is_br[l];
    end
  end


    /*------------------------
    |      Commit Signals    |
    -------------------------*/


  assign C_valid = ROB_state[ROB_head]==`FINISHED;

  assign C_mem_valid = ROB_mem_valid[ROB_head];
  assign C_mem_rdwt  = ROB_mem_rdwt [ROB_head];
  assign C_mem_addr  = ROB_mem_addr [ROB_head];
  assign C_mem_data  = ROB_mem_data [ROB_head];

  assign C_is_br   = ROB_is_br  [ROB_head];
  assign C_taken   = ROB_taken  [ROB_head];
  assign C_squash  = C_is_br &&
                     (ROB_predicted_taken[ROB_head] != ROB_taken[ROB_head]);
  assign C_next_pc = ROB_next_pc[ROB_head];

  assign C_wen     = ROB_wen    [ROB_head];
  assign C_rd      = ROB_rd     [ROB_head];
  assign C_rd_data = ROB_rd_data[ROB_head];

  // Formal Obs

  assign ROB_inst_wire = ROB_inst[ROB_head];

  wire [`MEMI_SIZE_LOG-1:0] ROB_pc_commit;
  assign ROB_pc_commit = ROB_pc[ROB_head];

// `ifdef FORMAL
    // `ifndef PARTIAL_DOM_USE_MISS_ONLY
        assign ld_addr = (|(ROB_exe_this_cycle & ROB_mem_rdwt & ROB_mem_valid)) ? ROB_mem_addr_wire : 0;
    // `endif
// `endif

endmodule

