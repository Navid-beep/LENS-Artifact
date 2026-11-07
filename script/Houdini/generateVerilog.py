import optparse
import os
import yaml
import re
import math
import json

# Implementation Import
from configuration import CONF, TEMP_CONF
from subprocess import run,  PIPE, STDOUT

def extract_block(template, tag):
    m = re.search(r"{0}_BEGIN\n?(.*?){0}_END".format(tag), template, re.DOTALL)
    if m is None:
        raise ValueError("{}_BEGIN/_END markers not found".format(tag))
    return m.group(1)


_TEMPLATE_CACHE = {}


def _houdini_template():
    """HoudiniTemplate.v, read once per run."""
    path = "script/VerilogTemplate/HoudiniTemplate.v"
    if path not in _TEMPLATE_CACHE:
        with open(path, "r") as f:
            _TEMPLATE_CACHE[path] = f.read()
    return _TEMPLATE_CACHE[path]


def _case_block(tag: str, verilog: list):
    """Fill in BASE_CASE_TEMPLATE or INDUCTIVE_CASE_TEMPLATE."""
    k = CONF.experimentalParameters["k"]
    ooo = CONF.experimentalParameters["PipelineDrain"] == "out-of-order"

    # Declare state_trg_equiv only if the miter does not already do it
    declared = any(re.search(r"\breg\s+state_trg_equiv\b", l) for l in verilog)

    replacements = [
        ("LOOKAHEAD",     str(k)),
        ("OUT_OF_ORDER",  "!" if ooo else ""),
        ("CLOCK",         CONF.microArchitecture["clock"]),
        ("RST",           CONF.microArchitecture["reset"]),
        ("STATE_TRG_DEF", "" if declared else "reg state_trg_equiv = 1;"),
        # Counter bits: [LOG_K:0] must hold k + 1 (inductive case). k.bit_length() bits + 1 is enough
        # for every k >= 1; the former ceil(log2(k)) gave a 1-bit counter for k = 1, which overflows.
        ("LOG_K",         str(k.bit_length())),
    ]
    block = extract_block(_houdini_template(), tag)
    for placeholder, value in replacements:
        block = block.replace(placeholder, value)
    return block


def _insert_case_block(verilog: list, block: str):
    """Replace the miter's 3-line `state_trg_equiv` always block with the case block:

        always @ (posedge in_clk) begin
                state_trg_equiv <= state_trg_equiv && trg_equiv;
        end
    """
    idx = next((i for i, l in enumerate(verilog)
                if "state_trg_equiv <=" in l and "init_state" not in l), None)

    if idx is not None:
        del verilog[idx - 1: idx + 2]
        verilog.insert(idx - 1, block)
        return

    # Older miters without that always block: insert before the assert and make it use state_trg_equiv
    idx = next((i for i, l in enumerate(verilog) if re.match(r"\s*assert\b", l)), None)
    if idx is None:
        raise ValueError("miter has neither a 'state_trg_equiv <=' always block nor an assert")
    verilog[idx] = re.sub(r"\btrg_equiv\b", "state_trg_equiv", verilog[idx])
    verilog.insert(idx, block)


def prepBaseCase(verilog: list):

    _insert_case_block(verilog, _case_block("BASE_CASE_TEMPLATE", verilog))

    with open(CONF.targetPath + "/Verification/Houdini" + "/contractVerification_base.v", 'w') as miter_file_modified:
        miter_file_modified.writelines(verilog)

    return 0


def prepInductiveCase(verilog: list):

    # Disable init: the inductive case starts from an arbitrary state
    trg_idx = next((i for i, line in enumerate(verilog) if "assume (initialize)" in line), None)
    if trg_idx is None:
        raise ValueError("miter has no 'assume (initialize)' line")
    del verilog[trg_idx]

    _insert_case_block(verilog, _case_block("INDUCTIVE_CASE_TEMPLATE", verilog))

    with open(CONF.targetPath + "/Verification/Houdini" + "/contractVerification_inductive.v", 'w') as miter_file_modified:
        miter_file_modified.writelines(verilog)

    return 0


