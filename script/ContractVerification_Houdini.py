import csv
import logging
import os
import re
import time

# Implementation Import
from configuration import CONF
from subprocess import run
from Houdini.generateVerilog import predicateInitBase, addPredicateVerilog
from Houdini.counterexample import cexAnalysis, solver_name

TEMPLATE_DIR = "script/VerificationTemplate"

# Solver selection (CONF.experimentalParameters):
#   Solver:        "rIC3" (default) or "smtbmc"
#   SMTSolver:     SMT solver passed to yosys-smtbmc -s       (default "yices")
#   SMTBMCPath:    yosys-smtbmc executable                     (default "yosys-smtbmc")
#   SMTBMCOptions: extra yosys-smtbmc flags, as one string     (default "")

log = logging.getLogger("houdini")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def houdini_dir():
    return CONF.targetPath + "/Verification/Houdini"


def mode_base(mode: str):
    # Prefix shared by every per-mode artefact: _memmapped.v, _all_pred.il, .aig, .aiw, .vcd ...
    return houdini_dir() + "/contract_memory_{}".format(mode)


def sh(cmd: str, quiet: bool = False):
    """Run a shell command and stop on failure, so a broken step never leaves stale files behind."""
    r = run(cmd, shell=True, capture_output=quiet, text=True)
    if r.returncode != 0:
        if quiet:
            print(r.stdout[-4000:])
            print(r.stderr[-4000:])
        raise RuntimeError("command failed ({0}): {1}".format(r.returncode, cmd))
    return r


def fill_template(template: str, out_name: str, replacements: list):
    with open(TEMPLATE_DIR + "/" + template, "r") as f:
        text = f.read()
    for placeholder, value in replacements:
        text = text.replace(placeholder, value)
    out_path = houdini_dir() + "/" + out_name
    with open(out_path, "w") as f:
        f.write(text)
    return out_path


def remove(*paths):
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


# ----------------------------------------------------------------------------
# Logging and timing
# ----------------------------------------------------------------------------

TIMING_FIELDS = ["mode", "iteration", "design_s", "verification_s", "cex_analysis_s",
                 "total_s", "result", "dropped_now", "dropped_total"]


def setup_logging():
    """Log to the console and to <houdini_dir>/houdini.log (overwritten at each run)."""
    os.makedirs(houdini_dir(), exist_ok=True)
    log.setLevel(logging.INFO)
    log.propagate = False
    for h in list(log.handlers):
        log.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logfile = logging.FileHandler(houdini_dir() + "/houdini.log", mode="w")
    logfile.setFormatter(fmt)
    log.addHandler(console)
    log.addHandler(logfile)

    # one row per iteration, written as soon as the iteration ends (kept even if the run stops)
    with open(timing_csv(), "w", newline="") as f:
        csv.writer(f).writerow(TIMING_FIELDS)


def timing_csv():
    return houdini_dir() + "/houdini_timing.csv"


class Stopwatch:
    """with Stopwatch() as sw: ...   ->   sw.elapsed (seconds)"""
    def __enter__(self):
        self.start = time.perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - self.start
        return False


def record_iteration(mode, iteration, t_design, t_verif, t_cex, result, dropped_now, dropped_total, totals):
    total = t_design + t_verif + t_cex
    log.info("[%s] iteration %d: design %.2f s | verification %.2f s | cex analysis %.2f s | "
             "total %.2f s | %s | dropped %d (%d in total)",
             mode, iteration, t_design, t_verif, t_cex, total, result, dropped_now, dropped_total)
    with open(timing_csv(), "a", newline="") as f:
        csv.writer(f).writerow([mode, iteration, "{:.3f}".format(t_design), "{:.3f}".format(t_verif),
                                "{:.3f}".format(t_cex), "{:.3f}".format(total), result,
                                dropped_now, dropped_total])
    totals["design"] += t_design
    totals["verification"] += t_verif
    totals["cex"] += t_cex
    totals["iterations"] = iteration


def log_summary(mode, t_prep, totals):
    log.info("[%s] summary: %d iteration(s) | design preparation (once) %.2f s | "
             "design per iteration %.2f s | verification %.2f s | cex analysis %.2f s | total %.2f s",
             mode, totals["iterations"], t_prep, totals["design"], totals["verification"], totals["cex"],
             t_prep + totals["design"] + totals["verification"] + totals["cex"])


# ----------------------------------------------------------------------------
# One-time steps
# ----------------------------------------------------------------------------

