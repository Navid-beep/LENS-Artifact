import re
import json
import os

# Implementation Import
from configuration import CONF
from subprocess import run


def sh(cmd: str):
    run(cmd, shell=True, check=True)


def solver_name():
    """CONF.experimentalParameters["Solver"]: "rIC3" (default) or "smtbmc" (yosys-smtbmc)."""
    s = str(CONF.experimentalParameters.get("Solver", "rIC3")).strip().lower()
    if s == "ric3":
        return "rIC3"
    if s in ("smtbmc", "yosys-smtbmc"):
        return "smtbmc"
    raise ValueError("unknown Solver '{}' (expected rIC3 or smtbmc)".format(s))


def mode_base(mode: str):
    return CONF.targetPath + "/Verification/Houdini/contract_memory_{}".format(mode)


def makeVCD(mode: str):
    """Witness (.aiw) -> .yw -> replay on <mode>_pre_aiger.il -> <mode>.vcd"""
    base = mode_base(mode)

    with open("script/YosysTemplate/GenerateVCD.ys", "r") as f:
        ys = f.read()
    ys = ys.replace("CONTRACT_NAME_MODE", base).replace("CONTRACT_PATH", base)

    ys_path = CONF.targetPath + "/Verification/Houdini/GenerateVCD_{}.ys".format(mode)
    with open(ys_path, "w") as f:
        f.write(ys)

    # Drop rIC3's first stdout line. Written to a separate file so a re-run never removes a second line.
    with open(base + ".aiw", "r") as f:
        lines = f.readlines()
    with open(base + "_clean.aiw", "w") as f:
        f.writelines(lines[1:])

    for p in (base + "_aiw.yw", base + ".vcd"):
        if os.path.exists(p):
            os.remove(p)

    sh("yosys-witness aiw2yw {0}_clean.aiw {0}.ywa {0}_aiw.yw".format(base))
    sh("yosys -q -s {}".format(ys_path))


# Deviation signals: the attacker-observation terms of `wire trg_equiv = ... ;` in the miter. Each is 1 when
# gold and gate agree. They are read from the trg_equiv expression itself, so adding an observation to the
# contract (e.g. `ld_addr_deviation`) needs no change here: every identifier of trg_equiv whose name contains
# CONF.experimentalParameters["DeviationPattern"] (default "_dev") is a deviation signal.
# CONF.experimentalParameters["DeviationSignals"] = [names] overrides the detection.
# LEGACY_DEVIATIONS is only used when the miter has no trg_equiv line.
LEGACY_DEVIATIONS = ("commit_deviation", "addr_deviation")
DEVIATIONS = None           # None: detect from trg_equiv
CONJ = "pred_conjunction"
STEP_PERIOD = 10        # default: yosys sim writes one clock cycle = 10 time units (#0, #5, #10, ...);
                        # the actual period is detected from each VCD (yosys-smtbmc may use another time scale)

_IDENT = re.compile(r"\\\S+|[A-Za-z_][A-Za-z0-9_$]*")
_dev_cache = {}


