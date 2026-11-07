import optparse
import os
import yaml
import re

# Implementation Import
from configuration import CONF, TEMP_CONF
from subprocess import run, PIPE

def genVCD():

    cmd = ["cd", CONF.targetPath + "/Verification/SBYScript" + "/ContractVerifications/", ";"]

    cmd.append(["yosys", "-p", "'read_rtlil model/design_prep.il; memory_map -formal; opt_clean; sim -hdlname -r engine_0/trace_aiw.yw -vcd engine_0/trace.vcd' "])

    proc = run(cmd, stdout=PIPE, stderr=PIPE, text=True)

# grep -n memory_map model/design_aiger.ys   # should show memory_map -formal
# yosys -p 'read_rtlil model/design_prep.il; memory_map -formal; opt_clean; \
#           sim -hdlname -r engine_0/trace_aiw.yw -vcd engine_0/trace.vcd'
    return 0


def ContractVerification_rIC3():

    # SBY Placeholder
    with open("script/VerificationTemplate/ContractVerification_rIC3.sby", 'r') as sby_template:
        sby = sby_template.read()

    os.makedirs(os.path.dirname(CONF.targetPath + "/Verification/SBYScript/"), exist_ok=True)

    multi_clk_dom = ""
    if CONF.experimentalParameters["Synch_level"] == "HighLevelClock":
        multi_clk_dom = "multiclock on"

    replacements = [
        ("MITER_TOP", "miter_" + CONF.designTop),
        ("MODULES", "contractVerification_verilog.v"),
        ("FILEPATH", CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v"),
        ("VERILOG_OUT","contractVerification_rIC3.v"),
        ("MULTI_CLOCK_DOMAIN", multi_clk_dom)
    ]

    for placeholder, value in replacements:
        sby = sby.replace(placeholder, value)

    print(sby)
    with open(CONF.targetPath + "/Verification/SBYScript" + "/ContractVerifications.sby", 'w') as sby_modified:
        sby_modified.write(sby)


    # Run Verification

    cmd = "sby -f {}".format(CONF.targetPath + "/Verification/SBYScript" + "/ContractVerifications.sby")
    # cmd = ["sby", "-f", CONF.targetPath + "/Verification/SBYScript" + "/ContractVerifications.sby"]
    
    run(cmd,  shell=True)
    # proc = run(cmd, stdout=PIPE, stderr=PIPE, text=True,  shell=True)
    # log = proc.stdout + proc.stderr
    # status = proc.returncode
    # # 

    # if status == 2 and re.search(r"returned FAIL", log):
    #     genVCD()

    return 0