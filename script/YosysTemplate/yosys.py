import optparse
import os
import yaml
import random as rand
from subprocess import run

# Implementation Import
from configuration import TEMP_CONF, CONF

def Hierarchy():
    """
    This function:
    1) Read the yosys template to generate the processed circuit design
    2) Modify the placeholders in the template with appropriate files 
    3) Run the yosys command to generate the circuit
    """

    def fill_template(path, replacements):
        with open(path, 'r') as f:
            text = f.read()
        for placeholder, value in replacements:
            text = text.replace(placeholder, value)
        return text


    src_files = os.listdir(TEMP_CONF.designSrc)

    macro_lst = "".join(f" -D {m} " for m in TEMP_CONF.designMacro) if TEMP_CONF.designMacro else ""
    file_lst  = "".join(f"{TEMP_CONF.designSrc}/{f} " for f in src_files)

    replacements = [
        ("YOSYS_PASS_PATH", "YosysPass/bin"),
        ("TOPMODULE",       TEMP_CONF.designTop),
        ("MACRO",           macro_lst),
        ("VERILOG_FILES",   file_lst),
        ("HIERARCHY",       TEMP_CONF.targetPath + "/Hierarchy"),
    ]

    yosys_1 = fill_template("script/YosysTemplate/DesignHierarchy.ys", replacements)
    yosys_2 = fill_template("script/YosysTemplate/DesignRegMem.ys",     replacements)

    os.makedirs(os.path.dirname(TEMP_CONF.targetPath + "/Contract/YosysScript" + "/DesignHierarchy.ys"), exist_ok=True)
    os.makedirs(os.path.dirname(TEMP_CONF.targetPath + "/Contract/YosysScript" + "/DesignRegMem.ys"), exist_ok=True)
    os.makedirs(os.path.dirname( TEMP_CONF.targetPath + "/Hierarchy/"), exist_ok=True)
 

    with open(TEMP_CONF.targetPath + "/Contract/YosysScript" + "/DesignHierarchy.ys", 'w') as yosys_modified:
        yosys_modified.write(yosys_1)

    with open(TEMP_CONF.targetPath + "/Contract/YosysScript" + "/DesignRegMem.ys", 'w') as yosys_modified:
        yosys_modified.write(yosys_2)


    cmd1 = "yosys -s {}".format(TEMP_CONF.targetPath + "/Contract/YosysScript" + "/DesignHierarchy.ys")
    cmd2 = "yosys -s {}".format(TEMP_CONF.targetPath + "/Contract/YosysScript" + "/DesignRegMem.ys")

    run(cmd1, shell=True)
    run(cmd2, shell=True)
    

    return 0


def YosysContract():

    # TODO: ensure that a static reference to yosys works of we should be smarter 

    """
    This function:
    1) Read the yosys template to generate the miter stuttering circuit
    2) Modify the placeholders in the template with appropriate files 
    3) Run the yosys command to generate the circuit
    """

    # Read Yosys Template
    if (CONF.experimentalParameters["Synch_level"] == "HighLevelClock"):
        with open("script/YosysTemplate/ContractVerification_stalling.ys", 'r') as yosys_template:
            yosys = yosys_template.read()
    else:
        with open("script/YosysTemplate/ContractVerification_stuttering.ys", 'r') as yosys_template:
            yosys = yosys_template.read()

    src_files = os.listdir(CONF.designSrc)

    macro_lst = "".join(f" -D {m} " for m in CONF.designMacro) if CONF.designMacro else ""
    file_lst  = "".join(f"{CONF.designSrc}/{f} " for f in src_files)

    # Order matters: MITER_TOPMODULE must come before TOPMODULE
    replacements = [
        ("YOSYS_PASS_PATH",   "YosysPass/bin"),
        ("MITER_MODULE",   "miter_" + CONF.designTop),
        ("TOPMODULE",         CONF.designTop),
        ("MACRO",             macro_lst),
        ("VERILOG_FILES",     file_lst),
        ("VERILOG_MITER_OUT", CONF.targetPath + "/Contract/Verilog"),
        ("RETIRE_PREDICATE",  "miter_" + CONF.designTop + "." + CONF.contract["retirementPredicate"]["dataSignal"]), 
        ("CLOCK", CONF.microArchitecture["clock"])
    ]

    for placeholder, value in replacements:
        yosys = yosys.replace(placeholder, value)

    os.makedirs(os.path.dirname(CONF.targetPath + "/Contract/Verilog/"), exist_ok=True)


    with open(CONF.targetPath + "/Contract/YosysScript" + "/ContractVerifications.ys", 'w') as yosys_modified:
        yosys_modified.write(yosys)

    # run
    cmd = "yosys -s {}".format(CONF.targetPath + "/Contract/YosysScript" + "/ContractVerifications.ys")

    run(cmd, shell=True)
    
    return 0
