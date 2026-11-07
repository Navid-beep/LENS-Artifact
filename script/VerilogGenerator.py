import optparse
import os
import yaml
import random as rand
import math
import re

# Implementation Import
from configuration import CONF

# Import Contract
import Contract.Contract_Indirect_Synch as Indirect
import Contract.Contract_Direct_Synch as Direct
import PipelineDrain
import AttackerObservation

# Import Yosys 
import YosysTemplate.yosys as yosys_script


def extract_block(template, tag):
    m = re.search(r"{0}_BEGIN\n?(.*?){0}_END".format(tag), template, re.DOTALL)
    if m is None:
        raise ValueError("{}_BEGIN/_END markers not found".format(tag))
    return m.group(1)


def manual_init_signals():
    """
    Read manually specified init signals from CONF.

    Expected YAML:
        microArchitecture:
          InitialState:
            - module: DatPath_2stage
              dataSignal: Core_2stage.DatPath_2stage.io_ctl_if_kill
              # value: 0          (optional, defaults to 0)

    Returns a list of (signal, value) tuples, in the order given.
    """
    entries = CONF.microArchitecture.get("InitialState") or []
    if isinstance(entries, dict):          # tolerate a single entry without the leading "-"
        entries = [entries]

    signals = []
    for idx, entry in enumerate(entries):
        signal = str(entry.get("dataSignal") or "").strip()
        if not signal:
            raise ValueError(
                "microArchitecture.InitialState[{}] is missing 'dataSignal'".format(idx)
            )
        value = entry.get("value", 0)
        signals.append((signal, value))
    return signals


def no_init_signals():
    """
    Collect the signals that must NOT be initialised: every signal listed in
    'dataSignals' of a functionalInvariant entry with noInit: true.
    noInit defaults to false when it is not set.

    Expected YAML:
        functionalInvariant:
          - module:
            dataSignals: [Core_2stage.DatPath_2stage.exe_reg_inst]
            invariant: ( ... )
            noInit: true
            condition: []

    Returns a set of signal names (bit slices such as "sig [6:0]" are reduced to "sig").
    """
    entries = getattr(CONF, "functionalInvariant", None)
    if entries is None:                         # also accept it under microArchitecture
        entries = CONF.microArchitecture.get("functionalInvariant")
    entries = entries or []
    if isinstance(entries, dict):
        entries = [entries]

    skip = set()
    for entry in entries:
        if not entry or not entry.get("noInit", False):
            continue
        signals = entry.get("dataSignals") or []
        if isinstance(signals, str):            # tolerate a single signal written without [ ]
            signals = [signals]
        for sig in signals:
            sig = str(sig).split("[")[0].strip()
            if sig:
                skip.add(sig)
    return skip


