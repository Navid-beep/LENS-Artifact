

OUT_OF_ORDER_PIPELINE_DRAIN_BEGIN

reg gate_empty_pipeline;
reg gold_empty_pipeline;
reg [ROB_TAIL_SIZE-1: 0] GATE_ROB_TAIL_rec;
reg [ROB_TAIL_SIZE-1: 0] GOLD_ROB_TAIL_rec;




wire trg_equiv = ATTACKER_OBSERVATIONS;


reg state_trg_equiv = 1;
always @ (posedge in_CLOCK) begin
        state_trg_equiv <= state_trg_equiv && trg_equiv;
end

always @(posedge in_CLOCK) begin

    if (in_RESET) begin
        gate_empty_pipeline <= 0;
        gold_empty_pipeline <= 0;
    end else begin
        if (!state_trg_equiv && ( GATE_COMMIT_SIGNAL_CONDITION GATE_COMMIT_ROLLBACK_CONDITION )) begin 
            gate_empty_pipeline <= 1;
        end

        if (!state_trg_equiv && ( GOLD_COMMIT_SIGNAL_CONDITION GOLD_COMMIT_ROLLBACK_CONDITION )) begin 
            gold_empty_pipeline <= 1;
        end
    end
end

assert  (!(!state_trg_equiv && gate_empty_pipeline && gold_empty_pipeline && !gate_SYNCHRONIZATION_signal && !gold_SYNCHRONIZATION_signal));


OUT_OF_ORDER_PIPELINE_DRAIN_END



DIRECT_CONTRACT_OUT_OF_ORDER_PROC_BEGIN

reg ROB_record = 0;

always @(posedge in_CLOCK) begin

    if (in_RESET) begin
        GATE_ROB_TAIL_rec <= 0;
        GOLD_ROB_TAIL_rec <= 0;
        ROB_record <= 0;
    end else if (!state_trg_equiv && ROB_record == 0) begin
        GATE_ROB_TAIL_rec <= GATE_ROB_RECORDING ;
        GOLD_ROB_TAIL_rec <= GOLD_ROB_RECORDING ;
        ROB_record <= 1;
    end

end

DIRECT_CONTRACT_OUT_OF_ORDER_PROC_END


IN_ORDER_PIPELINE_DRAIN_BEGIN

    wire trg_equiv = ATTACKER_OBSERVATIONS;

    reg [LA_UPPER_BOUND: 0]  bound = LOOKAHEAD;

    always @ (posedge in_CLOCK) begin
        if (bound > 0 && !state_trg_equiv) begin
            bound <= bound - 1;
        end
    end

    // update the states for verification
    reg state_trg_equiv = 1;
    always @ (posedge in_CLOCK) begin
            state_trg_equiv <= state_trg_equiv && trg_equiv;
    end

    wire fin_state_trg_equiv = ( bound > 0 || gate_SYNCHRONIZATION_signal || gold_SYNCHRONIZATION_signal) ||  state_trg_equiv ;

    assert  (fin_state_trg_equiv);

IN_ORDER_PIPELINE_DRAIN_END