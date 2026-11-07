import optparse
import os
import yaml

# Implementation Import
from configuration import CONF, TEMP_CONF
from subprocess import run


def ContractVerification_SMTBMC():

    # SBY Placeholder
    with open("script/VerificationTemplate/ContractVerification_SMTBMC.sby", 'r') as sby_template:
        sby = sby_template.read()

    os.makedirs(os.path.dirname(CONF.targetPath + "/Verification/SBYScript/"), exist_ok=True)


    replacements = [
        ("MITER_TOP", "miter_" + CONF.designTop),
        ("MODULES", "contractVerification_verilog.v"),
        ("FILEPATH", CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v"),
        ("VERILOG_OUT","contractVerification_rIC3.v"),
    ]

    for placeholder, value in replacements:
        sby = sby.replace(placeholder, value)

    print(sby)
    with open(CONF.targetPath + "/Verification/SBYScript" + "/ContractVerifications.sby", 'w') as sby_modified:
        sby_modified.write(sby)


    # Run Verification

    cmd = "sby -f {}".format(CONF.targetPath + "/Verification/SBYScript" + "/ContractVerifications.sby")

    run(cmd, shell=True)
    

    return 0