def initial_block():

    # read reg and mem file
    hier = os.path.join(CONF.targetPath, "Hierarchy")
    with open(os.path.join(hier, "reg_mem_list.dat")) as f:
        reg_mem_lines = f.readlines()
    with open(os.path.join(hier, "yosys_regs.dat")) as f:
        yosys_regs = f.read()

    # Verilog init part
    with open("script/VerilogTemplate/InitRegMem.v") as f:
        verilog_template_o = f.readlines()

    imem   = CONF.microArchitecture["instructionMemory"]["dataSignal"]
    dmem   = CONF.microArchitecture["dataMemory"]["dataSignal"]
    secret = CONF.microArchitecture["dataMemory"]["secret"]

    init_lines = []
    data_lines = []
    first_elem = True

    # Manually specified init signals (microArchitecture.InitialState)
    manual_signals = manual_init_signals()
    manual_names = {sig for sig, _ in manual_signals}

    # Signals constrained by a functional invariant with noInit: true -> never initialised
    no_init = no_init_signals()

    # parse file to extract - module - signal
    for elem in reg_mem_lines:
        key, name, *rest = elem.split(";")

        # register
        if yosys_regs and key in yosys_regs:
            signal = name.split("$")[2]
            # skip if set manually (avoids duplicates) or excluded by noInit
            if signal not in manual_names and signal not in no_init:
                if imem not in signal or dmem not in signal:
                    init_lines.append("        && \\gold.{0} == \\gate.{0} && \\gold.{0} == 0 \n".format(signal))

        # memory
        if "$mem_v2" in key or "memory" in key:
            has_imem = imem in name
            has_dmem = dmem in name
            depth = int(rest[0])

            if name not in no_init and (not has_imem and not has_dmem) and not (CONF.microArchitecture["bypassMem"]["Condition"] and (CONF.microArchitecture["bypassMem"]["Module"] + "." + CONF.microArchitecture["bypassMem"]["dataSignal"] in name)):
                init_lines.extend(
                    "        && \\gold.{0} [{1}] == \\gate.{0} [{1}] && \\gold.{0} [{1}] == 0 \n".format(name, idx)
                    for idx in range(depth)
                )

            # if has_dmem and not has_imem:
            #     for idx in range(depth):
            #         if idx == secret:
            #             continue
            #         if first_elem:
            #             first_elem = False
            #             data_lines.append("     \\gold.{0} [{1}] == \\gate.{0} [{1}] && \\gold.{0} [{1}] == 0 \n".format(name, idx))
            #         else:
            #             data_lines.append("      && \\gold.{0} [{1}] == \\gate.{0} [{1}] && \\gold.{0} [{1}] == 0 \n".format(name, idx))

    # append manual init signals
    for signal, value in manual_signals:
        if signal in no_init:
            print("[initial_block] WARNING: '{}' is in InitialState but has noInit: true "
                  "in functionalInvariant -> not initialised".format(signal))
            continue
        init_lines.append(
            "        && \\gold.{0} == \\gate.{0} && \\gold.{0} == {1} \n".format(signal, value)
        )

    init_wire = "".join(init_lines)
    data_wire = "".join(data_lines)

    # Init Specific Signals from Indirect Contract
    template = "".join(verilog_template_o)

    pipeline_drain = ""
    if CONF.experimentalParameters["PipelineDrain"] == "out-of-order":
        pipeline_drain = extract_block(template, "OUT_OF_ORDER_PIPELINE_DRAIN")

    contract_wire = ""
    if CONF.experimentalParameters["Synch_method"] == "indirect":
        contract_wire = extract_block(template, "CONTRACT_SPECIFICATION_INDIRECT")

    verilog_wire = data_wire + init_wire + pipeline_drain + contract_wire

    # the first condition must not start with "&&" (keep its indentation)
    verilog_wire = re.sub(r"^(\s*)&&[ \t]*", r"\1", verilog_wire, count=1)

    pipeline_drain_block = re.compile(r"[ \t]*OUT_OF_ORDER_PIPELINE_DRAIN_BEGIN[ \t]*\n?(.*?)[ \t]*OUT_OF_ORDER_PIPELINE_DRAIN_END[ \t]*\n?", re.DOTALL)
    indirect_contract_block = re.compile(r"[ \t]*CONTRACT_SPECIFICATION_INDIRECT_BEGIN[ \t]*\n?(.*?)[ \t]*CONTRACT_SPECIFICATION_INDIRECT_END[ \t]*\n?", re.DOTALL)
    direct_contract_block = re.compile(r"[ \t]*DIRECT_CONTRACT_SPECIFICATION_BEGIN[ \t]*\n?(.*?)[ \t]*DIRECT_CONTRACT_SPECIFICATION_END[ \t]*\n?", re.DOTALL)

    template = pipeline_drain_block.sub("", template)
    template = indirect_contract_block.sub("", template)
    template = direct_contract_block.sub("", template)

    verilog = template.replace("REG_INIT_PLACEHOLDER", verilog_wire)

    if CONF.experimentalParameters["Synch_level"] == "HighLevelClock":
        verilog = verilog.replace("SYNCHRONIZATION", "stall")
    else:
        verilog = verilog.replace("SYNCHRONIZATION", "stuttering")

    verilog = verilog.replace("CLOCK", CONF.microArchitecture["clock"])
    return verilog


