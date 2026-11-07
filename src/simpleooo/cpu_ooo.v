
`include "param.v"


module cpu_ooo(
  input clk,
  input rst
  
`ifndef FORMAL

  );

// `else
`endif
  // Required by Shadow Logic
  wire                      C_mem_valid_o;
  wire                      C_mem_rdwt_o;
  wire [`MEMD_SIZE_LOG-1:0] C_mem_addr_o; 
  wire                      C_taken_o; 
  wire [`MEMD_SIZE_LOG-1:0] ld_addr_o;
  wire                      C_is_br_o;
  wire [`MEMI_SIZE_LOG-1:0] C_next_pc_o;


  // ROB Registers - Contract Generation
  wire [`ROB_STATE_LEN*`ROB_SIZE-1:0]    ROB_state_w; 
  wire [`INST_SIZE_LOG*`ROB_SIZE-1:0]    ROB_op_w; 
  wire  [`MEMI_SIZE_LOG*`ROB_SIZE-1:0]   ROB_pc_w;
  wire  [`RF_SIZE_LOG*`ROB_SIZE-1  :0]   ROB_rs1_w;
  wire  [`ROB_SIZE-1     :0]             ROB_rs1_stall_o;
  wire  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rs1_imm_w;
  wire  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rs1_data_w;
  wire  [`ROB_SIZE_LOG*`ROB_SIZE-1 :0]   ROB_rs1_ROBlink_w;
  wire  [`MEMI_SIZE_LOG*`ROB_SIZE-1:0]   ROB_rs1_br_offset_w;
  wire  [`RF_SIZE_LOG*`ROB_SIZE-1  :0]   ROB_rs2_w;
  wire  [`ROB_SIZE-1     :0]             ROB_rs2_stall_o;
  wire  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rs2_data_w;
  wire  [`ROB_SIZE_LOG*`ROB_SIZE-1 :0]   ROB_rs2_ROBlink_w;
  wire  [`ROB_SIZE-1     :0]             ROB_rd_data_use_execute_o;
  wire  [`ROB_SIZE-1     :0]             ROB_wen_o;
  wire  [`RF_SIZE_LOG*`ROB_SIZE-1  :0]   ROB_rd_w;
  wire  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_rd_data_w;
  wire  [`ROB_SIZE-1     :0]             ROB_mem_valid_o;
  wire  [`ROB_SIZE-1     :0]             ROB_mem_rdwt_o;
  wire  [`MEMD_SIZE_LOG*`ROB_SIZE-1:0]   ROB_mem_addr_w;
  wire  [`REG_LEN*`ROB_SIZE-1      :0]   ROB_mem_data_w;
  wire  [`ROB_SIZE-1     :0]             ROB_is_br_o;
  wire  [`ROB_SIZE-1     :0]             ROB_predicted_taken_o;
  wire  [`ROB_SIZE-1     :0]             ROB_taken_o;
  wire  [`MEMI_SIZE_LOG*`ROB_SIZE-1:0]   ROB_next_pc_w;
  wire  [`ROB_SIZE-1     :0]             ROB_STORE_stall_o;

  
  wire [`ROB_SIZE_LOG-1  :0] ROB_head_o; 
  wire [`ROB_SIZE_LOG-1  :0] ROB_tail_o;


  // Instruction Memory wire - initial assumptions
  wire [`INST_LEN*`MEMI_SIZE-1:0] array_w;
  
  // Init State
  wire [`MEMI_SIZE_LOG-1:0]           F_pc_o;
  wire [`INST_SIZE_LOG-1:0]           F_opcode_o;
  wire                                C_valid_o; 

  // Directive Signals
  wire                                br_hist_o; 
  wire                                C_squash_o;

  // Rename table
  wire  [`RF_SIZE-1     :0]          renameTB_valid_o;
  wire  [`ROB_SIZE_LOG*`RF_SIZE-1:0] renameTB_ROBlink_w;

  // memd 

  wire [`REG_LEN*`MEMD_SIZE-1:0] memd_w;


  // Register file out for init state
  wire [`REG_LEN*`RF_SIZE-1:0]        rf_array_w;
// );

/* ---------------------------------
|   IO Management & Array Wrapping  |
 ----------------------------------*/

  // Copy to un-wrapped arrays & vectors
  assign C_mem_valid_o              = C_mem_valid;
  assign C_mem_rdwt_o               = C_mem_rdwt;
  assign C_mem_addr_o               = C_mem_addr;
  assign C_taken_o                  = C_taken;
  // assign ld_addr_o                  = ld_addr;
  assign C_is_br_o                  = C_is_br;
  assign C_next_pc_o                = C_next_pc;

  assign ROB_tail_o                 = ROB_tail;
  assign ROB_head_o                 = ROB_head;
  assign ROB_state_w                = ROB_state_packed;
  assign ROB_rd_data_w              = ROB_rd_data_packed;

  assign F_pc_o           = F_pc;
  assign F_opcode_o       = F_opcode;

  assign C_valid_o        = C_valid;
  assign br_hist_o        = br_hist;
  assign C_squash_o       = C_squash;

  assign renameTB_valid_o = renameTB_valid;

  assign renameTB_ROBlink_w = renameTB_ROBlink_packed;

  assign memd_w = memd_packed;

// `endif
/* -----------------------
|   Signals Declaration  |
 ------------------------*/
  integer i;

    /* -----------------
    |   Commit Signals  |
    --------------------*/

  wire                      C_valid;
  wire                      C_mem_valid;
  wire                      C_mem_rdwt;
  wire [`MEMD_SIZE_LOG-1:0] C_mem_addr;
  wire [`REG_LEN-1      :0] C_mem_data;
  wire                      C_is_br;
  wire                      C_taken;
  wire                      C_squash;
  wire [`MEMI_SIZE_LOG-1:0] C_next_pc;
  wire                      C_wen;
  wire [`RF_SIZE_LOG-1  :0] C_rd;
  wire [`REG_LEN-1      :0] C_rd_data;


    /* -----------------
    |   Decode Signals  |
    --------------------*/

  // STEP: Decode
  wire [`INST_SIZE_LOG-1:0] F_opcode;
  wire                      F_rs1_used;
  wire [`REG_LEN-1      :0] F_rs1_imm;
  wire [`RF_SIZE_LOG-1  :0] F_rs1;
  wire [`MEMI_SIZE_LOG-1:0] F_rs1_br_offset;
  wire                      F_rs2_used;
  wire [`RF_SIZE_LOG-1  :0] F_rs2;
  wire                      F_wen;
  wire [`RF_SIZE_LOG-1:0]   F_rd;
  wire                      F_rd_data_use_execute;

  wire F_mem_valid;
  wire F_mem_rdwt;
  wire F_is_br;

// `ifdef USE_DEFENSE_STT
//   wire F_IsAccessInstr;
//   wire F_IsTxInstr;
// `endif

    /*---------------
    |  Rename Table  |
    ----------------*/

  // Fetch Rename Table Signals
  wire                F_rs1_stall;
  wire [`REG_LEN-1:0] F_rs1_data;
  wire                F_rs2_stall;
  wire [`REG_LEN-1:0] F_rs2_data;

  // Rename Table Signals
  reg  [`RF_SIZE-1     :0] renameTB_valid;
  wire  [`ROB_SIZE_LOG-1:0] renameTB_ROBlink [`RF_SIZE-1:0];

  // Packed Array
  wire [`ROB_SIZE_LOG*`RF_SIZE-1   :0] renameTB_ROBlink_packed;



    /*---------------
    |       ROB      |
    ----------------*/
    // ROB wire signals
    wire [`REG_LEN-1      :0]  ROB_rd_data_wire;
    wire [`MEMD_SIZE_LOG-1:0]  ROB_mem_addr_wire;
    wire [`REG_LEN-1      :0]  ROB_mem_data_wire;
    wire                       ROB_taken_wire;
    wire [`MEMI_SIZE_LOG-1:0]  ROB_next_pc_wire;
    wire [`ROB_SIZE_LOG-1 :0]  ROB_head;
    wire [`ROB_SIZE_LOG-1 :0]  ROB_tail;
    wire [`ROB_SIZE-1     :0]  ROB_exe_this_cycle;
    wire                       ROB_full;
    wire                       ROB_empty;

    // ROB Input to ALU
    wire [`MEMI_SIZE_LOG-1:0] ROB_pc_wire;
    wire [`INST_SIZE_LOG-1:0] ROB_op_wire;
    wire [`REG_LEN-1      :0] ROB_rs1_imm_wire;
    wire [`REG_LEN-1      :0] ROB_rs1_data_wire;
    wire [`MEMI_SIZE_LOG-1:0] ROB_rs1_br_offset_wire;
    wire [`REG_LEN-1      :0] ROB_rs2_data_wire;
    wire                      ROB_rd_data_use_execute_wire;
    wire                      ROB_is_br_wire;

    // Packed Array
    wire [`ROB_STATE_LEN*`ROB_SIZE-1 :0] ROB_state_packed;
    wire [`REG_LEN*`ROB_SIZE-1       :0] ROB_rd_data_packed;
    

    // Unpacked Array
  wire [`ROB_STATE_LEN-1:0] ROB_state [`ROB_SIZE-1:0];
  wire [`REG_LEN-1      :0] ROB_rd_data [`ROB_SIZE-1:0];

    /*-------------
    |     MEMD    |
    ---------------*/

  // Packed Array
  wire [`REG_LEN*`MEMD_SIZE-1:0] memd_packed;

  // Unpacked Array
  wire [`REG_LEN-1:0] memd [`MEMD_SIZE-1:0];



/* -----------------------
|   Processor Operations  |
 -------------------------*/

    /*----------
    |   FETCH   |
    -----------*/

  // STEP: PC
  reg  [`MEMI_SIZE_LOG-1:0] F_pc;
  wire [`MEMI_SIZE_LOG-1:0] F_next_pc;
  always @(posedge clk) begin
    if (rst) F_pc <= 0;
    else     F_pc <= F_next_pc;
  end

  // STEP: Fetch
  wire [`INST_LEN-1:0] F_inst;
  memi memi_instance(
    .clk(clk), .rst(rst),
    .req_addr(F_pc), .resp_data(F_inst)
    // `ifdef FORMAL
    // ,
    // .array_w(array_w)
    // `endif
  ); 



    /*------------
    |   DECODE   |
    -------------*/

  decode decode_instance(
    .inst(F_inst),
    .opcode(F_opcode), .rs1_used(F_rs1_used), .rs1_imm(F_rs1_imm), .rs1(F_rs1),
    .rs1_br_offset(F_rs1_br_offset), .rs2_used(F_rs2_used), .rs2(F_rs2),
    .wen(F_wen), .rd(F_rd), .rd_data_use_execute(F_rd_data_use_execute),
    .mem_valid(F_mem_valid), .mem_rdwt(F_mem_rdwt),
    .is_br(F_is_br)
  );

    /*------------------
    |   Register File   |
    -------------------*/


  // STEP: rf Read Write
  wire [`REG_LEN-1:0] F_rs1_data_rf;
  wire [`REG_LEN-1:0] F_rs2_data_rf;
  rf rf_instance(
    .clk(clk), .rst(rst),
    .rs1(F_rs1), .rs1_data(F_rs1_data_rf),
    .rs2(F_rs2), .rs2_data(F_rs2_data_rf),
    .wen(C_valid && C_wen), .rd(C_rd), .rd_data(C_rd_data)
    
`ifdef FORMAL
    ,.array_w(rf_array_w)
`endif

  );


  // STEP: PC Prediction
  reg  br_hist;
  wire F_taken;

  always @(posedge clk) begin
    if (rst)                     br_hist <= 1'b0;
    else if (C_valid && C_is_br) br_hist <= C_taken;
  end

  assign F_taken =
    (`BR_PREDICT==`BR_PREDICT_NOT_TAKEN)?
      1'b0 :
    (`BR_PREDICT==`BR_PREDICT_BHB)?
      br_hist :
    (`BR_PREDICT==`BR_PREDICT_FORWARD_DATA_THEN_NOT_TAKEN)?
      (F_rs2_stall? 1'b0 : F_rs2_data==0) :
    // (`BR_PREDICT==`BR_PREDICT_FORWARD_DATA_THEN_BHB)?
      (F_rs2_stall? br_hist : F_rs2_data==0);

  assign F_next_pc = (C_valid && C_squash)? C_next_pc :
                     ROB_full?              F_pc :
                     (F_is_br && F_taken)?  F_pc+F_rs1_br_offset :
                                            F_pc+1;


    /*---------------
    |  Rename Table  |
    ----------------*/

  renameTable renameTable_instance(
    .clk(clk),
    .rst(rst),

    .C_squash(C_squash),
    .C_valid(C_valid), 
    .C_wen(C_wen),
    .C_rd(C_rd), 

    // ROB
    .ROB_full(ROB_full), 
    .ROB_tail(ROB_tail),
    .ROB_head(ROB_head),

    // Fetch
    .F_wen(F_wen), 
    .F_rd(F_rd),

    // Rename Table
    .renameTB_valid(renameTB_valid),
    .renameTB_ROBlink_w(renameTB_ROBlink_packed)

  );


    /*-------------------------------------------------
    |   RenameTable  -  Un-packed Array Work Around    |
    ---------------------------------------------------*/
    genvar RenameTable_idx;

    generate
    for (RenameTable_idx=0; RenameTable_idx < `RF_SIZE; RenameTable_idx++) begin
      assign renameTB_ROBlink[RenameTable_idx]  = renameTB_ROBlink_packed[RenameTable_idx*`ROB_SIZE_LOG +: `ROB_SIZE_LOG];
    end
    endgenerate  



  // STEP.: use renameTB to read data from either reg or ROB or stall
`ifdef USE_DEFENSE_PARTIAL_STT
//   assign F_rs1_stall =
//     F_rs1_used
//     && renameTB_valid[F_rs1]
//     && (!(ROB_state[renameTB_ROBlink[F_rs1]]==`FINISHED)
//         || ROB_op[renameTB_ROBlink[F_rs1]]==`INST_OP_LD
// `ifdef PARTIAL_STT_USE_SPEC
//            && ROB_isSpec[renameTB_ROBlink[F_rs1]]
// `endif
//            && !(renameTB_ROBlink[F_rs1]==ROB_head));
//   assign F_rs2_stall =
//     F_rs2_used
//     && renameTB_valid[F_rs2]
//     && (!(ROB_state[renameTB_ROBlink[F_rs2]]==`FINISHED)
//         || ROB_op[renameTB_ROBlink[F_rs2]]==`INST_OP_LD
// `ifdef PARTIAL_STT_USE_SPEC
//            && ROB_isSpec[renameTB_ROBlink[F_rs2]]
// `endif
//            && !(renameTB_ROBlink[F_rs2]==ROB_head));

`else
  assign F_rs1_stall =
    F_rs1_used && renameTB_valid[F_rs1] &&
    !(ROB_state[renameTB_ROBlink[F_rs1]]==`FINISHED);   
  assign F_rs2_stall =
    F_rs2_used && renameTB_valid[F_rs2] &&
    !(ROB_state[renameTB_ROBlink[F_rs2]]==`FINISHED);

`endif

  assign F_rs1_data = {`REG_LEN{F_rs1_used&&!F_rs1_stall}} & 
                      (renameTB_valid[F_rs1]?
                        ROB_rd_data[renameTB_ROBlink[F_rs1]]:
                        F_rs1_data_rf);
                        
  assign F_rs2_data = {`REG_LEN{F_rs2_used&&!F_rs2_stall}} & 
                      (renameTB_valid[F_rs2]?
                        ROB_rd_data[renameTB_ROBlink[F_rs2]]:
                        F_rs2_data_rf);



    /*---------------
    |       ROB      |
    ----------------*/

  rob rob_instance(
    .clk(clk),
    .rst(rst),

    .F_inst(F_inst),

    // Fetched Signals
    .F_pc(F_pc),
    .F_opcode(F_opcode),
    .F_rs1(F_rs1),
    .F_rs1_stall(F_rs1_stall), 
    .F_rs1_imm(F_rs1_imm),
    .F_rs1_data(F_rs1_data),
    .F_rs1_br_offset(F_rs1_br_offset),
    .renameTB_ROBlink_w(renameTB_ROBlink_packed),
    .F_rs2(F_rs2), 
    .F_rs2_stall(F_rs2_stall),
    .F_rs2_data(F_rs2_data),
    .F_rd_data_use_execute(F_rd_data_use_execute),
    .F_wen(F_wen),
    .F_rd(F_rd),
    .F_mem_valid(F_mem_valid),
    .F_mem_rdwt(F_mem_rdwt), 
    .F_is_br(F_is_br), 
    .F_taken(F_taken), 

    // ROB wire signals
    .ROB_rd_data_wire(ROB_rd_data_wire),
    .ROB_mem_addr_wire(ROB_mem_addr_wire),
    .ROB_mem_data_wire(ROB_mem_data_wire),
    .ROB_taken_wire(ROB_taken_wire),
    .ROB_next_pc_wire(ROB_next_pc_wire),

    // ROB Input to ALU
    .ROB_pc_wire(ROB_pc_wire),
    .ROB_op_wire(ROB_op_wire),
    .ROB_rs1_imm_wire(ROB_rs1_imm_wire),
    .ROB_rs1_data_wire(ROB_rs1_data_wire),
    .ROB_rs1_br_offset_wire(ROB_rs1_br_offset_wire),
    .ROB_rs2_data_wire(ROB_rs2_data_wire),
    .ROB_rd_data_use_execute_wire(ROB_rd_data_use_execute_wire),
    .ROB_is_br_wire(ROB_is_br_wire),

    .ROB_exe_this_cycle(ROB_exe_this_cycle),

    // ROB output signals
    .ROB_state_w(ROB_state_packed),
    .ROB_rd_data_w(ROB_rd_data_packed),
    .ROB_head(ROB_head),
    .ROB_tail(ROB_tail),

    .ROB_full(ROB_full),
    .ROB_empty(ROB_empty),

    // Commit Signals
    .C_valid(C_valid),
    .C_mem_valid(C_mem_valid),
    .C_mem_rdwt(C_mem_rdwt),
    .C_mem_addr(C_mem_addr),
    .C_mem_data(C_mem_data),
    .C_is_br(C_is_br),
    .C_taken(C_taken),
    .C_squash(C_squash),
    .C_next_pc(C_next_pc),
    .C_wen(C_wen),
    .C_rd(C_rd),
    .C_rd_data(C_rd_data)
  // .ld_addr(ld_addr)
 `ifdef FORMAL
 ,
  .ld_addr(ld_addr),
  .ROB_op_w(ROB_op_w), 
  .ROB_pc_w(ROB_pc_w),
  .ROB_rs1_w(ROB_rs1_w),
  .ROB_rs1_imm_w(ROB_rs1_imm_w),
  .ROB_rs1_data_w(ROB_rs1_data_w),
  .ROB_rs1_ROBlink_w(ROB_rs1_ROBlink_w),
  .ROB_rs1_br_offset_w(ROB_rs1_br_offset_w),
  .ROB_rs2_w(ROB_rs2_w),
  .ROB_rs2_data_w(ROB_rs2_data_w),
  .ROB_rs2_ROBlink_w(ROB_rs2_ROBlink_w),
  .ROB_rd_w(ROB_rd_w),
  .ROB_mem_addr_w(ROB_mem_addr_w),
  .ROB_mem_data_w(ROB_mem_data_w),
  .ROB_next_pc_w(ROB_next_pc_w), 

  .ROB_rs1_stall_o(ROB_rs1_stall_o),
  .ROB_rs2_stall_o(ROB_rs2_stall_o),
  .ROB_rd_data_use_execute_o(ROB_rd_data_use_execute_o),
  .ROB_wen_o(ROB_wen_o),
  .ROB_mem_valid_o(ROB_mem_valid_o),
  .ROB_mem_rdwt_o(ROB_mem_rdwt_o),
  .ROB_is_br_o(ROB_is_br_o),
  .ROB_predicted_taken_o(ROB_predicted_taken_o),
  .ROB_taken_o(ROB_taken_o),
  .ROB_STORE_stall_o(ROB_STORE_stall_o)


 `endif  
  );

    /*-------------------------------------------
    |   ROB  -  Un-packed Array Work Around      |
    --------------------------------------------*/
    genvar ROB_idx;

    generate
    for (ROB_idx=0; ROB_idx < `ROB_SIZE; ROB_idx++) begin
      assign ROB_state[ROB_idx]  = ROB_state_packed[ROB_idx*`ROB_STATE_LEN +: `ROB_STATE_LEN];
      assign ROB_rd_data[ROB_idx] = ROB_rd_data_packed[ROB_idx*`REG_LEN +: `REG_LEN];
    end
    endgenerate  

    /*--------------
    |    EXECUTE    |
    ---------------*/


  wire [`MEMD_SIZE_LOG-1:0] mem_read_addr;
  assign mem_read_addr = ROB_op_wire == `INST_OP_LD ? ROB_rs1_data_wire[`MEMD_SIZE_LOG-1:0] : 0;

  execute execute_instance(
    .pc(ROB_pc_wire),
    .op(ROB_op_wire),

    .rs1_imm(ROB_rs1_imm_wire),
    .rs1_br_offset(ROB_rs1_br_offset_wire),
    .rs1_data(ROB_rs1_data_wire),
    .rs2_data(ROB_rs2_data_wire),
    .rd_data_memory(memd[mem_read_addr]),
    .rd_data_use_execute(ROB_rd_data_use_execute_wire),

    .rd_data(ROB_rd_data_wire),
    
    // .memd(memd),
    .mem_addr(ROB_mem_addr_wire),
    .mem_data(ROB_mem_data_wire),

    .is_br(ROB_is_br_wire),
    .taken(ROB_taken_wire),
    .next_pc(ROB_next_pc_wire)
  );


  // Leakage: observation of memory trace
  `ifdef FORMAL
    wire [`MEMD_SIZE_LOG-1:0] ld_addr;

    `ifdef PARTIAL_DOM_USE_MISS_ONLY
      assign ld_addr = cached_addr;
    `endif
  `endif 



    /*-------------
    |     MEMD    |
    ---------------*/

    memd memd_instance(
      .clk(clk),
      .rst(rst),

      .C_valid(C_valid),
      .C_mem_valid(C_mem_valid),
      .C_mem_rdwt(C_mem_rdwt),
      .C_mem_addr(C_mem_addr),
      .C_mem_data(C_mem_data),

      .memd_w(memd_packed)
    );

    /*-------------------------------------------
    |   MEMD  -  Un-packed Array Work Around    |
    --------------------------------------------*/
    genvar MEMD_idx;

    generate
    for (MEMD_idx=0; MEMD_idx < `MEMD_SIZE; MEMD_idx++) begin
      assign memd[MEMD_idx]  = memd_packed[MEMD_idx*`REG_LEN +: `REG_LEN];
    end
    endgenerate  



endmodule

