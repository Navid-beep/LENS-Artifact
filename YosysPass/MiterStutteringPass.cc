#include "kernel/yosys.h"
#include <string>
#include <vector>

USING_YOSYS_NAMESPACE
PRIVATE_NAMESPACE_BEGIN

/*
    Usage: miter_stuttering <miter_top> <stuttering_port> <retire_port>

    args 1 -- Top module name           - ex: miter_top
    args 2 -- Stuttering port name      - input port of the gate/gold instances
    args 3 -- Retire signal port name   - ex: Retire_obs_trg_arg0_trg
                                          (output port of the gate/gold instances)

    Generated logic in the miter ("left" -> gate, "right" -> gold):

        stuttering_gate = retire_gate && !retire_gold;
        stuttering_gold = retire_gold && !retire_gate;
*/

// Returns the signal seen by `child` on `port`.
// - If the port is already connected in the miter, that signal is reused.
// - Otherwise a wire "<prefix>_<port>" is created (or reused if it already exists)
//   and connected to the port.
static RTLIL::SigSpec get_or_connect_port(RTLIL::Design *design, RTLIL::Module *miter,
                                          RTLIL::Cell *child, const std::string &prefix,
                                          const std::string &port_name)
{
    RTLIL::IdString port = RTLIL::escape_id(port_name);

    if (child->hasPort(port)) {
        RTLIL::SigSpec sig = child->getPort(port);
        if (GetSize(sig) > 0)
            return sig;
    }

    RTLIL::IdString wire_name = RTLIL::escape_id(prefix + "_" + port_name);
    RTLIL::Wire *w = miter->wire(wire_name);
    if (w == nullptr) {
        // Use the width of the port in the instantiated module when we can find it
        int width = 1;
        RTLIL::Module *ref = design->module(child->type);
        if (ref && ref->wire(port))
            width = ref->wire(port)->width;
        w = miter->addWire(wire_name, width);
    }

    child->setPort(port, RTLIL::SigSpec(w));
    return RTLIL::SigSpec(w);
}

// Returns the wire "<prefix>_<name>", creating it (1 bit) if it does not exist.
static RTLIL::Wire *get_or_add_wire(RTLIL::Module *m, const std::string &name)
{
    RTLIL::IdString id = RTLIL::escape_id(name);
    RTLIL::Wire *w = m->wire(id);
    return w ? w : m->addWire(id, 1);
}

struct MiterStutteringPass : public Pass {

    MiterStutteringPass() : Pass("miter_stuttering", "Update the miter circuit to handle different stuttering signals.") { }

    void help() override
    {
        log("\n");
        log("    miter_stuttering <miter_top> <stuttering_port> <retire_port>\n");
        log("\n");
        log("Creates gate_<stuttering_port> / gold_<stuttering_port> in the miter, connects them\n");
        log("to the gate/gold instances and drives them with:\n");
        log("\n");
        log("    gate_stuttering = retire_gate && !retire_gold\n");
        log("    gold_stuttering = retire_gold && !retire_gate\n");
        log("\n");
    }

    void execute(std::vector<std::string> args, RTLIL::Design *design) override
    {
        log_header(design, "Executing MITER_STUTTERING pass.\n");

        log("Arguments to miter_stuttering:\n");
        for (auto &arg : args)
            log("  %s\n", arg.c_str());

        if (args.size() != 4)
            log_cmd_error("Usage: miter_stuttering <miter_top> <stuttering_port> <retire_port>\n");

        const std::string &stutt_name  = args[2];
        const std::string &retire_name = args[3];

        // Load the top module
        RTLIL::Module *miter_top = design->module(RTLIL::escape_id(args[1]));
        if (miter_top == nullptr)
            log_cmd_error("Module `%s' not found.\n", args[1].c_str());

        RTLIL::Cell *gate_child = miter_top->cell(RTLIL::escape_id("gate"));
        RTLIL::Cell *gold_child = miter_top->cell(RTLIL::escape_id("gold"));
        if (gate_child == nullptr || gold_child == nullptr)
            log_cmd_error("Instances `gate' and/or `gold' not found in module `%s'.\n", args[1].c_str());

        log("---------------------------------Create Stuttering Signals for Gold & Gate------------------------------------------\n");

        RTLIL::Wire *gate_stuttering = get_or_add_wire(miter_top, "gate_" + stutt_name);
        RTLIL::Wire *gold_stuttering = get_or_add_wire(miter_top, "gold_" + stutt_name);

        log("---------------------------------Connect the Instances Port to the Signals------------------------------------------\n");

        gate_child->setPort(RTLIL::escape_id(stutt_name), RTLIL::SigSpec(gate_stuttering));
        gold_child->setPort(RTLIL::escape_id(stutt_name), RTLIL::SigSpec(gold_stuttering));

        log("---------------------------------Drive the Stuttering Signals from Retire------------------------------------------\n");

        RTLIL::SigSpec retire_gate = get_or_connect_port(design, miter_top, gate_child, "gate", retire_name);
        RTLIL::SigSpec retire_gold = get_or_connect_port(design, miter_top, gold_child, "gold", retire_name);

        // stuttering_gate = retire_gate && !retire_gold
        // RTLIL::Wire *not_retire_gold = miter_top->addWire(NEW_ID, 1);
        // miter_top->addLogicNot(NEW_ID, retire_gold, RTLIL::SigSpec(not_retire_gold));
        // miter_top->addLogicAnd(NEW_ID, retire_gate, RTLIL::SigSpec(not_retire_gold), RTLIL::SigSpec(gate_stuttering));

        // stuttering_gold = retire_gold && !retire_gate
        // RTLIL::Wire *not_retire_gate = miter_top->addWire(NEW_ID, 1);
        // miter_top->addLogicNot(NEW_ID, retire_gate, RTLIL::SigSpec(not_retire_gate));
        // miter_top->addLogicAnd(NEW_ID, retire_gold, RTLIL::SigSpec(not_retire_gate), RTLIL::SigSpec(gold_stuttering));

        miter_top->fixup_ports();
    }

} MiterStutteringPass;

PRIVATE_NAMESPACE_END

