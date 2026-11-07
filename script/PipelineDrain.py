import optparse
import os
import yaml
import random as rand
import math

# Implementation Import
from configuration import CONF
from AttackerObservation import deviation_wires   # commit_deviation (+ addr_deviation if 'addr' is in the YAML)

import re

def extract_block(template, tag):
    m = re.search(r"{0}_BEGIN\n?(.*?){0}_END".format(tag), template, re.DOTALL)
    if m is None:
        raise ValueError("{}_BEGIN/_END markers not found".format(tag))
    return m.group(1)


def PipelineDrain_OutOfOrder():


    with open("script/VerilogTemplate/PipelineDrain.v", 'r') as verilog_template:
        verilog_o = verilog_template.read()

    verilog = extract_block(verilog_o, "OUT_OF_ORDER_PIPELINE_DRAIN")


    if (CONF.experimentalParameters["Synch_method"] == 'direct'):
        rob_drain_direct = extract_block(verilog_o, "DIRECT_CONTRACT_OUT_OF_ORDER_PROC")
    else:
        rob_drain_direct = ""

    verilog += rob_drain_direct

    gate_commit_cond   = ""
    gold_commit_cond   = ""
    gate_rollback_cond = ""
    gold_rollback_cond  = ""

    for commitSignal in CONF.microArchitecture["COMMIT"]["commitNumSignal"]:
        gate_commit_cond += "((\\gate.{} && \\gate.{} == GATE_ROB_TAIL_rec ) || ".format(commitSignal, CONF.microArchitecture["ROB"]["headSignal"], CONF.microArchitecture["ROB"]["tailSignal"])
        gate_rollback_cond += "(\\gate.{} && \\gate.{} ))".format(commitSignal, CONF.microArchitecture["rollbackSignal"]["dataSignal"])

        gold_commit_cond += "((\\gold.{} && \\gold.{} == GOLD_ROB_TAIL_rec ) || ".format(commitSignal, CONF.microArchitecture["ROB"]["headSignal"], CONF.microArchitecture["ROB"]["tailSignal"])
        gold_rollback_cond += "(\\gold.{} && \\gold.{} ))".format(commitSignal, CONF.microArchitecture["rollbackSignal"]["dataSignal"])

    # Contract Pipeline drain
    atk_obs= ""
    if (CONF.experimentalParameters["Synch_method"] == "direct"):
        trigger = "!state_trg_equiv"
        atk_obs = "( {} )".format(" && ".join(deviation_wires()))
    else:
        trigger = "trg_equiv"
        atk_obs = "!( {} )".format(" || ".join(deviation_wires()))


    # Order matters: MITER_TOPMODULE must come before TOPMODULE
    replacements = [
        ("GATE_COMMIT_SIGNAL_CONDITION",   gate_commit_cond),
        ("GATE_COMMIT_ROLLBACK_CONDITION", gate_rollback_cond),
        ("COUNT_UPPER_BOUND", str(math.ceil(math.log2(CONF.microArchitecture["ROB"]["lookahead"])))),
        ("GOLD_COMMIT_SIGNAL_CONDITION", gold_commit_cond),
        ("GOLD_COMMIT_ROLLBACK_CONDITION", gold_rollback_cond), 
        ("ATTACKER_OBSERVATIONS", atk_obs ),
        ("CLOCK", CONF.microArchitecture["clock"]), 
        ("RESET", CONF.microArchitecture["reset"]),
        ("ROB_TAIL_SIZE", str(math.ceil(math.log2(CONF.microArchitecture["ROB"]["entries"])))), 
        ("GATE_ROB_RECORDING", "\\gate." + CONF.microArchitecture["ROB"]["tailSignal"]),
        ("GOLD_ROB_RECORDING", "\\gold." + CONF.microArchitecture["ROB"]["tailSignal"]),
        ("TRIGGER_SIGNAL", trigger), 
    ]

    for placeholder, value in replacements:
        verilog = verilog.replace(placeholder, value)

    if CONF.experimentalParameters["Synch_level"] == "HighLevelClock":
        verilog = verilog.replace("SYNCHRONIZATION", "stall")
    else:
        verilog = verilog.replace("SYNCHRONIZATION", "stuttering")

    return verilog

def PipelineDrain_InOrder():

    # Read Yosys Template

    with open("script/VerilogTemplate/PipelineDrain.v", 'r') as verilog_template:
        verilog = verilog_template.read()

    verilog = extract_block(verilog, "IN_ORDER_PIPELINE_DRAIN")

    if (CONF.experimentalParameters["Synch_method"] == "direct"):
        attacker_obs = " && ".join(deviation_wires())
        trigger = "!state_trg_equiv"
    else:
        trigger = "trg_equiv"
        attacker_obs = "!( {} )".format(" || ".join(deviation_wires()))


    replacements = [
        ("LOOKAHEAD",   str(CONF.microArchitecture["ROB"]["lookahead"])),
        ("LA_UPPER_BOUND", str(math.ceil(math.log2(CONF.microArchitecture["ROB"]["lookahead"])))),
        ("COUNT_UPPER_BOUND", str(math.ceil(math.log2(CONF.microArchitecture["ROB"]["lookahead"])))),
        ("CLOCK", CONF.microArchitecture["clock"]),
        ("ATTACKER_OBSERVATIONS", attacker_obs ), 
        ("TRIGGER_SIGNAL", trigger), 


    ]

    if CONF.experimentalParameters["Synch_level"] == "HighLevelClock":
        verilog = verilog.replace("SYNCHRONIZATION", "stall")
    else:
        verilog = verilog.replace("SYNCHRONIZATION", "stuttering")


    for placeholder, value in replacements:
        verilog = verilog.replace(placeholder, value)


    return verilog
