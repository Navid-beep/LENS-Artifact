// #include "kernel/register.h"
// #include "kernel/rtlil.h"
// #include "kernel/log.h"
// #include "kernel/yosys.h"
// #include "kernel/sigtools.h"
// #include "kernel/mem.h"
// #include "stdio.h"
// #include "backends/rtlil/rtlil_backend.h"
// #include "backends/rtlil/rtlil_backend.h"
// #include "list"
// #include <iostream>


// USING_YOSYS_NAMESPACE
// PRIVATE_NAMESPACE_BEGIN


// /*

//     args 1 -- Top Module Name - ex: miter_top
//     args 2 -- Output Folder Path 

// */


// /*
// Design choice:
//     - Instead of finding a way to dig into the design to generate the init for each submodules, it is required to flatten the design before using this pass
// */

// struct RegMemInitPass: public Pass {

//     RegMemInitPass() : Pass("reg_mem_init", "") { }

//     void execute(std::vector<std::string> args, RTLIL::Design *design) override
//     {   
//         log("Init the memories and registers.\n");

//         log("Arguments to my_cmd:\n");
//         for (auto &arg : args){
//             log("  %s\n", arg.c_str());
//         }

//         // Output Files
//         std::string reg_mem_list_file = args[2] + "/reg_mem_list.dat";
//         std::ofstream reg_mem_list;
//         reg_mem_list.open(reg_mem_list_file);

//         std::string yosys_regs_file = args[2] + "/yosys_regs.dat";
//         std::ofstream yosys_regs;
//         yosys_regs.open(yosys_regs_file);

//         // Load the topmodule
//         RTLIL::IdString top_str = RTLIL::escape_id(args[1]);

//         RTLIL::Module *top = design->module(top_str);

//         for (auto &mem: top->memories){
//             reg_mem_list << "memory" << ";" <<  RTLIL::id2cstr(mem.second->name)  << ";" << std::to_string(mem.second->size) << "\n";
//         }

//         for (auto &reg:  top->cells_){
//             if(reg.second->type.in(ID($mem_v2))){
//                 reg_mem_list << RTLIL::id2cstr(reg.second->type) << ";" << RTLIL::id2cstr(reg.second->name)   << ";" << std::to_string(reg.second->getParam(ID::SIZE).as_int()) << "\n";
//             }

//             if(RTLIL::builtin_ff_cell_types().count(reg.second->type)){
//                 reg_mem_list << RTLIL::id2cstr(reg.second->type) << ";" << RTLIL::id2cstr(reg.second->name) << ";"   << "\n"; 
//                 std::cout << "REGMEMEININT DEBUG" << RTLIL::id2cstr(reg.second->name) << std::endl;

//             }
//         }

//     for (auto type : RTLIL::builtin_ff_cell_types()) {
//         // log("THIS IS A HELLLLLLLP %s\n", log_id(type));
//         yosys_regs << log_id(type) << "\n";
//     }

//     }



// } RegMemInitPass;

// PRIVATE_NAMESPACE_END
#include "kernel/register.h"
#include "kernel/rtlil.h"
#include "kernel/log.h"
#include "kernel/yosys.h"
#include "kernel/sigtools.h"
#include "kernel/mem.h"
#include "backends/rtlil/rtlil_backend.h"
#include <fstream>
#include <iostream>
#include <string>
#include <vector>


USING_YOSYS_NAMESPACE
PRIVATE_NAMESPACE_BEGIN


/*

    args 1 -- Top Module Name - ex: miter_top
    args 2 -- Output Folder Path

*/


/*
Design choice:
    - Instead of finding a way to dig into the design to generate the init for each submodules,
      it is required to flatten the design before using this pass.
    - Flip-flops whose value can only ever influence their *own* next state are dead state
      and are skipped from reg_mem_list.dat. This is the case for `integer i` loop indices in
      clocked always blocks: the loop is inside an if-branch, so Yosys builds a hold mux
      (i <= cond ? 4 : i) and Q feeds back into its own D, but nowhere else.
    - A flip-flop is kept ("live") if its Q output reaches, through combinational logic,
      any of: another flip-flop, a memory cell, an unknown/blackbox cell, or a module output port.
    - To force-keep a register that would otherwise be dropped, put (* keep *) on it in the RTL.
*/

struct RegMemInitPass : public Pass {

    RegMemInitPass() : Pass("reg_mem_init", "list memories and live registers of a flattened design") { }

