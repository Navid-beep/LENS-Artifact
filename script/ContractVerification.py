import optparse
import os
import yaml

# Implementation Import
from configuration import CONF, TEMP_CONF
from subprocess import run


# Local Import
import ContractVerification_rIC3 as rIC3
# import ContractVerification_SMTBMC as SMTBMC
# import ContractVerification_AVR as AVR
import ContractVerification_Houdini as Houdini


def generate_vcd_rIC3():
    """
    Convert the rIC3 counterexample (AIGER witness) into a VCD trace.

    Runs, inside results/<targetPath>/Verification/SBYScript/ContractVerifications:
        yosys-witness aiw2yw engine_0/trace.aiw model/design_aiger.ywa engine_0/trace_aiw.yw
        yosys -p 'read_rtlil model/design_prep.il; memory_map -formal; opt_clean;
                  sim -hdlname -r engine_0/trace_aiw.yw -vcd engine_0/trace.vcd'
    """
    target = CONF.targetPath
    # avoid "results/results/..." if targetPath already starts with results/
    if os.path.normpath(target).split(os.sep)[0] != "results":
        target = os.path.join("results", target)
    work_dir = os.path.join(target, "Verification", "SBYScript", "ContractVerifications")

    if not os.path.isdir(work_dir):
        print("[VCD] Directory not found: {}".format(work_dir))
        return 1

    trace_aiw = os.path.join(work_dir, "engine_0", "trace.aiw")
    if not os.path.isfile(trace_aiw):
        print("[VCD] No counterexample found ({} missing): nothing to convert.".format(trace_aiw))
        return 1

    commands = [
        ["yosys-witness", "aiw2yw",
         "engine_0/trace.aiw", "model/design_aiger.ywa", "engine_0/trace_aiw.yw"],
        ["yosys", "-p",
         "read_rtlil model/design_prep.il; memory_map -formal; opt_clean; "
         "sim -hdlname -r engine_0/trace_aiw.yw -vcd engine_0/trace.vcd"],
    ]

    for cmd in commands:
        print("[VCD] ({}) {}".format(work_dir, " ".join(cmd)))
        result = run(cmd, cwd=work_dir)
        if result.returncode != 0:
            print("[VCD] Command failed with exit code {}".format(result.returncode))
            return result.returncode

    print("[VCD] Trace written to {}".format(os.path.join(work_dir, "engine_0", "trace.vcd")))
    return 0


# def ContractGeneration_main(argv=None):
def ContractGeneration_main():

    # Option & Argument Parser
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config', help="path to the .yaml configuration file")
    parser.add_option('-v', dest='verbose', action='store_true')
    parser.add_option('--VCD', dest='vcd', action='store_true', default=False,
                      help="(rIC3 only) convert the counterexample trace to engine_0/trace.vcd")
    opts, args = parser.parse_args()

    filelist = args

    for f in filelist:
        if not os.path.exists(f):
            raise IOError("file not found: " + f)

    # --- USER Configuration File Processing ---

    ## Init configuration
    configFile = filelist[0]

    with open(configFile, "r") as f:
        config_update: dict = yaml.safe_load(f)

    configuration_path = "{}/Configuration/configuration.yaml".format(config_update["targetPath"])

    # TODO: Safeguard if the configuration_path is not present yet (i.e. run first the contract generation)


    with open(configuration_path, "r") as f:
        config_update: dict = yaml.safe_load(f)

    for var, value in config_update.items():
        CONF.set(var, value)

    verifier = CONF.experimentalParameters["Verification"]

    if opts.vcd and verifier != "rIC3":
        print("[VCD] --VCD is only supported with rIC3 (current: {}); ignored.".format(verifier))

    match verifier:
        case "Houdini":
            Houdini.ContractVerification_Houdini()

        case "rIC3":
            rIC3.ContractVerification_rIC3()
            if opts.vcd:
                generate_vcd_rIC3()

    return 0


if __name__ == "__main__":
    ContractGeneration_main()