def _reject_raw_invariants():
    """rawInvariant (assumed, never checked) was removed: those rules now go under contract: predicate:,
    where Houdini proves them or drops them."""
    contract = getattr(CONF, "contract", None) or {}
    if not isinstance(contract, dict):
        contract = vars(contract)
    if contract.get("rawInvariant"):
        raise ValueError("CONF.contract['rawInvariant'] is no longer supported: move its entries under "
                         "'predicate:' (same 'range' / 'invariant' keys; add 'compare' or 'when' for relational ones)")


def addPredicateVerilog(predicate_list: list, mode: str):

    _reject_raw_invariants()
    predicate = "".join(predicate_list)   # every line already ends in "\n"

    with open(CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v", 'r') as verilog_template:
        verilog = verilog_template.readlines()

    # Exactly the `wire trg_equiv = ... ;` line (not state_trg_equiv / init_state_trg_equiv)
    trg_idx = next((i for i, l in enumerate(verilog) if re.match(r"\s*wire\s+trg_equiv\s*=", l)), None)
    if trg_idx is None:
        raise ValueError("miter has no 'wire trg_equiv = ...' line")

    line = verilog[trg_idx].rstrip().rstrip(";").rstrip()
    if re.search(r"\bpred_conjunction\b", line):
        # Already written in the contract template: keep it as it is, appending it again
        # (above all as "|| ! pred_conjunction") would change the meaning of the line
        print("NOTE: 'wire trg_equiv' already uses pred_conjunction; left unchanged")
        verilog[trg_idx] = line + " ;\n"
    elif CONF.experimentalParameters["Synch_method"] == "direct":
        verilog[trg_idx] = line + " && pred_conjunction ;\n"
    else:
        verilog[trg_idx] = line + " || ! pred_conjunction ;\n"

    verilog.insert(trg_idx, predicate)

    if mode == "base":
        prepBaseCase(verilog)
    else:
        prepInductiveCase(verilog)


def _is_internal(name):
    """Yosys-generated names: $..., or _123_ as the last path component (Core_2stage.DatPath_2stage._131_)."""
    leaf = name.split(".")[-1]
    return "$" in name or (leaf.startswith("_") and leaf.endswith("_"))

def _mangle(name):
    return name.replace(".", "_").replace("[", "_").replace("]", "")

def _wire_options():
    """CONF.experimentalParameters["HoudiniWires"] selects wire (combinational) candidates, as LeaVe does:
         absent / false  -> registers and memories only (previous behaviour)
         true            -> every wire of the design ("Variables" lines of regs_mems.dat)
         dict            -> filtered:
             include:   [regex, ...]   keep only wires matching one of them (default: all)
             exclude:   [regex, ...]   drop wires matching one of them
             max_width: N              drop wires wider than N bits (default: no limit)
       HoudiniExclude (regex list) applies to wires as well."""
    opt = CONF.experimentalParameters.get("HoudiniWires", False)
    if not opt:
        return None
    if opt is True:
        opt = {}
    if not isinstance(opt, dict):
        raise ValueError("HoudiniWires must be true/false or a dict with include/exclude/max_width")
    return {
        "include":   [re.compile(p) for p in (opt.get("include") or [])],
        "exclude":   [re.compile(p) for p in (opt.get("exclude") or [])],
        "max_width": opt.get("max_width"),
    }


def _wire_predicates(lines, reg_names, taken, exclude):
    """One equality predicate per selected wire (Variables||name||width), with the same naming as the
    register predicates (<mangled name>_predicate), so cexAnalysis reads their gold/gate values unchanged.
    Wires that are registers, internal (_123_, $...), missing from the miter or already taken are skipped."""
    opt = _wire_options()
    if opt is None:
        return [], []

    signals = _miter_signals(CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v")
    verilog, names = [], []
    skipped = {"register": 0, "filtered": 0, "not in miter": 0, "name clash": 0}

    for line in lines:
        f = line.rstrip("\n").split("||")
        if f[0] != "Variables" or len(f) < 3:
            continue
        name = f[1].replace("\\", "")
        width = int(f[2]) if f[2].strip().isdigit() else 0
        if name in reg_names:
            skipped["register"] += 1
            continue
        if (_is_internal(name) or width == 0
                or any(r.search(name) for r in exclude)
                or any(r.search(name) for r in opt["exclude"])
                or (opt["include"] and not any(r.search(name) for r in opt["include"]))
                or (opt["max_width"] is not None and width > int(opt["max_width"]))):
            skipped["filtered"] += 1
            continue
        if name not in signals:                      # removed or renamed when the miter was built
            skipped["not in miter"] += 1
            continue
        p = _mangle(name) + "_predicate"
        if p in taken:
            skipped["name clash"] += 1
            continue
        taken.add(p)
        names.append(p)
        verilog.append("wire {0} = \\gold.{1} == \\gate.{1} ;\n".format(p, name))

    print("{0} wire predicate(s) added (skipped: {1})".format(
        len(names), ", ".join("{0} {1}".format(v, k) for k, v in skipped.items())))
    return verilog, names


def predicateInitBase():
    with open(CONF.targetPath + "/Verification/Houdini/regs_mems.dat") as f:
        lines = f.readlines()

    exclude = [re.compile(p) for p in CONF.experimentalParameters.get("HoudiniExclude", [])]
    predicate, verilog, seen = [], [], set()

    for line in lines:
        f = line.rstrip("\n").split("||")
        if f[0] not in ("Registers", "Memories"):          # Variables lines: see _wire_predicates below
            continue
        name = f[1].replace("\\", "")
        if _is_internal(name) or any(r.search(name) for r in exclude):
            continue
        ref = name.replace("[", " [")

        if f[0] == "Registers":
            if name in seen:
                continue
            seen.add(name)
            p = _mangle(name) + "_predicate"
            predicate.append(p)
            verilog.append("wire {0} = \\gold.{1} == \\gate.{1} ;\n".format(p, ref))
        else:
            size   = int(f[3])
            offset = int(f[5]) if len(f) > 5 else 0
            n_wr   = int(f[6]) if len(f) > 6 else 1
            if n_wr == 0:                                   # read-only memory: no state after memory_map
                continue
            base = _mangle(name)
            for i in range(offset, offset + size):
                p = "{0}_{1}_predicate".format(base, i)
                predicate.append(p)
                verilog.append("wire {0} = \\gold.{1} [{2}] == \\gate.{1} [{2}] ;\n".format(p, ref, i))

    # Wire (combinational) predicates, LeaVe-style: only when CONF.experimentalParameters["HoudiniWires"] is set
    reg_names = {l.split("||")[1].replace("\\", "") for l in lines if l.startswith(("Registers||", "Memories||"))}
    wire_verilog, wire_names = _wire_predicates(lines, reg_names, set(predicate), exclude)
    verilog += wire_verilog
    predicate += wire_names

    # Custom predicates from CONF.contract["predicate"]
    custom_verilog, custom_names = customPredicates()
    verilog += custom_verilog
    predicate += custom_names

    conj = " && ".join(predicate) if predicate else "1'b1"
    verilog.append("wire pred_conjunction = {0} ;\n".format(conj))

    addPredicateVerilog(verilog, "base")
    return verilog, predicate


# ---- generateVerilog.py: add below the other helpers (needs `import re` and `import json` at the top) ----
#
# Custom predicates from the CONF yaml, read as CONF.contract["predicate"]:
#
#   predicate:
#     - module: rob
#       dataSignal: rob_instance.ROB_full   # full path inside the CPU (relative to gold./gate.)
#       width: 1
#       condition: []                       # no condition -> plain equality
#
#     - module: cpu_ooo
#       dataSignal: C_mem_addr
#       width: 2
#       condition:                          # all conditions must hold for the data to be compared
#         - module: cpu_ooo
#           dataSignal: C_mem_valid
#           condition: 1                    # value the condition signal must have
#           width: 1
#
# `module` is not used for the lookup: dataSignal is taken as the full path.
#
# generates
#
#   wire C_mem_addr_if_C_mem_valid_1_custom_predicate =
#        \gold.C_mem_valid == \gate.C_mem_valid
#     && ( ! ( \gold.C_mem_valid == 1'd1 ) || ( \gold.C_mem_addr == \gate.C_mem_addr ) ) ;


def _miter_signals(miter_path):
    """Names declared as \\gold.<name> in the miter -> width (memories map to their word width)."""
    widths = {}
    decl = re.compile(r"^\s*(?:wire|reg)\s*(?:\[(\d+):(\d+)\])?\s*\\gold\.(\S+)")
    with open(miter_path, "r") as f:
        for line in f:
            m = decl.match(line)
            if m:
                hi, lo, name = m.groups()
                widths.setdefault(name, abs(int(hi) - int(lo)) + 1 if hi else 1)
    return widths


def _resolve(entry, signals):
    """dataSignal is already the full path inside the CPU (relative to gold./gate.),
    e.g. rob_instance.ROB_full or rob_instance.ROB_mem_addr[3]. Check that it exists in the miter."""
    path = str(entry["dataSignal"]).strip().replace("\\", "")
    base = path.split("[")[0]                       # memory word: strip the index for the lookup

    if base not in signals:
        raise ValueError("custom predicate: '{0}' is not declared as \\gold.{1} in the miter "
                         "(module: {2})".format(path, base, entry.get("module", "?")))

    width = entry.get("width")
    if width is not None and signals.get(path.split("[")[0]) not in (None, int(width)):
        print("WARNING: custom predicate {0}: yaml width {1} but the miter declares {2} bits"
              .format(path, width, signals[path.split("[")[0]]))
    return path


def _ref(path):
    """'rob_instance.ROB_mem_addr[3]' -> 'rob_instance.ROB_mem_addr [3]' (escaped identifier, then index)."""
    return path.replace("[", " [")


def _mangle_sig(path):
    return path.replace(".", "_").replace("[", "_").replace("]", "")


def _custom_entries():
    """The custom predicate list: CONF.contract["predicate"]. Says why when there is none."""
    contract = getattr(CONF, "contract", None)
    if contract is None:
        print("NOTE: CONF has no 'contract' attribute -> no custom predicates")
        return []
    if not isinstance(contract, dict):
        contract = vars(contract)

    entries = contract.get("predicate")
    if entries is None and "Predicate" in contract:
        print("NOTE: using CONF.contract['Predicate'] (capital P); the expected key is 'predicate'")
        entries = contract["Predicate"]

    if not entries:
        print("NOTE: CONF.contract['predicate'] is missing or empty (contract keys: {}) -> no custom predicates"
              .format(", ".join(sorted(map(str, contract))) or "none"))
        return []
    if isinstance(entries, dict):
        entries = [entries]
    return entries


_CP_REF = re.compile(r"\{(?:cp|gold|gate)\}\.([A-Za-z0-9_$.]+)((?:\s*\[\s*\d+\s*\])?)")


def _invariant_predicates(n, entry, signals):
    """Custom predicate given as a single-copy formula:

        - name: ld_ready_at_head          # optional
          range: 8                        # optional: one predicate per {i} = 0 .. range-1
          invariant: "... {cp}.rob_instance.ROB_state [{i}] ... "

    compare: both (default)     ( formula with \\gold ) && ( formula with \\gate )
             equal              ( formula with \\gold ) == ( formula with \\gate )     (gold/gate equivalence)
             equal_and_both     equivalence, and the formula holds
    when: "<formula>"           conditional equivalence (LeaVe style), `invariant` is then the value:
                                ( W_gold == W_gate ) && ( !W_gold || ( V_gold == V_gate ) )
    {gold} / {gate}             free-form relational formula, used as written (no compare / when), e.g.
                                "{gold}.rob_instance.cached_addr == {gate}.rob_instance.cached_addr"
    {i}                         replaced everywhere (also in constants such as 3'd{i})
    Like every predicate it is assumed during the inductive prefix and checked by Houdini, so it is
    proven (base + inductive) or dropped. Yields (predicate name, expression, signal paths)."""
    text = str(entry["invariant"]).strip().rstrip(";")
    base_name = re.sub(r"\W", "_", str(entry.get("name", "custom_invariant_{}".format(n))).strip())
    indices = range(int(entry["range"])) if "range" in entry else [None]

    when_text = str(entry["when"]).strip() if entry.get("when") not in (None, "") else None

    def refs(t):
        found = []
        for sig, idx in _CP_REF.findall(t):
            if sig not in signals:
                raise ValueError("custom predicate '{0}': '{1}' is not declared as \\gold.{1} in the miter"
                                 .format(base_name, sig))
            idx = re.sub(r"\s", "", idx)
            if sig + idx not in found:
                found.append(sig + idx)
        return found

    free_form = "{gold}" in text or "{gate}" in text
    if free_form and ("{cp}" in text or when_text is not None or "compare" in entry):
        raise ValueError("custom predicate '{0}': {{gold}}/{{gate}} text cannot be combined with "
                         "{{cp}}, 'compare' or 'when'".format(base_name))

    for i in indices:
        t = text if i is None else text.replace("{i}", str(i))
        gold_f, gate_f = t.replace("{cp}", "\\gold"), t.replace("{cp}", "\\gate")

        if free_form:
            # relational formula written out by hand
            paths = refs(t)
            expr = t.replace("{gold}", "\\gold").replace("{gate}", "\\gate")
        elif when_text is not None:
            # conditional equivalence (LeaVe style): the condition agrees in both copies and,
            # when it holds, the value agrees too
            w = when_text if i is None else when_text.replace("{i}", str(i))
            paths = refs(w) + [p for p in refs(t) if p not in refs(w)]
            gold_w, gate_w = w.replace("{cp}", "\\gold"), w.replace("{cp}", "\\gate")
            expr = "( ( {0} ) == ( {1} ) ) && ( !( {0} ) || ( ( {2} ) == ( {3} ) ) )".format(
                gold_w, gate_w, gold_f, gate_f)
        else:
            paths = refs(t)
            mode = str(entry.get("compare", "both")).strip().lower()
            if mode == "equal":
                # relational: both copies agree on the formula's value
                expr = "( {0} ) == ( {1} )".format(gold_f, gate_f)
            elif mode == "equal_and_both":
                # relational and single-copy: both agree, and the formula holds
                expr = "( ( {0} ) == ( {1} ) ) && ( {0} )".format(gold_f, gate_f)
            else:
                # "both" (default): the formula holds in each copy
                expr = "( {0} ) && ( {1} )".format(gold_f, gate_f)

        pname = "{0}{1}_custom_predicate".format(base_name, "" if i is None else "_{}".format(i))
        yield pname, expr, paths


def customPredicates():
    """Build one wire per CONF.contract["predicate"] entry. Returns (verilog_lines, predicate_names) and writes
    custom_predicates.json (signals of each predicate) for the counterexample log."""
    entries = _custom_entries()
    if not entries:
        return [], []

    signals = _miter_signals(CONF.targetPath + "/Contract/Verilog/contractVerification_verilog.v")
    verilog, names, operands = [], [], {}

    for n, e in enumerate(entries):
        if isinstance(e, str):
            e = {"invariant": e}          # bare formula: compare: both
        if "invariant" in e:
            # single-copy property, checked by Houdini (dropped if it fails)
            for pname, expr, paths in _invariant_predicates(n, e, signals):
                if pname in names:
                    raise ValueError("custom predicate {} is defined twice".format(pname))
                verilog.append("wire {0} = {1} ;\n".format(pname, expr))
                names.append(pname)
                operands[pname] = paths
            continue

        data = _resolve(e, signals)
        d = _ref(data)
        data_eq = "\\gold.{0} == \\gate.{0} ".format(d)

        conds = e.get("condition") or []
        if isinstance(conds, dict):
            conds = [conds]

        name = _mangle_sig(data)
        eq_parts, hold_parts, cond_paths = [], [], []
        for c in conds:
            cp = _resolve(c, signals)
            cr = _ref(cp)
            value = int(c.get("condition", 1))
            width = int(c.get("width") or signals.get(cp.split("[")[0], 1))
            eq_parts.append("\\gold.{0} == \\gate.{0} ".format(cr))
            hold_parts.append("( \\gold.{0} == {1}'d{2} )".format(cr, width, value))
            cond_paths.append(cp)
            name += "_if_{0}_{1}".format(_mangle_sig(cp), value)

        pname = name + "_custom_predicate"
        if pname in names:
            raise ValueError("custom predicate {} is defined twice".format(pname))

        if conds:
            expr = "{0} && ( ! ( {1} ) || ( {2}) )".format(
                " && ".join(eq_parts), " && ".join(hold_parts), data_eq)
        else:
            expr = data_eq

        verilog.append("wire {0} = {1} ;\n".format(pname, expr))
        names.append(pname)
        operands[pname] = cond_paths + [data]

    with open(CONF.targetPath + "/Verification/Houdini/custom_predicates.json", "w") as f:
        json.dump(operands, f, indent=2)

    print("{} custom predicate(s) from CONF: {}".format(len(names), ", ".join(names)))
    return verilog, names