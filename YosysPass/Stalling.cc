/*
 * Stalling.cc -- Yosys plugin
 *
 * Pass "stalling": for every instance of <module> found in the design
 * (i.e. the gold/gate copies created by 'miter -equiv'), gate its clock
 * with that copy's own stuttering signal <inst>_<stall_signal>. If that
 * net does not exist yet in the parent (miter) module it is created as an
 * internal, undriven 1-bit wire (never as a port):
 *
 *     gold (.clk(in_clk))  -->  gold (.clk(gold_stuttering_signal ? 1'h0 : in_clk))
 *     gate (.clk(in_clk))  -->  gate (.clk(gate_stuttering_signal ? 1'h0 : in_clk))
 *
 * No ports are added to the miter.
 *
 * Build:  yosys-config --build Stalling.so Stalling.cc
 * Use:    plugin -i Stalling.so
 *         stalling cpu_ooo clk stuttering_signal
 */

#include "kernel/yosys.h"

USING_YOSYS_NAMESPACE
PRIVATE_NAMESPACE_BEGIN

struct StallingPass : public Pass {
	StallingPass() : Pass("stalling", "gate the clock of miter instances with their stuttering signal") {}

	void help() override
	{
		//   |---v---|---v---|---v---|---v---|---v---|---v---|---v---|---v---|---v---|---v---|
		log("\n");
		log("    stalling <module> <clk_port> <stall_signal>\n");
		log("\n");
		log("For every instance of <module> (e.g. the 'gold' and 'gate' cells created by\n");
		log("'miter -equiv'), rewrite its clock connection as:\n");
		log("\n");
		log("    .<clk_port>(X)  -->  .<clk_port>(<inst>_<stall_signal> ? 1'h0 : X)\n");
		log("\n");
		log("where <inst> is the instance name. If the net <inst>_<stall_signal> does not\n");
		log("exist in the parent module it is created as an internal, undriven 1-bit\n");
		log("wire. It is never added to the module's ports.\n");
		log("\n");
		log("Example:\n");
		log("    stalling cpu_ooo clk stuttering_signal\n");
		log("\n");
	}

	static RTLIL::IdString fresh_name(RTLIL::Module *module, const std::string &base)
	{
		RTLIL::IdString id = RTLIL::escape_id(base);
		for (int i = 1; module->wire(id) != nullptr || module->cell(id) != nullptr; i++)
			id = RTLIL::escape_id(stringf("%s_%d", base.c_str(), i));
		return id;
	}

	void execute(std::vector<std::string> args, RTLIL::Design *design) override
	{
		log_header(design, "Executing STALLING pass (clock gating with stuttering signal).\n");

		if (args.size() != 4)
			log_cmd_error("Usage: stalling <module> <clk_port> <stall_signal>\n");

		RTLIL::IdString type_id = RTLIL::escape_id(args[1]);
		RTLIL::IdString clk_id = RTLIL::escape_id(args[2]);
		std::string stall_name = args[3];

		if (design->module(type_id) == nullptr)
			log_cmd_error("Module %s not found in design.\n", log_id(type_id));

		int count = 0;
		for (auto module : design->modules()) {
			// snapshot the cell list: we add $mux cells while iterating
			std::vector<RTLIL::Cell *> targets;
			for (auto cell : module->cells())
				if (cell->type == type_id)
					targets.push_back(cell);

			for (auto cell : targets) {
				std::string inst = RTLIL::unescape_id(cell->name);

				if (!cell->hasPort(clk_id))
					log_cmd_error("Cell %s.%s has no port %s.\n",
						      log_id(module), log_id(cell), log_id(clk_id));

				RTLIL::SigSpec clk = cell->getPort(clk_id);
				if (GetSize(clk) != 1)
					log_cmd_error("Port %s on cell %s.%s has width %d, expected 1.\n",
						      log_id(clk_id), log_id(module), log_id(cell), GetSize(clk));

				RTLIL::IdString stall_id = RTLIL::escape_id(inst + "_" + stall_name);
				RTLIL::Wire *stall = module->wire(stall_id);
				if (stall == nullptr) {
					// internal net only: NOT a port of the miter, left undriven
					stall = module->addWire(stall_id, 1);
					log("  Created internal (undriven) net %s in %s.\n",
					    log_id(stall_id), log_id(module));
				}
				if (stall->width != 1)
					log_cmd_error("Stall signal %s in module %s has width %d, expected 1.\n",
						      log_id(stall_id), log_id(module), stall->width);

				// gated = stall ? 1'b0 : clk      ($mux: Y = S ? B : A)
				RTLIL::Wire *gated = module->addWire(fresh_name(module, inst + "_stalled_" + args[2]), 1);
				module->addMux(fresh_name(module, inst + "_stall_mux"),
					       clk, RTLIL::SigSpec(RTLIL::State::S0), RTLIL::SigSpec(stall), gated);
				cell->setPort(clk_id, gated);

				log("  %s.%s.%s: %s  ->  %s ? 1'h0 : %s\n",
				    log_id(module), log_id(cell), log_id(clk_id), log_signal(clk),
				    log_id(stall_id), log_signal(clk));
				count++;
			}
		}

		if (count == 0)
			log_warning("No instances of %s found; nothing changed.\n", log_id(type_id));
		else
			log("Gated the clock of %d instance(s) of %s.\n", count, log_id(type_id));
	}
} StallingPass;

PRIVATE_NAMESPACE_END