    void execute(std::vector<std::string> args, RTLIL::Design *design) override
    {
        log_header(design, "Executing REG_MEM_INIT pass.\n");

        if (args.size() < 3)
            log_cmd_error("Usage: reg_mem_init <top_module> <output_dir>\n");

        log("Arguments to reg_mem_init:\n");
        for (auto &arg : args)
            log("  %s\n", arg.c_str());

        // Load the top module
        RTLIL::IdString top_str = RTLIL::escape_id(args[1]);
        RTLIL::Module *top = design->module(top_str);
        if (top == nullptr)
            log_cmd_error("Module %s not found in design.\n", args[1].c_str());

        // Output files
        std::string reg_mem_list_file = args[2] + "/reg_mem_list.dat";
        std::ofstream reg_mem_list(reg_mem_list_file);
        if (!reg_mem_list.is_open())
            log_cmd_error("Cannot open %s for writing.\n", reg_mem_list_file.c_str());

        std::string yosys_regs_file = args[2] + "/yosys_regs.dat";
        std::ofstream yosys_regs(yosys_regs_file);
        if (!yosys_regs.is_open())
            log_cmd_error("Cannot open %s for writing.\n", yosys_regs_file.c_str());

        // ------------------------------------------------------------------
        // Build a fanout index: for every signal bit, which cells read it.
        // ------------------------------------------------------------------
        SigMap sigmap(top);
        dict<SigBit, pool<RTLIL::Cell*>> bit_readers;
        pool<SigBit> output_bits;

        for (auto cell : top->cells()) {
            // For cells whose port directions are unknown (e.g. blackboxes),
            // conservatively treat every connection as a read.
            bool known = cell->known();
            for (auto &conn : cell->connections()) {
                if (known && !cell->input(conn.first))
                    continue;
                for (auto bit : sigmap(conn.second))
                    if (bit.wire)
                        bit_readers[bit].insert(cell);
            }
        }

        for (auto wire : top->wires())
            if (wire->port_output)
                for (auto bit : sigmap(wire))
                    if (bit.wire)
                        output_bits.insert(bit);

        auto is_ff = [](RTLIL::Cell *c) {
            return RTLIL::builtin_ff_cell_types().count(c->type) > 0;
        };

        auto is_mem_cell = [](RTLIL::Cell *c) {
            return c->type.in(ID($mem), ID($mem_v2),
                              ID($memrd), ID($memrd_v2),
                              ID($memwr), ID($memwr_v2),
                              ID($meminit), ID($meminit_v2));
        };

        // ------------------------------------------------------------------
        // A FF is live if its Q reaches (through combinational cells) anything
        // other than its own inputs: another FF, a memory, an unknown cell,
        // or a module output port.
        // ------------------------------------------------------------------
        auto ff_is_live = [&](RTLIL::Cell *ff) -> bool {
            SigSpec q = ff->getPort(ID::Q);

            // Explicit (* keep *) on the register wire forces it to be listed.
            for (auto &chunk : q.chunks())
                if (chunk.wire && chunk.wire->get_bool_attribute(ID::keep))
                    return true;

            pool<SigBit> visited;
            pool<RTLIL::Cell*> visited_cells;
            std::vector<SigBit> work;

            for (auto bit : sigmap(q))
                if (bit.wire)
                    work.push_back(bit);

            while (!work.empty()) {
                SigBit bit = work.back();
                work.pop_back();
                if (visited.count(bit))
                    continue;
                visited.insert(bit);

                if (output_bits.count(bit))
                    return true;

                auto it = bit_readers.find(bit);
                if (it == bit_readers.end())
                    continue;

                for (auto reader : it->second) {
                    if (reader == ff)
                        continue;               // feedback into itself: not an observer
                    if (is_ff(reader) || is_mem_cell(reader) || !reader->known() || design->module(reader->type) != nullptr)      
                        return true;            // influences other state
                    if (visited_cells.count(reader))
                        continue;
                    visited_cells.insert(reader);

                    // Combinational cell: follow its outputs.
                    for (auto &conn : reader->connections())
                        if (reader->output(conn.first))
                            for (auto ob : sigmap(conn.second))
                                if (ob.wire)
                                    work.push_back(ob);
                }
            }
            return false;
        };

        // ------------------------------------------------------------------
        // Memories
        // ------------------------------------------------------------------
        for (auto &mem : top->memories)
            reg_mem_list << "memory" << ";" << RTLIL::id2cstr(mem.second->name)
                         << ";" << mem.second->size << "\n";

        // ------------------------------------------------------------------
        // $mem_v2 cells and flip-flops
        // ------------------------------------------------------------------
        int skipped = 0;
        for (auto cell : top->cells()) {
            if (cell->type == ID($mem_v2)) {
                reg_mem_list << RTLIL::id2cstr(cell->type) << ";" << RTLIL::id2cstr(cell->name)
                             << ";" << cell->getParam(ID::SIZE).as_int() << "\n";
                continue;
            }

            if (is_ff(cell)) {
                if (!ff_is_live(cell)) {
                    log("Skipping dead FF (only feeds itself, e.g. loop index): %s\n", log_id(cell->name));
                    skipped++;
                    continue;
                }
                reg_mem_list << RTLIL::id2cstr(cell->type) << ";" << RTLIL::id2cstr(cell->name) << ";" << "\n";
            }
        }
        log("Skipped %d dead flip-flop(s).\n", skipped);

        // ------------------------------------------------------------------
        // List of builtin FF cell types known to this Yosys build
        // ------------------------------------------------------------------
        for (auto type : RTLIL::builtin_ff_cell_types())
            yosys_regs << log_id(type) << "\n";
    }

} RegMemInitPass;

PRIVATE_NAMESPACE_END
