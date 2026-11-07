// #include "kernel/register.h"
// #include "kernel/rtlil.h"
// #include "kernel/log.h"
// #include "kernel/yosys.h"
// #include "kernel/sigtools.h"

// USING_YOSYS_NAMESPACE
// PRIVATE_NAMESPACE_BEGIN
// using namespace std;


// struct AddModulePass : public Pass {
//     AddModulePass() : Pass("stuttering", "stuttering the module based on the stuttering signal") { }
// 	void execute(std::vector<std::string> args, RTLIL::Design *design) override
// 	{
//         log_header(design, "Executing stuttering pass (stuttering the module based on the stuttering signal).\n");
//         if (args.size() != 3){
//             log("command argument error");
//             exit(0);
//         }
//         RTLIL::IdString main = RTLIL::escape_id(args[1]);
// 	    RTLIL::IdString stuttering_signal = RTLIL::escape_id(args[2]);
//         if (design->module(main) == nullptr)
// 		    log_cmd_error("Can't find main module %s!\n", main.c_str());

//         RTLIL::Module *main_module = design->module(main);


//         for (auto &cell : main_module->cells_) {
//             //stuttering registers
//             if (RTLIL::builtin_ff_cell_types().count(cell.second->type)){
//                 log("---------------------------------stuttering register cells------------------------------------------\n");
//                 RTLIL::SigSpec APort = cell.second->getPort(ID::D);
//                 RTLIL::SigSpec BPort = cell.second->getPort(ID::Q);
//                 int width = (cell.second->parameters["\\WIDTH"]).as_int();
//                 log_cell(cell.second);  
                
//                 std::string intermedia_signal_name = RTLIL::escape_id(RTLIL::id2cstr((cell.second->name)) + std::string("_intermedia_signal"));
//                 std::string stuttering_cell_name = RTLIL::escape_id(RTLIL::id2cstr((cell.second->name)) + std::string("_stuttering_cell"));
//                 cout << intermedia_signal_name << "\n";
//                 cout << stuttering_cell_name << "\n";
//                 // intermedia_signal_wire
//                 RTLIL::Wire *intermedia_signal = main_module->addWire(intermedia_signal_name, width);

//                 // update the register cell with the intermedia signal
//                 cell.second->setPort(ID::D, intermedia_signal);
//                 log_cell(cell.second);

//                 // generate an conditional assignment base on the stuttering signal
//                 RTLIL::Cell *stuttering_assignment = main_module->addCell(stuttering_cell_name, ID($mux));
//                 log("---------------------------------Width------------------------------------------\n");
//                 stuttering_assignment->parameters["\\WIDTH"] = width;
//                 log("---------------------------------Y------------------------------------------\n");
//                 stuttering_assignment->setPort(ID::Y, intermedia_signal);
//                 log("---------------------------------S------------------------------------------\n");
//                 stuttering_assignment->setPort(ID::S, main_module->wire(stuttering_signal));
//                 log("---------------------------------A------------------------------------------\n");
//                 stuttering_assignment->setPort(ID::A, APort);
//                 log("---------------------------------B------------------------------------------\n"); 
//                 stuttering_assignment->setPort(ID::B, BPort);

//                 log_cell(stuttering_assignment);              
                
//             }      
//         }
// 	}
// } AddModulePass;

// PRIVATE_NAMESPACE_END



// stuttering.cc -- Yosys pass: freeze ALL state of a module while a stuttering signal is high.
//
//   stuttering <module> <stuttering_signal> [-nomem]
//
// Run after `proc` and `flatten` (and optionally `memory_collect`), before the miter is built.
//
// What it does, for every state element of <module>:
//   * flip-flops / latches with a D input:   D' = stut ? Q : D           (hold)
//   * memory write ports (all kinds):        EN' = EN & {W{~stut}}       (no write while stuttering)
//   * clocked (synchronous) memory read ports: EN' = EN & ~stut          (read register holds)
//
// Fixes w.r.t. the original version:
//   1. Memories ($memwr/$memwr_v2/$mem/$mem_v2, unpacked or packed) were never gated, so register
//      files, ROB arrays, data memories, ... kept being written by a "frozen" copy.
//   2. Cells/wires were added while iterating over module->cells_ (hashlib dict) -> undefined
//      behaviour on rehash. We now snapshot the cell list first.
//   3. Fine-grained FF cells ($_DFF_P_, $_DFFE_PP_, ...) have no WIDTH parameter -> crash.
//      Width is now taken from the Q port.
//   4. FF types without a D port ($sr, $_SR_*) made getPort(ID::D) assert; they are now skipped
//      with a warning.
//   5. Missing / wrong-width stuttering signal was dereferenced as nullptr; now a clean error.
//   6. Hierarchical (un-flattened) designs were silently only partially instrumented; now an error.
//   7. The FF that drives the stuttering signal itself (if it lives in the module) is not held,
//      otherwise the stutter would latch forever.
//   8. Running the pass twice no longer adds a second mux layer (cells are tagged).
//   9. Argument errors use log_cmd_error instead of exit(0).

#include "kernel/yosys.h"
#include "kernel/sigtools.h"
#include "kernel/mem.h"

USING_YOSYS_NAMESPACE
PRIVATE_NAMESPACE_BEGIN

static const char *ATTR_DONE = "\\stuttering_done";

struct StutteringPass : public Pass {
	StutteringPass() : Pass("stuttering", "freeze all state of a module while a stuttering signal is high") { }

