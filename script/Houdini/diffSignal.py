
import bisect
from collections import defaultdict
 
 
def find_differing_signals(vcd_path, output_path="differing_signals.txt", inst_a="gold", inst_b="gate"):
    """
    Read a VCD file and find signals that have the same name under two instances
    (e.g. gold.mem.addr and gate.mem.addr) but different values at some time step.
    Writes the result to `output_path` as:
 
        Signals:
        mem.addr
        mem.we
 
    Returns the list of differing signal names.
    """
    id_to_names = defaultdict(list)   # VCD id code -> full signal names
    changes = defaultdict(list)       # VCD id code -> [(time, value), ...]
    scope = []
    t = 0
 
    with open(vcd_path, "r", errors="replace") as f:
        in_header = True
        tokens = []
        for line in f:
            if in_header:
                # Header: $scope / $upscope / $var ... $end
                tokens.extend(line.split())
                while "$end" in tokens:
                    end = tokens.index("$end")
                    cmd, args = tokens[0], tokens[1:end]
                    tokens = tokens[end + 1:]
                    if cmd == "$scope" and len(args) >= 2:
                        scope.append(args[1])
                    elif cmd == "$upscope" and scope:
                        scope.pop()
                    elif cmd == "$var" and len(args) >= 4:
                        name = args[3] + "".join(args[4:])
                        id_to_names[args[2]].append(".".join(scope + [name]))
                    elif cmd == "$enddefinitions":
                        in_header = False
                continue
 
            # Value changes
            line = line.strip()
            if not line:
                continue
            c = line[0]
            if c == "#":
                t = int(line[1:].split()[0])
            elif c in "bBrR":
                parts = line.split()
                if len(parts) >= 2:
                    changes[parts[1]].append((t, parts[0][1:]))
            elif c in "01xXzZuUwWlLhH-":
                changes[line[1:].strip()].append((t, c))
 
    # Pair gold.<path> with gate.<path>
    pairs = defaultdict(dict)
    for id_code, names in id_to_names.items():
        for full in names:
            parts = full.split(".")
            for i, p in enumerate(parts):
                if p in (inst_a, inst_b):
                    pairs[".".join(parts[i + 1:])][p] = id_code
                    break
 
    def norm(v):
        # b11 and b0011 are the same value
        return None if v is None else (v.lower().lstrip("0") or "0")
 
    def value_at(series, times, time):
        i = bisect.bisect_right(times, time) - 1
        return series[i][1] if i >= 0 else None
 
    differing = []
    for name, ids in sorted(pairs.items()):
        if inst_a not in ids or inst_b not in ids:
            continue
        sa, sb = changes.get(ids[inst_a], []), changes.get(ids[inst_b], [])
        ta, tb = [x[0] for x in sa], [x[0] for x in sb]
        for time in sorted(set(ta) | set(tb)):
            if norm(value_at(sa, ta, time)) != norm(value_at(sb, tb, time)):
                differing.append(name)
                break
 
    with open(CONF.targetPath , "w") as out:
        out.write("Signals:\n")
        for name in differing:
            out.write(name + "\n")
 
    return differing
 