def functionalInvariant():
    verilog = ""
    invariant = ""
    assumption = "assume ( "
    assumption_list = []
    count = 0
    for invar in CONF.functionalInvariant:
        invariant += "wire gold_invar_{0} = {1} ;\n".format(count, invar["goldInvariant"])
        invariant += "wire gate_invar_{0} = {1} ;\n".format(count, invar["gateInvariant"])
        assumption_list.append("gold_invar_{0}".format(count))
        assumption_list.append("gate_invar_{0}".format(count))
        count += 1

    assumption += " && ".join(assumption_list)
    assumption += " ); \n"

    verilog += invariant + assumption

    return verilog

def programMemory():
    """
    Build the program-equivalence assumption from:

        contract:
          ProgramEquivalence:
            - module: memi
              dataSignal: array_mem
              width: 11
              range: 8
              condition: []

    Each memory word gets a wire program_<n> (\\gold.<dataSignal> [i] == \\gate.<dataSignal> [i]);
    they are ANDed into program_equiv and assumed. dataSignal is used as-is (the hierarchy
    pass has already resolved the full path).
    Returns "" if contract / ProgramEquivalence is not defined or empty.
    """
    contract = getattr(CONF, "contract", None) or {}
    entries = contract.get("ProgramEquivalence") or []
    if isinstance(entries, dict):              # tolerate a single entry without the leading "-"
        entries = [entries]
    if not entries:
        return ""

    wire_lines = []
    wire_names = []

    for p in entries:
        path = str(p["dataSignal"]).strip()     # already the full hierarchical path
        depth = int(p["range"])

        for idx in range(depth):
            wire = "program_{}".format(len(wire_names))   # unique across all entries
            wire_names.append(wire)
            wire_lines.append(
                "wire {0} = \\gold.{1} [{2}] == \\gate.{1} [{2}];\n".format(wire, path, idx)
            )

    if not wire_names:
        return ""

    verilog = "".join(wire_lines)
    verilog += "\nwire program_equiv = {};\n".format(" && ".join(wire_names))
    verilog += "assume (program_equiv);\n"
    return verilog

def ContractGeneration():
    """
    Control Function for the verification of the generated positive example
    1) Run Yosys Pass to generate the stuttering miter circuit
    2) generate the verification template in verilog
    3) simulate the program on the design 

    Returns the verification result
    """
    Passed = False

    # Yosys

    yosys_script.YosysContract()

    # Load the miter circuit to modify
    with open(CONF.targetPath + "/Contract/Verilog" + "/contractVerification_verilog.v", 'r') as miter_file:
        miter_circuit = miter_file.read()

    # Clean the stuttering/stalling signal
    stutter = "stall" if CONF.experimentalParameters["Synch_level"] == "HighLevelClock" else "stuttering"
    miter_circuit = miter_circuit.replace(f"wire gold_{stutter}_signal;", "")
    miter_circuit = miter_circuit.replace(f"wire gate_{stutter}_signal;", "")




    with open(CONF.targetPath + "/Contract/Verilog" + "/contractVerification_verilog.v", 'w') as miter_file_modified:
        miter_file_modified.write(miter_circuit)

    # Verilog Generation 
    verilog = "\n"

    # Init the registers and memory
    verilog += initial_block()

    verilog += functionalInvariant()

    verilog += programMemory()

    # Specify the contract
    match CONF.experimentalParameters["Synch_method"]:
        case "direct":
            verilog += Direct.contract_seq_ct()
            verilog += AttackerObservation.AttackerObservation_Direct()
        case "indirect":
            contract_template = Indirect.contract_seq_ct()
            verilog += AttackerObservation.AttackerObservation_Indirect(contract_template)
        case _:
            raise ValueError("Select a contract method.")

    if CONF.experimentalParameters["PipelineDrain"] == "out-of-order":
        verilog += PipelineDrain.PipelineDrain_OutOfOrder()
    else: 
        verilog += PipelineDrain.PipelineDrain_InOrder()
        
    verilog += "endmodule\n"

    with open(CONF.targetPath + "/Contract/Verilog" + "/contractVerification_verilog.v", 'r') as miter_file:
        miter_circuit = miter_file.readlines()


    with open(CONF.targetPath + "/Contract/Verilog" + "/contractVerification_verilog.v", 'w') as miter_file_modified:
        miter_file_modified.writelines(miter_circuit[:-1])
        miter_file_modified.write(verilog)


        # Verification


    return Passed