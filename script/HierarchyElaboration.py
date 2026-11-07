import optparse
import os
import yaml
import random as rand
import json
import re

# Import Yosys 
import YosysTemplate.yosys as yosys_script


# Implementation Import
from configuration import TEMP_CONF

def DesignConfigModification(configuration_path: str):

    with open(configuration_path, 'r') as hierarchy:
        hier_yaml = yaml.safe_load(hierarchy)


    GOLD_PREFIX = "\\gold."
    GATE_PREFIX = "\\gate."

    func_inv_conf = hier_yaml.get("functionalInvariant") or []

    for inv in range(len(func_inv_conf)):
        # signal_path = modules_dict[func_inv_conf[inv]["module"]]
        # prefix = signal_path + "." if signal_path != 'top' else ""

        invariant      = str(func_inv_conf[inv]["invariant"])
        gold_invariant = invariant
        gate_invariant = invariant

        for sig in func_inv_conf[inv].get("dataSignals", []):
            # Bare signal name (handles a file that was already processed)

            # Match the signal (with or without its path), as a whole word,
            # not already preceded by a word char, '.', or '\'
            pattern = r'(?<![\w.\\])' + re.escape(sig) + r'(?!\w)'

            # Use lambdas so the backslash in "\gold." isn't read as a regex escape
            # invariant      = re.sub(pattern, lambda m: full, invariant)
            gold_invariant = re.sub(pattern, lambda m: GOLD_PREFIX + sig, gold_invariant)
            gate_invariant = re.sub(pattern, lambda m: GATE_PREFIX + sig, gate_invariant)


        func_inv_conf[inv]["goldInvariant"] = gold_invariant
        func_inv_conf[inv]["gateInvariant"] = gate_invariant

    with open(configuration_path, 'w') as hierarchy_update:
        yaml.dump(hier_yaml, hierarchy_update)


    return 0


def DesignHierarchyGeneration(configuration_path: str):

    # Yosys Pre-Processing
    # yosys_script.Hierarchy()

    # Read the hierarchy

    with open(TEMP_CONF.targetPath + "/Hierarchy" + "/duv_structure.json", 'r') as duv_structure:
        duv_structure_o = json.load(duv_structure)

    with open(configuration_path, 'r') as hierarchy:
        hier_yaml = yaml.safe_load(hierarchy)


    modules = list(duv_structure_o["modules"].keys())
    modules_dict = {}

    top_key = ''

    for mod in modules:
        if len(mod.split('$')) > 1:
            key, val = mod.split('$')
        else:
            key, val = [mod, 'top']
            top_key = mod
        modules_dict[key] = val
 
    # Remove the top level module from the path 
    for key in modules_dict:
        modules_dict[key] = modules_dict[key].replace(top_key+".", "")

    # Contract Observation Update

    contract_conf = hier_yaml["contract"]

    for elem in contract_conf:
        if elem == "Predicate":
            continue
        elif type(contract_conf[elem]) == list:
            for obs in range(len(contract_conf[elem])):
                signal_path = modules_dict[contract_conf[elem][obs]["module"]]
                for key in contract_conf[elem][obs]:
                    if key.endswith("Signal"):
                        contract_conf[elem][obs][key] = signal_path + "." + contract_conf[elem][obs][key] if signal_path != 'top' else contract_conf[elem][obs][key]
                # contract_conf[elem] = obs

        elif type(contract_conf[elem]) == dict:
            if "module" in contract_conf[elem]:
                for key in contract_conf[elem]:
                    if key.endswith("Signal"):
                        contract_conf[elem][key] = signal_path + "." + contract_conf[elem][key] if signal_path != 'top' else contract_conf[elem][key]
    
    # Functional Invariant Update

    GOLD_PREFIX = "\\gold."
    GATE_PREFIX = "\\gate."

    func_inv_conf = hier_yaml.get("functionalInvariant") or []

    for inv in range(len(func_inv_conf)):
        signal_path = modules_dict[func_inv_conf[inv]["module"]]
        prefix = signal_path + "." if signal_path != 'top' else ""

        invariant      = str(func_inv_conf[inv]["invariant"])
        gold_invariant = invariant
        gate_invariant = invariant
        new_signals = []

        for sig in func_inv_conf[inv].get("dataSignals", []):
            # Bare signal name (handles a file that was already processed)
            bare = sig[len(prefix):] if prefix and sig.startswith(prefix) else sig
            full = prefix + bare

            # Match the signal (with or without its path), as a whole word,
            # not already preceded by a word char, '.', or '\'
            path_part = "(?:" + re.escape(prefix) + ")?" if prefix else ""
            pattern = r'(?<![\w.\\])' + path_part + re.escape(bare) + r'(?!\w)'

            # Use lambdas so the backslash in "\gold." isn't read as a regex escape
            invariant      = re.sub(pattern, lambda m: full, invariant)
            gold_invariant = re.sub(pattern, lambda m: GOLD_PREFIX + full, gold_invariant)
            gate_invariant = re.sub(pattern, lambda m: GATE_PREFIX + full, gate_invariant)

            new_signals.append(full)

        func_inv_conf[inv]["dataSignals"]   = new_signals
        func_inv_conf[inv]["invariant"]     = invariant
        func_inv_conf[inv]["goldInvariant"] = gold_invariant
        func_inv_conf[inv]["gateInvariant"] = gate_invariant

    # uArch Update
    microArch_conf = hier_yaml["microArchitecture"]

    for elem in microArch_conf:
        if (elem == "ROB" and microArch_conf[elem]["isROB"] == False):
            continue
        if (elem == "bypassMem"):
            continue
        if "module" in microArch_conf[elem]:
            signal_path = modules_dict[microArch_conf[elem]["module"]]
            for key in microArch_conf[elem]:
                if key.endswith("Signal"):
                    microArch_conf[elem][key] = signal_path + "." + microArch_conf[elem][key] if signal_path != 'top' else microArch_conf[elem][key]

    with open(configuration_path, 'w') as hierarchy_update:
        yaml.dump(hier_yaml, hierarchy_update)

    return 0
