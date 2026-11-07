

BASE_CASE_TEMPLATE_BEGIN

	reg  [LOG_K : 0 ] k = LOOKAHEAD;

	STATE_TRG_DEF

    always @(posedge in_CLOCK) begin
		if (k > 0) begin
			k <= k - 1;
		end
	end

	always @(posedge in_CLOCK) begin
		if (in_RST) begin
			state_trg_equiv <= 1;
		end else begin
			if (k > 0) begin
				state_trg_equiv <= state_trg_equiv && OUT_OF_ORDER trg_equiv;
			end
		end
	end

BASE_CASE_TEMPLATE_END



INDUCTIVE_CASE_TEMPLATE_BEGIN

    reg  [LOG_K +1: 0 ] k = LOOKAHEAD + 1;
    always @(posedge in_CLOCK) begin
        if (k > 0) begin
            k <= k - 1;
        end
    end

	reg init_state_trg_equiv = 1;


	STATE_TRG_DEF

	always @(posedge in_CLOCK) begin
		if (in_RST) begin
			state_trg_equiv <= 1;
			init_state_trg_equiv <= 1;
		end else begin
			if (k > 0) begin
				state_trg_equiv <= state_trg_equiv && OUT_OF_ORDER trg_equiv;
			end
			if (k > 1) begin
				init_state_trg_equiv <= init_state_trg_equiv && OUT_OF_ORDER trg_equiv;
			end
		end
	end

    assume (init_state_trg_equiv);

INDUCTIVE_CASE_TEMPLATE_END
