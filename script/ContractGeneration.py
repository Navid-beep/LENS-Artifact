import optparse
import os
import sys
import yaml

# Implementation Import
from configuration import CONF, TEMP_CONF
from subprocess import run


# Local Import
from VerilogGenerator import ContractGeneration
from HierarchyElaboration import DesignHierarchyGeneration, DesignConfigModification
import YosysTemplate.yosys as yosys_script


# Configurations whose file name starts with one of these prefixes are not allowed to run
BLOCKED_CONFIG_PREFIXES = ("UASC", "Pitfalls")


# def ContractGeneration_main(argv=None):
def ContractGeneration_main():

    # Option & Argument Parser
    parser = optparse.OptionParser()
    parser.add_option('-c', '--congig', help="path to the .yaml configuration file")
    parser.add_option('-v', dest='verbose', action='store_true')
    opts, args = parser.parse_args()

    filelist = args

    for f in filelist:
        if not os.path.exists(f):
            raise IOError("file not found: " + f)

    # --- USER Configuration File Processing ---

    ## Init configuration
    configFile = filelist[0]

    # Block UASC / Pitfalls configurations before anything is created or copied
    config_name = os.path.basename(configFile)
    if config_name.startswith(BLOCKED_CONFIG_PREFIXES):
        print("[ContractGeneration] '{}' starts with {}: contract generation is not "
              "allowed for this configuration. Aborting.".format(
                  config_name, " / ".join(BLOCKED_CONFIG_PREFIXES)))
        return 1

    with open(configFile, "r") as f:
        config_update: dict = yaml.safe_load(f)

    cmd = "mkdir {}".format(config_update["targetPath"])
    run(cmd, shell=True)

    # cmd = "mkdir {}/Configuration".format(config_update["targetPath"])
    # run(cmd, shell=True)


    configuration_path = "{}/Configuration/configuration.yaml".format(config_update["targetPath"])

    os.makedirs(os.path.dirname(configuration_path), exist_ok=True)

    cmd = "cp {} {}".format(configFile, configuration_path)
    print(cmd)
    run(cmd, shell=True)

    for var, value in config_update.items():
        TEMP_CONF.set(var, value)


    with open(configuration_path, "r") as f:
        config_update: dict = yaml.safe_load(f)

    # ------------------Hierarchy Generation-----------------------

    # Processing the Design to extract the Hierarchy & new Config File
    yosys_script.Hierarchy()

    if (TEMP_CONF.experimentalParameters["Hierarchy"]):
        DesignHierarchyGeneration(configuration_path)

    else:
        DesignConfigModification(configuration_path)

    # open new configuration
    with open(configuration_path, "r") as f:
        config_update: dict = yaml.safe_load(f)

    for var, value in config_update.items():
        CONF.set(var, value)

    ContractGeneration()

    return 0

if __name__ == "__main__":
    sys.exit(ContractGeneration_main())

# import optparse
# import os
# import yaml

# # Implementation Import
# from configuration import CONF, TEMP_CONF
# from subprocess import run


# # Local Import
# from VerilogGenerator import ContractGeneration
# from HierarchyElaboration import DesignHierarchyGeneration, DesignConfigModification
# import YosysTemplate.yosys as yosys_script


# # def ContractGeneration_main(argv=None):
# def ContractGeneration_main():

#     # Option & Argument Parser
#     parser = optparse.OptionParser()
#     parser.add_option('-c', '--congig', help="path to the .yaml configuration file")
#     parser.add_option('-v', dest='verbose', action='store_true')
#     opts, args = parser.parse_args()

#     filelist = args

#     for f in filelist:
#         if not os.path.exists(f):
#             raise IOError("file not found: " + f)

#     # --- USER Configuration File Processing ---

#     ## Init configuration
#     configFile = filelist[0]

#     with open(configFile, "r") as f:
#         config_update: dict = yaml.safe_load(f)

#     cmd = "mkdir {}".format(config_update["targetPath"])
#     run(cmd, shell=True)

#     # cmd = "mkdir {}/Configuration".format(config_update["targetPath"])
#     # run(cmd, shell=True)


#     configuration_path = "{}/Configuration/configuration.yaml".format(config_update["targetPath"])

#     os.makedirs(os.path.dirname(configuration_path), exist_ok=True)
 
#     cmd = "cp {} {}".format(configFile, configuration_path)
#     print(cmd)
#     run(cmd, shell=True)

#     for var, value in config_update.items():
#         TEMP_CONF.set(var, value)


#     with open(configuration_path, "r") as f:
#         config_update: dict = yaml.safe_load(f)

#     # ------------------Hierarchy Generation-----------------------

#     # Processing the Design to extract the Hierarchy & new Config File
#     # TODO: Fix the dep issues + memory issues + multi-instances issues (a lot of issues...)
#     yosys_script.Hierarchy()

#     if (TEMP_CONF.experimentalParameters["Hierarchy"]):
#         DesignHierarchyGeneration(configuration_path)

#     else:
#         DesignConfigModification(configuration_path)

#     # open new configuration
#     with open(configuration_path, "r") as f:
#         config_update: dict = yaml.safe_load(f)

#     for var, value in config_update.items():
#         CONF.set(var, value)

#     ContractGeneration()

#     return 0

# if __name__ == "__main__":
#     ContractGeneration_main()