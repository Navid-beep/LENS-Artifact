import optparse
import os
import yaml
import random as rand
import math

# Implementation Import
from configuration import CONF

def contract_seq_ct():

    observation = ""
    tests = []

    with open("script/VerilogTemplate/Contract_Direct.v", 'r') as verilog_template:
        synch = verilog_template.read()



    # synch += "wire gate_SYNCHRONIZATION_signal = \\gate.{0} && ! \\gold.{0} ; \n".format(CONF.contract["retirementPredicate"]["dataSignal"])
    # synch += "wire gold_SYNCHRONIZATION_signal = \\gold.{0} && ! \\gate.{0} ; \n".format(CONF.contract["retirementPredicate"]["dataSignal"])

    synch = synch.replace("CLOCK", CONF.microArchitecture["clock"])

    synch = synch.replace("RETIREMENT_PREDICATE", CONF.contract["retirementPredicate"]["dataSignal"])
    
    if CONF.experimentalParameters["Synch_level"] == "HighLevelClock":
        synch = synch.replace("SYNCHRONIZATION", "stall")
    else:
        synch = synch.replace("SYNCHRONIZATION", "stuttering")

    for sig in CONF.contract["contractObservation"]:
        name = sig["dataSignal"]
        obs_name = name.replace(".", "_")
        obs_name = "{}_observation".format(obs_name)
        tests.append(obs_name)

        cond_terms = ""
        eq_terms   = ""
        # trailing space after each escaped identifier is required
        if (len(sig["condition"]) > 0):
            eq_terms   = ["\\gold.{0} == \\gate.{0} ".format(c["dataSignal"]) for c in sig["condition"]]
            cond_terms = ["\\gold.{0} == {1}".format(c["dataSignal"], c["condition"]) for c in sig["condition"]]
        data_eq    = "\\gold.{0} == \\gate.{0} ".format(name)

        if cond_terms:
            guarded = "( !({}) || {})".format(" && ".join(cond_terms), data_eq)
            expr = " && ".join(eq_terms + [guarded])
        else:
            expr = data_eq   # unconditional observation

        observation += "    wire {} = {};\n".format(obs_name, expr)
    ret = CONF.contract["retirementPredicate"]["dataSignal"]
    contract =      "    wire contract_leakage = !( \\gold.{0} && \\gate.{0} ) || ({1} ); \n".format(ret, " && ".join(tests))

    assumption =    "    assume (contract_leakage ); \n\n"

    verilog = synch + observation + contract + assumption

    verilog = verilog.replace("RESET", CONF.microArchitecture["reset"])

    return verilog