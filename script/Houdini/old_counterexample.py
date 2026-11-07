import optparse
import os
import yaml

# Implementation Import
from configuration import CONF, TEMP_CONF
from subprocess import run,  PIPE, STDOUT
from Houdini.utils import fixClock, displayObservations, renameDotNotation, compileWithIVerilog


def counterexampleAnalysis():
    testbed = CONF.targetPath + "/Verification/Houdini/ContractVerifications/engine_0/trace_tb.v"
    verif_status = True
    verif_failed = False

    cmd = [CONF.vvp, testbed]
    # ctx = run_process(cmd, CONF.verbose_counterexample_checking)
    ctx = run(cmd, shell=True, stderr=STDOUT, stdout=PIPE)
    print(f"THEL : {cmd} >>>>>>>>>>> {ctx}")
    cycles = ctx.split(">>>>>")
        
    attacker_obs_signal = []
    attacker_obs_signal.append(elem["dataSignal"] for elem in CONF.AttackerObservations)

    diffcycle = False
    for cycle in cycles:

        if diffcycle:
            break
        else:
            fail_invar = []
            invs = cycle.split("\n")
            for inv in invs:


                tbname = inv.split(" ")
                if (tbname[-1] == "0" or tbname[-1] == "x") and len(tbname) == 2:
                    name = tbname[0].split("_trg")[0].split(".")[-1]

                    if any(attacker_obs_signal in name):
                        # Verif Failed
                        verif_failed = True
                        verif_status = False
                    fail_invar.append(name)
            if len(fail_invar) < 2:
                diffcycle = False
            else:
                diffcycle = True


    return fail_invar, verif_failed


def waveformWorkaround(mode: str):

    counterexample_path = CONF.targetPath + "/Verification/Houdini/ContractVerifications/engine_0/trace_tb.v"
    counterexample_folder = CONF.targetPath + "/Verification/Houdini/ContractVerifications/engine_0"

    # Copy the contract verification design 
    cp_src = CONF.targetPath + "/Verification/Houdini" + f"/contractVerification_{mode}.v"
    cp_dst = counterexample_folder + "/miter_{}.v".format(CONF.designTop)
    cmd = "cp {0} {1}".format(cp_src, cp_dst)
    print(cmd)
    run(cmd, shell=True)

    with open(counterexample_path, 'r') as counterexample:
        counterexample = counterexample.read()

    counterexample_backup = counterexample

    # 1st hack:
    counterexample = fixClock(counterexample)

    # 2nd append display statements to the counterexample
    counterexample = displayObservations(counterexample, predicate_list, "trg", "ASSERT")

    # 3st hack:
    counterexample = renameDotNotation(counterexample)


    with open(counterexample_path, 'w') as mod_counterexample_witness:
        mod_counterexample_witness.write(counterexample)
    
    compileWithIVerilog(counterexample_path, counterexample_folder )