def extractPredicate():
    os.makedirs(houdini_dir(), exist_ok=True)
    path = fill_template("ContractVerification_Houdini_Predicate.ys",
                         "ContractVerification_Houdini_Predicate.ys", [
        ("TOPMODULE",         CONF.designTop),
        ("VERILOG_MITER_OUT", CONF.targetPath + "/Contract/Verilog"),
        ("VERIFICATION_PATH", houdini_dir()),
        ("YOSYS_PASS_PATH",   "YosysPass/bin"),
    ])
    remove(houdini_dir() + "/regs_mems.dat")
    sh("yosys -s {}".format(path), quiet=True)
    return 0


def prepYosys(mode: str):
    """Run once per mode, then snapshot the netlist as RTLIL; every Houdini iteration starts from the snapshot.
      rIC3:   flatten + memory_map (slang) -> _memmapped.v -> Snapshot.ys -> <mode_base>_all_pred.il
      smtbmc: flatten, memories KEPT as arrays (write_smt2 supports them) -> <mode_base>_all_pred_smt.il"""

    module = "contractVerification_{}.v".format(mode)
    repl = [
        ("MITER_TOP",          "miter_" + CONF.designTop),
        ("MODULES",            module),
        ("FILEPATH",           houdini_dir() + "/" + module),
        ("VERILOG_OUT",        "contractVerification_Houdini.v"),
        ("CONTRACT_NAME_MODE", mode_base(mode)),
    ]

    if solver_name() == "smtbmc":
        remove(mode_base(mode) + "_all_pred_smt.il")
        path = fill_template("ContractVerification_Houdini_smt.ys", "ContractVerifications_{}_smt.ys".format(mode), repl)
        sh("yosys -q -s {}".format(path))
        return

    remove(mode_base(mode) + "_memmapped.v", mode_base(mode) + "_all_pred.il")

    path = fill_template("ContractVerification_Houdini.ys", "ContractVerifications_{}.ys".format(mode), repl)
    sh("yosys -q -s {}".format(path))

    path = fill_template("Snapshot.ys", "Snapshot_{}.ys".format(mode), repl)
    sh("yosys -q -s {}".format(path))


def bmc_depth(mode:str):

    if mode == "base":
        depth = CONF.experimentalParameters["k"] + CONF.microArchitecture["ROB"]["lookahead"]

    else:
        depth = CONF.experimentalParameters["k"] + CONF.microArchitecture["ROB"]["lookahead"] + 1

    return depth