def _trg_equiv_expr(mode):
    """Right-hand side of `wire trg_equiv = ... ;` (may span several lines), from the miter used for `mode`."""
    paths = [CONF.targetPath + "/Verification/Houdini/contractVerification_{}.v".format(mode),
             CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v"]
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", errors="replace") as f:
            text = f.read()
        m = re.search(r"\bwire\s+trg_equiv\s*=\s*(.*?);", text, re.S)
        if m:
            return m.group(1), path
    return None, None


def deviation_signals(mode):
    """Deviation signals of the miter for `mode`, in trg_equiv order (cached per mode)."""
    if mode in _dev_cache:
        return _dev_cache[mode]

    override = CONF.experimentalParameters.get("DeviationSignals")
    if override:
        devs = tuple(str(d).strip() for d in override)
        print("[{0}] deviation signals (DeviationSignals): {1}".format(mode, ", ".join(devs)))
        _dev_cache[mode] = devs
        return devs

    expr, path = _trg_equiv_expr(mode)
    if expr is None:
        print("WARNING: [{0}] no 'wire trg_equiv = ...;' found; using {1}".format(mode, ", ".join(LEGACY_DEVIATIONS)))
        _dev_cache[mode] = LEGACY_DEVIATIONS
        return LEGACY_DEVIATIONS

    pattern = str(CONF.experimentalParameters.get("DeviationPattern", "_dev"))
    devs, other = [], []
    for tok in _IDENT.findall(expr):
        name = tok.lstrip("\\")
        if name == CONJ or name.endswith("_predicate") or name in devs or name in other:
            continue
        (devs if pattern in name else other).append(name)

    if not devs:
        raise RuntimeError("[{0}] trg_equiv in {1} has no term containing '{2}': no deviation can be detected "
                           "(trg_equiv = {3})".format(mode, path, pattern, " ".join(expr.split())))
    print("[{0}] deviation signals from trg_equiv: {1}".format(mode, ", ".join(devs)))
    if other:
        print("WARNING: [{0}] trg_equiv term(s) not treated as deviations (no '{1}' in the name): {2}"
              .format(mode, pattern, ", ".join(other)))
    _dev_cache[mode] = tuple(devs)
    return _dev_cache[mode]


def _read_first_failure(vcd_path, devs, conj=CONJ):
    """Scan the VCD and return the values of all tracked signals at the FIRST timestamp where
    pred_conjunction or any deviation signal is 0. Only top-level miter wires are tracked."""
    ids, scope = {}, []
    copies = {}                     # (copy, mangled name) -> vcd code, for gold./gate. signals
    with open(vcd_path, errors="replace") as f:
        for line in f:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "$scope":
                scope.append(tok[2].lstrip("\\"))
            elif tok[0] == "$upscope":
                scope.pop()
            elif tok[0] == "$var" and len(tok) >= 5:
                name = tok[4].lstrip("\\")      # yosys-smtbmc may keep the RTLIL escape: \gold.xxx
                if len(scope) == 1 and name.split(".", 1)[0] in ("gold", "gate"):
                    # yosys sim -hdlname writes copy signals flat: "gold.rob_instance.ROB_state[4]"
                    copy, rel = name.split(".", 1)
                    copies.setdefault((copy, _mangle(rel)), tok[3])
                elif len(scope) == 1 and "." not in name:              # the miter's own wires
                    if name.endswith("_predicate") or name == conj or name in devs or \
                            (devs is LEGACY_DEVIATIONS and name.endswith("_deviation")):
                        ids.setdefault(tok[3], []).append(name)
                elif len(scope) > 1 and scope[1] in ("gold", "gate"):
                    # nested-scope layout, in case the VCD writer emits one
                    rel = ".".join(scope[2:] + [name])
                    copies.setdefault((scope[1], _mangle(rel)), tok[3])
            elif tok[0] == "$enddefinitions":
                break

        tracked = {n for v in ids.values() for n in v}
        dev_names = [d for d in devs if d in tracked]
        if devs is LEGACY_DEVIATIONS:
            dev_names += sorted(n for n in tracked if n.endswith("_deviation") and n not in dev_names)
        else:
            missing = [d for d in devs if d not in tracked]
            if missing:
                # a deviation that is not in the trace cannot be checked: classifying the step would be unsound
                raise RuntimeError("{0}: deviation signal(s) {1} from trg_equiv are not in the VCD (optimised away "
                                   "or renamed?). Keep them in the miter (e.g. (* keep *)) or set DeviationSignals."
                                   .format(vcd_path, ", ".join(missing)))

        # operands of every predicate: <name>_predicate -> [(label, gold code, gate code), ...]
        # custom predicates (from CONF `predicates:`) list their signals in custom_predicates.json
        custom = _load_custom_operands()
        operands = {}
        for n in tracked:
            if not n.endswith("_predicate"):
                continue
            if n in custom:
                operands[n] = [(sig, _operand_ref(copies, "gold", sig), _operand_ref(copies, "gate", sig))
                               for sig in custom[n]]
            else:
                key = n[:-len("_predicate")]
                operands[n] = [(None, copies.get(("gold", key)), copies.get(("gate", key)))]
        op_codes = {_ref_code(c) for ops in operands.values() for _, g, h in ops for c in (g, h) if c}
        op_val = {}

        cur, hit, hit_time, t_now, n_values = {}, None, None, 0, 0
        period = None                   # step length in VCD time units, from the first non-zero timestamp

        def snapshot():
            vals = {n: v for c, v in cur.items() for n in ids[c]}
            if vals.get(conj) == "0" or any(vals.get(d) == "0" for d in dev_names):
                return vals
            return None

        for line in f:
            c = line[:1]
            if c == "#":
                if cur:
                    hit = snapshot()
                    if hit:
                        hit_time = t_now
                        break               # values of the previous timestamp = first failing step
                t_now = int(line[1:].split()[0])
                if period is None and t_now > 0:
                    # a first timestamp of 5 is the falling clock edge of a 10-unit cycle (yosys sim)
                    period = 10 if t_now == 5 else t_now
            elif c in "bB":                 # vector form, used by yosys sim even for 1-bit wires: "b1 n42"
                parts = line.split()
                if len(parts) >= 2:
                    if parts[1] in ids:
                        cur[parts[1]] = parts[0][-1]    # all tracked signals are 1 bit wide
                        n_values += 1
                    if parts[1] in op_codes:
                        op_val[parts[1]] = parts[0][1:]
            elif c in "01xXzZ":             # scalar form: "1n42"
                code = line[1:].strip()
                if code in ids:
                    cur[code] = c
                    n_values += 1
                if code in op_codes:
                    op_val[code] = c
        else:
            hit = snapshot()
            hit_time = t_now

    if hit is None:
        found = ", ".join("{0} found: {1}".format(s, s in tracked) for s in (conj,) + tuple(devs))
        raise RuntimeError(
            "{0}: no step violates {1} or any deviation signal. Tracked {2} signals ({3}), "
            "parsed {4} value changes.".format(vcd_path, conj, len(tracked), found, n_values))

    values = {p: [(label, _fmt(_ref_value(op_val, g)), _fmt(_ref_value(op_val, h))) for label, g, h in ops]
              for p, ops in operands.items()}
    return hit, hit_time, dev_names, values, (period or STEP_PERIOD)


def _mangle(name):
    return name.strip().replace("\\", "").replace(".", "_").replace("[", "_").replace("]", "")


_BIT_SEL = re.compile(r"^(.*?)\s*\[\s*(\d+)\s*\]$")


def _operand_ref(copies, cp, sig):
    """VCD code of a custom-predicate operand. 'X[k]' is a memory word when the VCD has one (X_k);
    otherwise it is bit k of the packed vector X (ROB_rs1_stall, ROB_is_br, ...): returns (code, k)."""
    code = copies.get((cp, _mangle(sig)))
    if code is not None:
        return code
    m = _BIT_SEL.match(sig.strip())
    if m:
        base = copies.get((cp, _mangle(m.group(1))))
        if base is not None:
            return (base, int(m.group(2)))
    return None


def _ref_code(ref):
    return ref[0] if isinstance(ref, tuple) else ref


def _ref_value(op_val, ref):
    if ref is None:
        return None
    if isinstance(ref, tuple):
        v = op_val.get(ref[0])
        if v is None:
            return None
        k = ref[1]
        if len(v) == 1 and v not in "01":
            return v                    # x / z for the whole vector
        return v[-1 - k] if k < len(v) else "0"   # VCD drops leading zeros
    return op_val.get(ref)


def _load_custom_operands():
    path = CONF.targetPath + "/Verification/Houdini/custom_predicates.json"
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _fmt(v):
    """Decimal value, plus the bits for vectors (one bit per ROB entry for ROB_wen, ROB_mem_valid, ...)."""
    if v is None:
        return "?"
    if len(v) > 1 and set(v) <= set("01"):
        return "{0} (b{1})".format(int(v, 2), v)
    return v


# ----------------------------------------------------------------------------
# Deviation log: one entry per analysed counterexample, appended to
# <targetPath>/Verification/Houdini/predicate_deviations.log (reset at the first call of a run)
# ----------------------------------------------------------------------------

_log_started = False
_iteration = {}


def _log_path():
    return CONF.targetPath + "/Verification/Houdini/predicate_deviations.log"


def _write_log(mode, report, values, status):
    global _log_started
    _iteration[mode] = _iteration.get(mode, 0) + 1
    with open(_log_path(), "a" if _log_started else "w") as f:
        _log_started = True
        f.write("=== {0} counterexample {1}: first failing step {2} (#{3}) -> {4}\n".format(
            mode, _iteration[mode], report["step"], report["time"], status))
        f.write("pred_conjunction = {0}\n".format(report["pred_conjunction"]))
        for d, v in report["deviations"].items():
            f.write("{0} = {1}{2}\n".format(d, v, "   <-- DEVIATION" if v == "0" else ""))
        f.write("{0} predicate(s) false:\n".format(len(report["failed_predicates"])))
        width = max([len(p) for p in report["failed_predicates"]] + [1])
        for p in report["failed_predicates"]:
            ops = values.get(p, [(None, "?", "?")])
            for i, (label, g, h) in enumerate(ops):
                head = p if i == 0 else ""
                if label is None:
                    f.write("  {0:<{w}}  gold = {1:<16}  gate = {2}\n".format(head, g, h, w=width))
                else:                                   # custom predicate: one line per signal
                    f.write("  {0:<{w}}  {1}: gold = {2:<16}  gate = {3}\n".format(head, label, g, h, w=width))
        f.write("\n")


def first_failure(vcd_path, mode, devs=DEVIATIONS, conj=CONJ):
    """Evaluate pred_conjunction and every deviation signal TOGETHER at the first failing step.

    Returns (predicates_to_drop, status, report):
      status  "FAILED"   a deviation and no predicate failing (or any deviation in the base case)
              "Running"  predicates failed -> drop them and iterate
      report  dict with the step, which deviation signals are 0, which predicates are 0,
              and the value of pred_conjunction at that step
    """
    if devs is None:
        devs = deviation_signals(mode)
    hit, t, dev_names, values, period = _read_first_failure(vcd_path, devs, conj)

    deviated = [d for d in dev_names if hit.get(d) == "0"]
    preds_bad = sorted(n for n, v in hit.items() if n.endswith("_predicate") and v != "1")
    report = {
        "time": t,
        "step": None if t is None else t // period,
        "pred_conjunction": hit.get(conj),
        "deviations": {d: hit.get(d) for d in dev_names},
        "deviated": deviated,
        "failed_predicates": preds_bad,
    }

    print("[{0}] first failing step {1} (#{2}): pred_conjunction={3}, {4}, {5} predicate(s) false"
          .format(mode, report["step"], t, report["pred_conjunction"],
                  ", ".join("{0}={1}".format(d, v) for d, v in report["deviations"].items()) or "no deviation signals",
                  len(preds_bad)))

    # A deviation signal that is not 0/1 means the model itself is broken (typically: a dropped predicate was
    # merged with the deviation wire by opt_merge, and connect -set left the net undriven). Deviations can then
    # no longer be detected, so stop instead of continuing with an unsound check.
    broken = [d for d in dev_names if hit.get(d) not in ("0", "1")]
    if broken:
        _write_log(mode, report, values, "STOPPED: undefined deviation signal(s) " + ", ".join(broken))
        raise RuntimeError("{0}: {1} is undefined ({2}) in the counterexample: the deviation check is no longer "
                           "valid (a dropped predicate is aliased with it). See predicate_deviations.log."
                           .format(mode, "/".join(broken), ", ".join(hit.get(d, "?") for d in broken)))
    if preds_bad:
        print("[{0}]   false predicates: {1}".format(mode, " ".join(preds_bad)))

    stop_on_dev = CONF.experimentalParameters.get("StopOnDeviation", False)

    if deviated and (mode == "base" or not preds_bad or stop_on_dev):
        _write_log(mode, report, values, "FAILED")
        return set(), "FAILED", report

    _write_log(mode, report, values, "drop {} predicate(s)".format(len(preds_bad)))

    if deviated:
        # Inductive case: a deviation and failing predicates at the same step. The start state may be
        # unreachable, so drop the predicates and retry; if the deviation is real it comes back
        # with no predicate failing and is then reported as FAILED.
        print("[{0}]   {1} deviated together with {2} predicate(s): dropping the predicates and retrying"
              .format(mode, "/".join(deviated), len(preds_bad)))

    return set(preds_bad), "Running", report


def cexAnalysis(mode: str):
    if solver_name() == "rIC3":
        makeVCD(mode)                   # witness -> .yw -> sim replay -> <mode_base>.vcd
    elif not os.path.exists(mode_base(mode) + ".vcd"):
        raise RuntimeError("no counterexample VCD from yosys-smtbmc: " + mode_base(mode) + ".vcd")
    drop, status, _report = first_failure(mode_base(mode) + ".vcd", mode)
    return drop, status