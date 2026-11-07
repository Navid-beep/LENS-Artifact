


# LENS: Leakage-contract Evaluation and aNalysis Suite

<LENS> is a tool for verifying whether a processor design, written in (System)Verilog, satisfies a given Seq-CT leakage contract.

LENS builds a two-copy product circuit (miter) of the design, assumes the contract, and checks that the attacker observations (commit timing, load addresses, ...) cannot diverge.

**Verification backends**

- **rIC3** in prove mode
- **Houdini**, using either rIC3 in BMC mode or Yosys-SMTBMC with Yices

**Configuration**

YAML files specify the design-specific variables, the contract observations, the attacker observations, and the experimental parameters.

**Output**

- **rIC3** returns either a proof or a counterexample with a witness waveform.
- **Houdini** logs each run, so you can follow its steps and see which invariants are discarded at each iteration.
## Dependencies

- Python 3.8 or higher with PyYAML
- Yosys TODO (developed with 0.60+)
- [yosys-slang](https://github.com/povik/yosys-slang) TODO: version.
- [SBY (SymbiYosys)](https://github.com/YosysHQ/sby)
- rIC3 (https://github.com/gipsyh/rIC3)
- yosys-smtbmc (ships with Yosys) and an SMT solver (yices2 by default; TODO: version), only needed for `Solver: smtbmc`

Everything else the scripts use is part of the Python standard library.

**All tools must be installed system-wide, i.e. reachable from your `PATH`.** The scripts call them by name (`yosys`, `sby`, `rIC3`, `yosys-smtbmc`, `yices-smt2`, `python3`) and not by an absolute path. If a tool lives in a custom location, add its directory to `PATH` before running.

Check that every command resolves from a fresh shell:
 
```bash
yosys -V
yosys -m slang -p "help read_slang"    # yosys-slang plugin loads
sby --help
rIC3 --version
yosys-smtbmc -h                        # only for Solver: smtbmc
yices-smt2 --version                   # only for Solver: smtbmc (or the SMT solver you select)
python3 -c "import yaml"
```
 
If one of these prints `command not found`, the tool is not on your `PATH` and the flow will fail when it reaches that step.

## Compile the Yosys passes first

The tool needs the custom Yosys passes to run properly. 

```bash
cd YosysPass/
mkdir bin
make
```

## Baseline examples

Two examples are provided: `Example_simpleooo.yaml` and `Example_Sodor2_Houdini.yaml`

1. Specify the contract you want to observe.
2. Generate the verilog
Run:
   ```bash
   python3 script/ContractGeneration.py user/configuration/Target.yaml
   ```
For example:
   ```bash
   python3 script/ContractGeneration.py user/configuration/Example_simpleooo.yaml
   ```
4. Start the verification 
Run:
   ```bash
   python3 script/ContractVerification.py user/configuration/Target.yaml
   ```
For example:
   ```bash
   python3 script/ContractVerification.py user/configuration/Example_simpleooo.yaml
   ```
   `TODO: <targetPath>/Verification/Houdini/houdini.log` should end with the verification passing (`PASS`).

Each run writes the following to `<targetPath>/Verification/Houdini/`:

## Reproducing the results from the paper

### RQ-1-3-4

Target (`UASC_*.yaml`) 

1. The contract are already generated in 'results/'

2. Verify the contract.
Run:
   ```bash
   python3 script/ContractVerification.py user/configuration/Target.yaml
   ```
For example:
   ```bash
   python3 script/ContractVerification.py user/configuration/UASC_SOOO_IB_Baseline.yaml
   ```
### RQ-2

Target (`Pitfalls_*.yaml`) 

1. The contract are already generated in 'results/'
2. Verify the contract.
Run:
   ```bash
   python3 script/ContractVerification.py user/configuration/Target.yaml
   ```
For example:
   ```bash
   python3 script/ContractVerification.py user/configuration/Pitfalls_SOOO_IB_CT_MemAddr.yaml
   ```

Note that, in this mode, the tool does not regenerate the Verilog contract specification.
In addition, some configurations evaluated in RQ2 cannot be generated automatically, since they correspond to the pitfalls discussed in the paper.
Supporting all combinations is left as future work.

## Note on Design Hierarchy Resolution

For simple designs such as SimpleOOO, automatic hierarchy resolution completes the signal names in the YAML file with their full paths. This does not yet fully work for more complex designs such as Sodor2, which require you to:

1. Specify the full hierarchical path of every signal in the YAML configuration file.
2. Disable automatic hierarchy resolution with the following flag:

   ```yaml
   experimentalParameters:
     Hierarchy: false
   ```

## Directory structure

```
user/configuration/          example.yaml and one configuration per target
script/          Python script, Yosys and Verilog templates used for contract generation and verification
YosysPasses/     All custom Yosys passes
results/         Contract after generation and Verification results
src/             Processor designs
README.md
```