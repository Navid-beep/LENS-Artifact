## Config
class Configuration:

    # input/output information
    designSrc: str = "" # folder with Verilog sources
    targetPath: str = "" # target folder for intermediate data
    # prodCircuitTemplate: str = ""
    clockInput: str = ""
    initRegister: str = ""

    # Design Description
    designTop: str = ""

    # Processing Tool
    yosysPath: str = ""

    # Solver
    hhoudiniPath: str = ""
    avrPath: str = ""
    ric3Path: str = ""

    vvp: str = "vvp"
    iverilogPath: str = "iverilog"
    # Experimental 
    experimentalParameters  = {}


    # Simulation Tool
    verilatorPath: str = ""

    # Instruction Set
    instructionSet = str = ""

    # Instruction Memory
    microArchitecture = {}

    designMacro = []

    contract = {}

    functionalInvariant = []

    # Simulation files
    programFile = str = "positiveExample.mem"
    secretAddressFile = str = "secret.mem"

    # output
    outputformat = ""

    # observations
    contractObservation = []
    AttackerObservations = []

    #predicates
    predicateRetire = []
    
    # index metavariables
    metaVars = []

    # preprocessing
    Unpacked2PackMem = []

    verbose_preprocessing = True
    verbose_verification = True
    verbose_counterexample_checking = True
    verbose_external_processes = True

    def set(self, name, value):

        if self.__getattribute__(name) is None:
            raise ValueError(f"Unknown configuration variable: {name}")

        if type(self.__getattribute__(name)) != type(value):
            raise ValueError(f"Configuration variable {name} is not correctly set")

        self.__setattr__(name, value)

CONF = Configuration()
TEMP_CONF = Configuration()