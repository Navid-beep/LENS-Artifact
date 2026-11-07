	
	
	
	reg init = 0;

	always @ (posedge in_CLOCK) begin
		if (init == 0) begin
			init <= 1;
		end
	end

    wire init_wire = 	REG_INIT_PLACEHOLDER 

						OUT_OF_ORDER_PIPELINE_DRAIN_BEGIN
						&& gate_empty_pipeline == gold_empty_pipeline && gate_empty_pipeline == 0
						&& GATE_ROB_TAIL_rec == GOLD_ROB_TAIL_rec && GATE_ROB_TAIL_rec == 0
						OUT_OF_ORDER_PIPELINE_DRAIN_END

						&& gate_SYNCHRONIZATION_signal == gold_SYNCHRONIZATION_signal && gate_SYNCHRONIZATION_signal == 0

						CONTRACT_SPECIFICATION_INDIRECT_BEGIN
						&& commit_deviation == 0 && addr_deviation == 0
						CONTRACT_SPECIFICATION_INDIRECT_END
						;

		
    wire initialize = (init != 0) || (init_wire) ;

    assume (initialize);

