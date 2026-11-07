
CONTRACT_TEMPLATE_BEGIN
    if(CONTRACT_CONDITION  CONTRACT_EQUIVALENCE ) begin
        invalid_program <= 1;
    end
CONTRACT_TEMPLATE_END



ROB_RECORDING_BEGIN
if (!(commit_deviation || addr_deviation )) begin 
    GATE_ROB_TAIL_rec <= GATE_ROB_RECORDING ;
    GOLD_ROB_TAIL_rec <= GOLD_ROB_RECORDING ;
end
ROB_RECORDING_END


CONTRACT_SPECIFICATION_BEGIN

/* ------ Signals Declaration ------*/

reg gate_SYNCHRONIZATION_signal;
reg gold_SYNCHRONIZATION_signal;
reg commit_deviation;
reg addr_deviation;
reg invalid_program;

/* ------ Contract Enforcement ------*/

always @(posedge in_CLOCK) begin 
    if (in_RESET ) begin 
        gate_SYNCHRONIZATION_signal <= 0;
        gold_SYNCHRONIZATION_signal <= 0;
        commit_deviation <= 0;
        invalid_program <= 0;
        addr_deviation <= 0;
        ROB_RECORDING_SIGNAL

    end else begin 
        if (!gold_SYNCHRONIZATION_signal && !gate_SYNCHRONIZATION_signal) begin 

            if (GATE_RETIREMENT_PREDICATE && GOLD_RETIREMENT_PREDICATE ) begin

                    CONTRACT_TEMPLATE_PLACEHOLDER

            end else if (!GATE_RETIREMENT_PREDICATE && GOLD_RETIREMENT_PREDICATE ) begin 

                        gold_SYNCHRONIZATION_signal <= 1;
                        commit_deviation <= 1;

                        ROB_RECORDING_PLACEHOLDER

            end else if (GATE_RETIREMENT_PREDICATE && !GOLD_RETIREMENT_PREDICATE ) begin 

                        gate_SYNCHRONIZATION_signal <= 1;
                        commit_deviation <= 1;
                        
                        ROB_RECORDING_PLACEHOLDER
            end

        end else if (gate_SYNCHRONIZATION_signal && !gold_SYNCHRONIZATION_signal ) begin 

            if (GOLD_RETIREMENT_PREDICATE ) begin 

                    gate_SYNCHRONIZATION_signal <= 0;

                    CONTRACT_TEMPLATE_PLACEHOLDER

            end

        end else if (!gate_SYNCHRONIZATION_signal && gold_SYNCHRONIZATION_signal ) begin 

            if (GATE_RETIREMENT_PREDICATE ) begin 

                    gold_SYNCHRONIZATION_signal <= 0;

                    CONTRACT_TEMPLATE_PLACEHOLDER

            end

        end

        ADDRESS_DEVIATION_DETECTION

    end
end

assume  (invalid_program == 0 );

CONTRACT_SPECIFICATION_END