def check_depth(mode:str):
    """With BMC, a counterexample deeper than --end is never found and the run reports a pass.
    The assertion only fails `bound` cycles after state_trg_equiv drops, so warn if the depth is too short."""
    with open(CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v", "r") as f:
        m = re.search(r"reg\s*\[[^\]]*\]\s*bound\s*=\s*(\d+)", f.read())
    if m is None:
        return
    # rIC3 --end N checks steps 0..N; yosys-smtbmc is run with -t N+1, which checks the same steps 0..N.
    # Earliest failing step: k + bound (base), k + bound + 1 (inductive)
    needed = CONF.experimentalParameters["k"] + int(m.group(1)) + (1 if mode == "inductive" else 0)
    if bmc_depth(mode) < needed:
        log.warning("WARNING: [%s] BMC depth %d < %d (earliest failing step); deeper counterexamples are "
                    "missed and reported as passes.", mode, bmc_depth(mode), needed)


# ----------------------------------------------------------------------------
# Per-iteration steps
# ----------------------------------------------------------------------------

def buildAig(mode: str, dropped: set):
    """Tie every dropped predicate to 1 on the snapshot, then write the AIG (and pre_aiger.il for VCD replay)."""
    deviation = "".join(
        "select -assert-count 1 w:{0}\nconnect -set {0} 1'b1\n".format(p) for p in sorted(dropped))

    remove(mode_base(mode) + ".aig", mode_base(mode) + ".ywa", mode_base(mode) + "_pre_aiger.il")
    path = fill_template("Iterate.ys", "Iterate_{}.ys".format(mode), [
        ("MITER_TOP",           "miter_" + CONF.designTop),
        ("CONTRACT_NAME_MODE",  mode_base(mode)),
        ("PREDICATE_DEVIATION", deviation),
    ])
    sh("yosys -q -s {}".format(path))


def runRic3(mode: str):
    """Return "CEX" or "PASS". Line [1] of the witness: 1 = counterexample, 2 = none within the bound, 0 = safe."""
    aiw = mode_base(mode) + ".aiw"
    remove(aiw)

    cmd = "rIC3 -e bmc --end {0} --witness {1}.aig > {2}".format(bmc_depth(mode), mode_base(mode), aiw)
    log.info("[%s] %s", mode, cmd)
    run(cmd, shell=True)            # rIC3's exit code encodes the result, so it is not checked here

    with open(aiw, "r") as f:
        output = f.readlines()
    if len(output) < 2:
        raise RuntimeError("rIC3 produced no result in " + aiw)

    result = output[1].strip()
    if "1" in result:
        return "CEX"
    if "2" in result or result == "0":
        return "PASS"
    raise RuntimeError("unexpected rIC3 result line: " + output[1])


def buildSmt2(mode: str, dropped: set):
    """Tie every dropped predicate to 1 on the snapshot, then write <mode_base>.smt2 for yosys-smtbmc."""
    deviation = "".join(
        "select -assert-count 1 w:{0}\nconnect -set {0} 1'b1\n".format(p) for p in sorted(dropped))

    remove(mode_base(mode) + ".smt2")
    path = fill_template("Iterate_smt.ys", "Iterate_{}_smt.ys".format(mode), [
        ("MITER_TOP",           "miter_" + CONF.designTop),
        ("CONTRACT_NAME_MODE",  mode_base(mode)),
        ("PREDICATE_DEVIATION", deviation),
    ])
    sh("yosys -q -s {}".format(path))


def runSmtbmc(mode: str):
    """Return "CEX" or "PASS". The counterexample VCD is written directly to <mode_base>.vcd
    (no witness conversion), and the solver output to <mode_base>_smtbmc.log."""
    p = CONF.experimentalParameters
    vcd = mode_base(mode) + ".vcd"
    out_log = mode_base(mode) + "_smtbmc.log"
    remove(vcd, out_log)

    steps = bmc_depth(mode) + 1          # -t N checks steps 0..N-1, i.e. the same steps as rIC3 --end N-1
    cmd = "{0} -s {1} -t {2} --presat {3} --dump-vcd {4} {5}.smt2".format(
        p.get("SMTBMCPath", "yosys-smtbmc"), p.get("SMTSolver", "yices"), steps,
        p.get("SMTBMCOptions", ""), vcd, mode_base(mode))
    log.info("[%s] %s", mode, cmd)
    # progress ("Checking assertions in step N..") is shown live in the terminal and copied to out_log
    r = run("{0} 2>&1 | tee {1}".format(cmd, out_log), shell=True)
    with open(out_log, "r") as f:
        output = f.read()

    if "Assumptions are unsatisfiable" in output or "Status: PREUNSAT" in output:
        raise RuntimeError("yosys-smtbmc: the assumptions are unsatisfiable, the check would be vacuous "
                           "(see {})".format(out_log))
    if "Status: PASSED" in output:
        return "PASS"
    if "Status: FAILED" in output:
        if not os.path.exists(vcd):
            raise RuntimeError("yosys-smtbmc reported a failure but wrote no VCD: " + vcd)
        return "CEX"
    raise RuntimeError("unexpected yosys-smtbmc result (exit code {0}), see {1}".format(r.returncode, out_log))


def buildDesign(mode: str, dropped: set):
    if solver_name() == "smtbmc":
        buildSmt2(mode, dropped)
    else:
        buildAig(mode, dropped)


def runSolver(mode: str):
    return runSmtbmc(mode) if solver_name() == "smtbmc" else runRic3(mode)


def houdini_loop(mode: str, dropped: set, stats: dict):
    """Drop failing predicates until the case passes. `dropped` is shared between the cases and updated in place.
    Per iteration, times: design processing (Iterate.ys -> AIG, or Iterate_smt.ys -> SMT2), verification
    (rIC3 or yosys-smtbmc) and counterexample analysis (witness -> VCD, or smtbmc's VCD -> predicates).
    stats[mode] receives the case's wall-clock time, iteration count and outcome."""
    t_case = time.perf_counter()
    stats[mode] = {"time": 0.0, "iterations": 0, "outcome": "running"}
    with Stopwatch() as sw:
        prepYosys(mode)
    t_prep = sw.elapsed
    log.info("[%s] design preparation (slang + flatten + snapshot, once): %.2f s", mode, t_prep)

    totals = {"design": 0.0, "verification": 0.0, "cex": 0.0, "iterations": 0}
    iteration = 0

    try:
        while True:
            iteration += 1

            # 1) design processing
            with Stopwatch() as sw:
                buildDesign(mode, dropped)
            t_design = sw.elapsed

            # 2) verification
            with Stopwatch() as sw:
                result = runSolver(mode)
            t_verif = sw.elapsed

            if result == "PASS":
                record_iteration(mode, iteration, t_design, t_verif, 0.0, "PASS", 0, len(dropped), totals)
                log.info("[%s] passed after %d iteration(s), %d predicates dropped in total",
                         mode, iteration, len(dropped))
                stats[mode]["outcome"] = "PASS"
                return

            # 3) counterexample analysis
            with Stopwatch() as sw:
                new, status = cexAnalysis(mode)
            t_cex = sw.elapsed

            if status == "FAILED":
                record_iteration(mode, iteration, t_design, t_verif, t_cex, "FAILED", 0, len(dropped), totals)
                stats[mode]["outcome"] = "FAILED"
                raise Exception("Verification Failed ({} case): commits deviate while every predicate holds.".format(mode))

            new -= dropped
            if not new:
                record_iteration(mode, iteration, t_design, t_verif, t_cex, "UNKNOWN", 0, len(dropped), totals)
                stats[mode]["outcome"] = "UNKNOWN"
                raise Exception("Verification Unknown ({} case): counterexample but no new predicate to drop.".format(mode))

            dropped |= new
            record_iteration(mode, iteration, t_design, t_verif, t_cex, "CEX", len(new), len(dropped), totals)

    finally:
        log_summary(mode, t_prep, totals)       # also written when the case stops with an exception
        stats[mode]["time"] = time.perf_counter() - t_case
        stats[mode]["iterations"] = totals["iterations"]
        if stats[mode]["outcome"] == "running":
            stats[mode]["outcome"] = "ERROR"     # stopped by an unexpected exception (tool failure, ...)
        log.info("[%s] total time for the %s case: %.2f s", mode, mode, stats[mode]["time"])


def log_final_summary(t_setup, stats, t_total):
    """Final timing block, also written to <houdini_dir>/houdini_timing_summary.txt."""
    lines = ["===== Houdini timing summary =====",
             "setup (predicate extraction + miter generation): {:.2f} s".format(t_setup)]
    for mode in ("base", "inductive"):
        if mode in stats:
            s = stats[mode]
            lines.append("{0} case: {1:.2f} s ({2} iteration(s), {3})".format(
                mode, s["time"], s["iterations"], s["outcome"]))
        else:
            lines.append("{0} case: not run".format(mode))
    lines.append("whole verification: {:.2f} s".format(t_total))
    lines.append("per-iteration timings: {}".format(timing_csv()))
    for l in lines:
        log.info(l)
    with open(houdini_dir() + "/houdini_timing_summary.txt", "w") as f:
        f.write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def ContractVerification_Houdini():

    setup_logging()
    t_start = time.perf_counter()
    log.info("solver: %s", solver_name() if solver_name() == "rIC3" else "yosys-smtbmc ({})".format(
        CONF.experimentalParameters.get("SMTSolver", "yices")))

    # Registers / memories of the single design -> regs_mems.dat
    with Stopwatch() as sw:
        extractPredicate()
    log.info("predicate extraction (show_regs_mems): %.2f s", sw.elapsed)

    # Both cases get the FULL predicate set; dropped predicates are tied to 1 in Iterate.ys
    with Stopwatch() as sw:
        predicate_expr, predicate_list = predicateInitBase()      # writes contractVerification_base.v
        addPredicateVerilog(predicate_expr, "inductive")          # writes contractVerification_inductive.v
    log.info("%d candidate predicates; miter generation: %.2f s", len(predicate_list), sw.elapsed)

    check_depth("base")
    check_depth("inductive")

    t_setup = time.perf_counter() - t_start
    dropped = set()
    stats = {}

    try:
        # BASE: once it passes it is never re-run. Removing predicates only weakens
        # trg_equiv, so the base obligation stays satisfied.
        houdini_loop("base", dropped, stats)
        log.info("Passed base case.")

        # INDUCTIVE
        houdini_loop("inductive", dropped, stats)
        log.info("Passed inductive case.")
    finally:
        log_final_summary(t_setup, stats, time.perf_counter() - t_start)

    kept = [p for p in predicate_list if p not in dropped]
    with open(houdini_dir() + "/invariants.txt", "w") as f:
        f.write("\n".join(kept) + "\n")
    log.info("%d invariants kept -> %s/invariants.txt", len(kept), houdini_dir())

    return 0
