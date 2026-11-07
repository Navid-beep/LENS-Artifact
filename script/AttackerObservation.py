
import optparse
import os
import yaml
import random as rand
import math
import re

# Implementation Import
from configuration import CONF

def extract_block(template, tag):
    m = re.search(r"{0}_BEGIN\n?(.*?){0}_END".format(tag), template, re.DOTALL)
    if m is None:
        raise ValueError("{}_BEGIN/_END markers not found".format(tag))
    return m.group(1)


def get_observation(name):
    """
    Return the AttackerObservation entry with the given 'name', or None if absent.
    """
    observations = CONF.contract.get("AttackerObservation") or []
    if isinstance(observations, dict):          # tolerate a single entry without the leading "-"
        observations = [observations]
    for obs in observations:
        if str(obs.get("name") or "").strip() == name:
            return obs
    return None


def get_commit_observation():
    obs = get_observation("commit")
    if obs is None:
        raise ValueError("contract.AttackerObservation must define an observation with 'name: commit'")
    return obs


def deviation_wires():
    """
    Deviation signals that are actually generated, e.g.
    ["commit_deviation"] or ["commit_deviation", "addr_deviation"].
    Use it wherever the deviations are combined (ATTACKER_OBSERVATIONS, trg_equiv).
    """
    wires = ["commit_deviation"]
    if get_observation("addr") is not None:
        wires.append("addr_deviation")
    return wires


def AttackerObservation_Direct():

    """
    Direct Contract:
    - commit time deviation        (mandatory, name: commit)
    - memory address deviation     (optional,  name: addr) -> skipped if not in the YAML
    """
    verilog = ""

    commit = get_commit_observation()

    # Commit time deviation
    verilog += "wire commit_deviation = "

    if len(commit.get("condition") or []) > 0:
        for cond in commit["condition"]:
            verilog += " \\gold.{0} == {1} && \\gate.{0} == {1} &&".format(cond["dataSignal"], cond["condition"])

    verilog += "( \\gold.{0} == \\gate.{0} );\n".format(commit["dataSignal"])

    # Address Deviation (optional)
    sig = get_observation("addr")
    if sig is None:
        return verilog

    if CONF.experimentalParameters["PipelineDrain"] == "out-of-order":
        verilog += "wire addr_deviation = commit_deviation && "
    else:
        verilog += "wire addr_deviation = "

    name = sig["dataSignal"]
    conditions = sig.get("condition") or []
    cond_terms = ""
    eq_terms   = ""
    # trailing space after each escaped identifier is required
    if (len(conditions) > 0):
        eq_terms   = ["\\gold.{0} == \\gate.{0} ".format(c["dataSignal"]) for c in conditions]
        cond_terms = ["\\gold.{0} == {1}".format(c["dataSignal"], c["condition"]) for c in conditions]

    data_eq = "( \\gold.{0} == \\gate.{0} ) \n".format(name)

    if cond_terms:
        guarded = "( !({}) || {})".format(" && ".join(cond_terms), data_eq)
        expr = " && ".join(eq_terms + [guarded])
    else:
        expr = data_eq   # unconditional observation

    verilog += "{};\n".format(expr)

    return verilog



def AttackerObservation_Indirect(contract: str):
    """
    Indirect Contract:
    - memory address deviation     (optional, name: addr) -> placeholder emptied if not in the YAML
    """
    get_commit_observation()                    # commit is mandatory

    sig = get_observation("addr")
    if sig is None:
        return contract.replace("ADDRESS_DEVIATION_DETECTION", "")

    with open("script/VerilogTemplate/AttackerObservation.v", 'r') as verilog_template:
        verilog = verilog_template.read()

    rob_drain_template = extract_block(verilog, "ROB_RECORDING")

    addr_dev_template = extract_block(verilog, "ADDRESS_DEVIATION_TEMPLATE")

    if (CONF.experimentalParameters["PipelineDrain"] == "out-of-order"):
        addr_dev_template = addr_dev_template.replace("ROB_RECORDING_PLACEHOLDER", rob_drain_template)
    else:
        addr_dev_template = addr_dev_template.replace("ROB_RECORDING_PLACEHOLDER", "")

    condition = ""
    for cond in sig.get("condition") or []:
        condition += " \\gold.{0} == {1} && \\gate.{0} == {1} &&".format(cond["dataSignal"], cond["condition"])

    replacements = [
        ("CLOCK", CONF.microArchitecture["clock"]),
        ("RESET", CONF.microArchitecture["reset"]),
        ("GOLD_ADDRESS_OBSERVATION", "\\gold." + sig["dataSignal"]),
        ("GATE_ADDRESS_OBSERVATION", "\\gate." + sig["dataSignal"]),
        ("GATE_ROB_RECORDING", "\\gate." + CONF.microArchitecture["ROB"]["tailSignal"]),
        ("GOLD_ROB_RECORDING", "\\gate." + CONF.microArchitecture["ROB"]["tailSignal"]),
        ("CONDITION", condition)
    ]

    for placeholder, value in replacements:
        addr_dev_template = addr_dev_template.replace(placeholder, value)

    contract = contract.replace("ADDRESS_DEVIATION_DETECTION", addr_dev_template)

    return contract
