

// STEP: Arch States
// `define REG_LEN       4
// `define REG_LEN_LOG   2
// `define RF_SIZE       4
// `define RF_SIZE_LOG   2
// `define MEMI_SIZE     2
// `define MEMI_SIZE_LOG 1
// `define MEMD_SIZE     4
// `define MEMD_SIZE_LOG 2

`define REG_LEN       4
`define REG_LEN_LOG   2
`define RF_SIZE       4
`define RF_SIZE_LOG   2
`define MEMI_SIZE     8
`define MEMI_SIZE_LOG 3
`define MEMD_SIZE     4
`define MEMD_SIZE_LOG 2


// STEP: Inst
`define INST_SIZE     6
`define INST_SIZE_LOG 3
`define INST_OP_LI  0
`define INST_OP_ADD 1
`define INST_OP_MUL 2
`define INST_OP_LD  3
`define INST_OP_ST  4
`define INST_OP_BR  5
`define INST_LEN (`INST_SIZE_LOG + `REG_LEN + 2*`RF_SIZE_LOG)
`define OPCODE [`INST_LEN-1:`INST_LEN-`INST_SIZE_LOG]
`define RS1    [`INST_LEN-`INST_SIZE_LOG-1:`INST_LEN-`INST_SIZE_LOG-`REG_LEN]
`define RS2    [2*`RF_SIZE_LOG-1:`RF_SIZE_LOG]
`define RD     [`RF_SIZE_LOG-1:0]

// {OPCODE RS1 RS2 RD}
// LI   IMM          -           RD
// ADD  RS1 (op)     RS2 (op)    RD
// MUL  RS1 (op)     RS2 (op)    RD
// LD   RS1 (addr)   -           RD (dest reg)
// ST   RS1 (addr)   RS2 (data)
// BR   IMM (Offset) RS2 (cond)  - (branch if rs2 == 0)


// STEP: Micro-architecture states
`define ROB_SIZE 4
`define ROB_SIZE_LOG 2
`define ROB_STATE_LEN 3
`define IDLE        0
`define STALLED     1
`define READY       2
`define EXECUTING_1 3
`define EXECUTING_0 4
`define FINISHED    5

`define USE_CACHE




// STEP: Interference

// NOTE: By not using F_rs2_data to decide branch direction,
//       the speculative accessed data in F_rs2_data will not affect pc
`define BR_PREDICT_NOT_TAKEN 0
`define BR_PREDICT_BHB 1
`define BR_PREDICT_FORWARD_DATA_THEN_NOT_TAKEN 2
`define BR_PREDICT_FORWARD_DATA_THEN_BHB 3
`define BR_PREDICT `BR_PREDICT_NOT_TAKEN


// STEP: Observation Model
// NOTE: equivalent to commit time,
//       since we assume the commited address to be the same in ISA
`define OBSV_COMITTED_ADDR 0
`define OBSV_EVERY_ADDR 1
`define OBSV `OBSV_EVERY_ADDR
`define OBSV_LD_DATA 1


// STEP: Secret Address
`define SECRET_ADDR 1


// STEP: Init state
`define INIT_VALUE_ZERO 0
`define INIT_VALUE_CUSTOMIZED 1
`define INIT_VALUE `INIT_VALUE_CUSTOMIZED

// STEP: Immediate Stall
`define IMM_STALL

// STEP: Control whether OOO forwards info to ISA
`define NO_FORWARD 0
