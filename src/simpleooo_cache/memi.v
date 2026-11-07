

`include "param.v"

module memi(
  input clk,
  input rst,

  input  [`MEMI_SIZE_LOG-1:0] req_addr,
  output [`INST_LEN-1     :0] resp_data
);

  reg [`INST_LEN-1:0] array_mem [`MEMI_SIZE-1:0];

  // STEP Read
  assign resp_data = array_mem[req_addr];

  // Arbitrary program, used only when reset is applied (undriven -> free value)
  wire [`INST_LEN-1:0] array_symb [`MEMI_SIZE-1:0];

  always @(posedge clk) begin
    for (int i = 0; i < `MEMI_SIZE; i = i + 1) begin
      if (rst)
        array_mem[i] <= array_symb[i];   // load an arbitrary program once, at reset
      else
        array_mem[i] <= array_mem[i];    // no-op self-write: the program stays fixed
    end
  end

endmodule