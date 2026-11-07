import optparse
import os
import yaml
import random as rand
import math

# Implementation Import
from configuration import CONF
import re


# def commit_dev_single_issue(ret_case: str, contractSignal: dict):
#     # Contract handling for single issue processor
#     verilog = "\n"

#     cond = ""
#     signal = ""

#     contract = ""

#     if (CONF.microArchitecture["ROB"]["isROB"]):
#         # If OoO

#         # Contract Verification
#         for sig in CONF.contract["contractObservation"]:
#             signal = "\\gate." + sig["dataSignal"] + " != " + "\\gold." + sig["dataSignal"]

#             for condition in sig["condition"]:
#                 cond += f"{condition["dataSignal"]} == {condition["condition"]} && "

#             contract += "                if({} && {} ) begin\n".format(cond, signal)
#             contract += "                    {} <= 1;\n".format(contractSignal["invalidate"][0])
#             contract += "                end\n"
#             contract += "\n"

#         match ret_case:
#             case "synch_retirement": 

#                 # CPU1 and CPU2 commits 
#                 verilog += contract

#                 # not CPU1 and CPU2 commits
#                 verilog += "            end else if (!\\gate.{} && \\gold.{} ) begin \n\n".format(CONF.contract["retirementPredicate"]["dataSignal"], CONF.contract["retirementPredicate"]["dataSignal"])
#                 verilog += "                    gold_{} <= 1;\n".format(contractSignal["stuttering"][0])
#                 verilog += "                    {} <= 1;\n".format(contractSignal["deviation"][0])
#                 verilog += "                    if (!({} || {} )) begin \n".format(contractSignal["deviation"][0], contractSignal["deviation"][1])
#                 verilog += "                        gate_{}_rec <= \\gate.{} ;\n".format(CONF.microArchitecture["ROB"]["tailSignal"], CONF.microArchitecture["ROB"]["tailSignal"])
#                 verilog += "                        gold_{}_rec <= \\gold.{} ;\n".format(CONF.microArchitecture["ROB"]["tailSignal"], CONF.microArchitecture["ROB"]["tailSignal"])
#                 verilog += "                    end\n\n"

#                 # CPU1 and not CPU2 commits
#                 verilog += "            end else if (\\gate.{} && !\\gold.{} ) begin \n\n".format(CONF.contract["retirementPredicate"]["dataSignal"], CONF.contract["retirementPredicate"]["dataSignal"])
#                 verilog += "                    gate_{} <= 1;\n".format(contractSignal["stuttering"][0])
#                 verilog += "                    {} <= 1;\n".format(contractSignal["deviation"][0])
#                 verilog += "                    if (!({} || {} )) begin \n".format(contractSignal["deviation"][0], contractSignal["deviation"][1])
#                 verilog += "                        gate_{}_rec <= \\gate.{} ;\n".format(CONF.microArchitecture["ROB"]["tailSignal"], CONF.microArchitecture["ROB"]["tailSignal"])
#                 verilog += "                        gold_{}_rec <= \\gold.{} ;\n".format(CONF.microArchitecture["ROB"]["tailSignal"], CONF.microArchitecture["ROB"]["tailSignal"])
#                 verilog += "                    end\n\n"

#                 verilog += "            end\n\n"

#             case "gate_stall":
#                 verilog += "            if (\\gold.{} ) begin \n\n".format(CONF.contract["retirementPredicate"]["dataSignal"])
#                 verilog += contract
#                 verilog += "            end\n\n"

#             case "gold_stall":
#                 verilog += "            if (\\gate.{} ) begin \n\n".format(CONF.contract["retirementPredicate"]["dataSignal"])
#                 verilog += contract
#                 verilog += "            end\n\n"

#     else:
#         verilog += ""

#     return verilog


# def old_contract_seq_ct():

#     # Enforce contract -- Shadow Logic inspired template but generalised
#     contractSignal = {
#         "stuttering": ["stuttering_signal", "stuttering_signal"],
#         "pipeline": ["empty_pipeline", "empty_pipeline"], 
#         "deviation": ["commit_deviation", "addr_deviation"],
#         "invalidate": ["invalid_program"]
#     }

#     verilog = "\n"

#     verilog += "/* ------ Contract Enforcement ------*/\n"

#     verilog += "always @(posedge {}) begin \n".format(CONF.microArchitecture["clock"])
#     verilog += "    if ({}) begin \n".format(CONF.microArchitecture["reset"])

