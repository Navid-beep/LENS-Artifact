# Most in not all function from this file are copied from LeaVe

import re
import optparse
import os
import yaml

# Implementation Import
from configuration import CONF
from subprocess import run,  PIPE, STDOUT

def compileWithIVerilog(file,outFolder):
    cmd = [CONF.iverilogPath]
    cmd.append("-gno-assertions")
    cmd.append("-g2005-sv")
    cmd.append("-o {}/{}".format(outFolder, "trace_tb.v".replace(".v","")))
    cmd.append(f"-I {outFolder}")
    cmd.append(f"-y {outFolder}")
    cmd.append(file)

    print(" ".join(cmd))
    output = run(cmd, shell=True, stderr=STDOUT, stdout=PIPE)
    # if "error" in output:
    #     print("Errors during counterexample compilation!")
    #     exit(1)
    return "{}/{}".format(outFolder, "trace_tb.v".replace(".v",""))
    

def fixClock(verilog_tb: str):

    code = verilog_tb

    testbed_clock = "PI_"+ CONF.microArchitecture["clock"]

    if f"wire [0:0] {testbed_clock} = clock;" not in code:
        ## yosys-smtbmc messed up, we need to fix it :-|
        code = code.replace(f".{CONF.microArchitecture["clock"]}({testbed_clock})", f".{CONF.microArchitecture["clock"]}(clock)")

        print("Fixed clock signal")
    else:
        print("Yosys-smtbmc correctly assigned the clock signal")

    return code

def rename(id_):
    # print("id_: ", id_)
    renamed = "renamed_"+id_.replace(".","__").replace("[","___").replace("]","").replace("\\","").replace(" ","")#.replace("$","").replace("/","").replace(":","")
    # if renamed.find("$func$") != -1:
    #     print("-renamed-: ", renamed)
    return renamed


def renameDotNotation(verilog_tb: str):

    code = verilog_tb

    #1) find all occurrences of . notation

    #ids = re.findall('UUT\.([A-Za-z0-9_\.\\]*)(\[[A-Za-z0-9\']*\])?[A-Za-z0-9_\.\\\\]*', code)
    ids = re.findall('UUT\.(left\.[A-Za-z0-9_\.\\\\$/;]*)(?:\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)? =', code)  
    ids += re.findall('UUT\.(right\.[A-Za-z0-9_\.\\\\$/;]*)(?:\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)? =', code)

    ids_auto = re.findall('UUT\.(left\.[A-Za-z0-9_\.$/;]*)(\\\\[A-Za-z_\.]*\[[A-Za-z0-9\']*\] )([A-Za-z0-9_\.\\\\]*)? =', code)
    ids_auto += re.findall('UUT\.(right\.[A-Za-z0-9_\.$/;]*)(\\\\[A-Za-z_\.]*\[[A-Za-z0-9\']*\] )([A-Za-z0-9_\.\\\\]*)? =', code)

    # rename the variables defined in the prod.v start with "\\"
    namedArrays = re.findall('UUT\.(\\\\[A-Za-z0-9_\.\\\\$/;]*)(\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)?', code)
    # currently yosys puts two spaces before the assignment whenever the [..] is used as part of an identifier :-\
    namedArrays += re.findall('UUT\.(left\.\\\\[A-Za-z0-9_\.\\\\$/;]*)(\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)?  =', code)  # UUT.left.\IACK_reg[7]  =
    namedArrays += re.findall('UUT\.(right\.\\\\[A-Za-z0-9_\.\\\\$/;]*)(\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)?  =', code)
    
    namedArrays += re.findall('UUT\.(left\.[A-Za-z0-9_\.\\\\$/;]*)(\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)?  =', code)  # UUT.left.\IACK_reg[7]  =
    namedArrays += re.findall('UUT\.(right\.[A-Za-z0-9_\.\\\\$/;]*)(\[[A-Za-z0-9\']*\])?([A-Za-z0-9_\.\\\\]*)?  =', code)

    ids+=ids_auto
    ids+=namedArrays

    
    ids.sort(reverse=True,key=lambda id_: len(id_[0]+id_[1]) )
    list(set(ids))

    for id_ in ids:

        if id_ in namedArrays:
            id_ = id_[0] + id_[1] +id_[2]
            code = code.replace("UUT."+id_, "UUT."+rename(id_))
        elif id_ in ids_auto:
            id_ = id_[0] + id_[1] +id_[2]
            code = code.replace("UUT."+id_, "UUT."+rename(id_))
        else:
            id_ = id_[0] + id_[1]
            code = code.replace("UUT."+id_, "UUT."+rename(id_))

    return code

    


def displayObservations(counterexample, obsDict, prodType, keyword):
    # Some default parameters

    yosysCtxCycle = "cycle"
    yosysCtxClock = "clock"
    yosysCtxUUT = "UUT"
    yosysCtxDisplayAtEdge = True


    debug = True
    if len(obsDict) > 0:
        code = counterexample
        if yosysCtxDisplayAtEdge:
            displayObs = f"\talways @(posedge {yosysCtxClock}) begin\n"
        else:
            displayObs = f"\talways @* begin\n"
        displayObs += f"\t\t$display(\">>>>> CYCLE %0d -- {keyword}\", {yosysCtxCycle});\n"
        for obsId in obsDict:
            displayObs += f"\t\t $display(\"{yosysCtxUUT}.{obsId} %b\", {yosysCtxUUT}.{obsId});\n"
        displayObs += f"\t\t$display(\"{yosysCtxUUT}.{prodType}_equiv %b\", {yosysCtxUUT}.{prodType}_equiv);\n"
        if debug:
            for obsId in obsDict:
                displayObs += f"\t\t$display(\">>> {obsId}\");\n"
                # for obs in obsDict[obsId]:
                # var = obs.get("var")
                displayObs += f"\t\t$display(\"{obsId} %b =?= %b\", {yosysCtxUUT}.gold.{obsId},  {yosysCtxUUT}.gate.{obsId});\n"
        displayObs += "\tend\n"
        displayObs += "endmodule\n"

        code = code.replace("endmodule", displayObs)
    return code