	void help() override
	{
		log("\n");
		log("    stuttering <module> <stuttering_signal> [-nomem]\n");
		log("\n");
		log("Makes every register, latch and memory of <module> hold its value in every\n");
		log("cycle in which the 1-bit wire <stuttering_signal> is high.\n");
		log("The module must be flattened and processes must be lowered (run proc first).\n");
		log("\n");
		log("    -nomem\n");
		log("        do not touch memories (old behaviour; NOT recommended)\n");
		log("\n");
	}

	void execute(std::vector<std::string> args, RTLIL::Design *design) override
	{
		log_header(design, "Executing STUTTERING pass.\n");

		bool do_mem = true;
		std::vector<std::string> pos;
		for (size_t i = 1; i < args.size(); i++) {
			if (args[i] == "-nomem") { do_mem = false; continue; }
			pos.push_back(args[i]);
		}
		if (pos.size() != 2)
			log_cmd_error("Usage: stuttering <module> <stuttering_signal> [-nomem]\n");

		RTLIL::IdString main = RTLIL::escape_id(pos[0]);
		RTLIL::IdString stut_name = RTLIL::escape_id(pos[1]);

		RTLIL::Module *module = design->module(main);
		if (module == nullptr)
			log_cmd_error("Can't find module %s!\n", log_id(main));
		if (!module->processes.empty())
			log_cmd_error("Module %s still has processes; run `proc` first.\n", log_id(module));

		RTLIL::Wire *stut_wire = module->wire(stut_name);
		if (stut_wire == nullptr)
			log_cmd_error("Can't find wire %s in module %s!\n", log_id(stut_name), log_id(module));
		if (stut_wire->width != 1)
			log_cmd_error("Stuttering signal %s must be 1 bit wide (is %d).\n", log_id(stut_name), stut_wire->width);

		// Snapshot cells before modifying the module.
		std::vector<RTLIL::Cell*> cells;
		for (auto cell : module->cells())
			cells.push_back(cell);

		for (auto cell : cells)
			if (design->module(cell->type) != nullptr)
				log_cmd_error("Cell %s instantiates module %s: run `flatten` before `stuttering`.\n",
						log_id(cell), log_id(cell->type));

		SigMap sigmap(module);
		RTLIL::SigBit stut = sigmap(RTLIL::SigSpec(stut_wire))[0];
		RTLIL::SigSpec not_stut;   // created lazily
		auto get_not_stut = [&]() -> RTLIL::SigSpec {
			if (not_stut.empty())
				not_stut = module->Not(NEW_ID_SUFFIX("not_stuttering"), RTLIL::SigSpec(stut_wire));
			return not_stut;
		};

		int n_ff = 0, n_skip = 0, n_wr = 0, n_rd = 0;

		// ---------------------------------------------------------------- registers / latches
		for (auto cell : cells) {
			if (!RTLIL::builtin_ff_cell_types().count(cell->type))
				continue;
			if (cell->has_attribute(ATTR_DONE))
				continue;
			if (!cell->hasPort(ID::D) || !cell->hasPort(ID::Q)) {
				log_warning("Stuttering: FF cell %s (%s) has no D input, cannot be held -- skipped.\n",
						log_id(cell), log_id(cell->type));
				n_skip++;
				continue;
			}

			RTLIL::SigSpec d = cell->getPort(ID::D);
			RTLIL::SigSpec q = cell->getPort(ID::Q);

			// Do not hold the register that produces the stuttering signal itself.
			bool drives_stut = false;
			for (auto bit : sigmap(q))
				if (bit == stut) drives_stut = true;
			if (drives_stut) {
				log("  not holding %s: it drives the stuttering signal\n", log_id(cell));
				n_skip++;
				continue;
			}

			int width = GetSize(q);
			RTLIL::Wire *d_new = module->addWire(NEW_ID_SUFFIX("stut_d"), width);
			// stut == 0 -> A (= old D), stut == 1 -> B (= Q, hold)
			module->addMux(NEW_ID_SUFFIX("stut_mux"), d, q, RTLIL::SigSpec(stut_wire), d_new);
			cell->setPort(ID::D, d_new);
			cell->set_bool_attribute(ATTR_DONE);
			n_ff++;
		}

		// ---------------------------------------------------------------- memories
		if (do_mem) {
			for (auto &mem : Mem::get_all_memories(module)) {
				if (mem.has_attribute(ATTR_DONE))
					continue;
				bool changed = false;
				int mem_wr = 0, mem_rd = 0;

				for (auto &wr : mem.wr_ports) {
					if (wr.removed) continue;
					RTLIL::SigSpec ns = get_not_stut();
					RTLIL::SigSpec ns_rep;
					for (int i = 0; i < GetSize(wr.en); i++) ns_rep.append(ns);
					wr.en = module->And(NEW_ID_SUFFIX("stut_wr_en"), wr.en, ns_rep);
					changed = true;
					n_wr++; mem_wr++;
				}

				for (auto &rd : mem.rd_ports) {
					if (rd.removed || !rd.clk_enable) continue;   // async reads have no state
					rd.en = module->And(NEW_ID_SUFFIX("stut_rd_en"), rd.en, get_not_stut());
					changed = true;
					n_rd++; mem_rd++;
				}

				if (changed) {
					mem.set_bool_attribute(ATTR_DONE);
					mem.emit();
				}
				log("  memory %s: %d write port(s), %d sync read port(s) gated\n",
						log_id(mem.memid), mem_wr, mem_rd);
			}
		}

		log("Stuttering %s with %s: %d FF(s) held, %d skipped, %d memory write port(s) and %d sync read port(s) gated.\n",
				log_id(module), log_id(stut_name), n_ff, n_skip, n_wr, n_rd);
		if (n_skip)
			log_warning("Stuttering: %d FF(s) were NOT held -- check the log.\n", n_skip);
	}
} StutteringPass;

PRIVATE_NAMESPACE_END