#     for elem in contractSignal:
#         print(elem)
#         for signal in contractSignal[elem]:
#             verilog += "        {} <= 0;\n".format(signal)

#     verilog += "    end else begin \n"

#     verilog += "        if (!gold_{} && !gate_{}) begin \n".format(contractSignal["stuttering"][0], contractSignal["stuttering"][1])

#     verilog += commit_dev_single_issue("synch_retirement", contractSignal)

#     verilog += "        end else if (gate_{} && !gold_{}) begin \n".format(contractSignal["stuttering"][0], contractSignal["stuttering"][1])

#     verilog += commit_dev_single_issue("gate_stall", contractSignal)

#     verilog += "        end else if (!gate_{} && gold_{}) begin \n".format(contractSignal["stuttering"][0], contractSignal["stuttering"][1])

#     verilog += commit_dev_single_issue("gold_stall", contractSignal)

#     verilog += "        end\n\n"

#     #TODO: Addr Deviation rountine

#     # verilog += PipelineDrain(contractSignal)

#     verilog += "    end\n\n"
#     return verilog


def extract_block(template, tag):
    m = re.search(r"{0}_BEGIN\n?(.*?){0}_END".format(tag), template, re.DOTALL)
    if m is None:
        raise ValueError("{}_BEGIN/_END markers not found".format(tag))
    return m.group(1)


def contract_seq_ct():

    with open("script/VerilogTemplate/Contract_Indirect.v", 'r') as verilog_template:
        verilog_temp = verilog_template.read()

    verilog = extract_block(verilog_temp, "CONTRACT_SPECIFICATION")


    # Pipeline Drain Method
    if CONF.experimentalParameters["PipelineDrain"] == "out-of-order":
        rob_block = extract_block(verilog_temp, "ROB_RECORDING")
        verilog = verilog.replace("ROB_RECORDING_PLACEHOLDER", rob_block)
    else:
        verilog = verilog.replace("ROB_RECORDING_PLACEHOLDER", "")

    # Contract Observation
    contract = ""
    for sig in CONF.contract["contractObservation"]:
        contract_block = extract_block(verilog_temp, "CONTRACT_TEMPLATE")
        cond = ""
        if (len(sig["condition"]) > 0):
            for condition in sig["condition"]:
                cond += f"\\gate.{condition["dataSignal"]} == {condition["condition"]} && "
                cond += f"\\gold.{condition["dataSignal"]} == {condition["condition"]} && "
        equiv = "\\gate." + sig["dataSignal"] + " != " + "\\gold." + sig["dataSignal"]

        contract_block = contract_block.replace("CONTRACT_CONDITION", cond)
        contract_block = contract_block.replace("CONTRACT_EQUIVALENCE", equiv)

        contract += contract_block + "\n\n"


    verilog = verilog.replace("CONTRACT_TEMPLATE_PLACEHOLDER", contract)


    # Order matters: MITER_TOPMODULE must come before TOPMODULE
    replacements = [
        ("CLOCK", CONF.microArchitecture["clock"]), 
        ("RESET", CONF.microArchitecture["reset"]), 
        ("GATE_RETIREMENT_PREDICATE", "\\gate." + CONF.contract["retirementPredicate"]["dataSignal"]),
        ("GOLD_RETIREMENT_PREDICATE", "\\gold." + CONF.contract["retirementPredicate"]["dataSignal"]),
        ("GATE_ROB_RECORDING", "\\gate." + CONF.microArchitecture["ROB"]["tailSignal"]),
        ("GOLD_ROB_RECORDING", "\\gold." + CONF.microArchitecture["ROB"]["tailSignal"]),
        
    ]



    for placeholder, value in replacements:
        verilog = verilog.replace(placeholder, value)


    # Synchronization Method
    if CONF.experimentalParameters["Synch_level"] == "HighLevelClock":
        verilog = verilog.replace("SYNCHRONIZATION", "stall")
    else:
        verilog = verilog.replace("SYNCHRONIZATION", "stuttering")

    rob_recording = "GATE_ROB_TAIL_rec <= 0; \n"
    rob_recording += "GOLD_ROB_TAIL_rec <= 0; \n"


    # Synchronization Method
    if CONF.experimentalParameters["PipelineDrain"] == "out-of-order":
        verilog = verilog.replace("ROB_RECORDING_SIGNAL", rob_recording)
    else:
        verilog = verilog.replace("ROB_RECORDING_SIGNAL", "")


    return verilog