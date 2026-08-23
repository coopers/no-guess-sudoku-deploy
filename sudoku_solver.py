"""
Explainable, no-guess Sudoku solver.

Pure constraint propagation: every placement and every candidate
elimination is justified by a named strategy and logged with a
human-readable explanation. If logic stalls, the solver says so
instead of guessing.

Strategies (cheapest first):
  1. Naked single
  2. Hidden single
  3. Naked pair / triple / quad
  4. Hidden pair / triple / quad
  5. Pointing pair/triple (box -> line)
  6. Box-line reduction (line -> box)

Candidates are 9-bit masks: bit d-1 set  <=>  digit d still possible.
"""

from itertools import combinations

# ---------------------------------------------------------------- units

ROWS = [[r * 9 + c for c in range(9)] for r in range(9)]
COLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOXES = [[(br * 3 + r) * 9 + (bc * 3 + c) for r in range(3) for c in range(3)]
         for br in range(3) for bc in range(3)]

UNITS = [(f"row {i+1}", u) for i, u in enumerate(ROWS)] + \
        [(f"column {i+1}", u) for i, u in enumerate(COLS)] + \
        [(f"box {i+1}", u) for i, u in enumerate(BOXES)]

PEERS = [set() for _ in range(81)]
for _, unit in UNITS:
    for cell in unit:
        PEERS[cell] |= set(unit) - {cell}

def rc(cell):
    return f"r{cell // 9 + 1}c{cell % 9 + 1}"

def digits_of(mask):
    return [d for d in range(1, 10) if mask >> (d - 1) & 1]

def mask_of(digits):
    m = 0
    for d in digits:
        m |= 1 << (d - 1)
    return m

SUBSET_NAME = {2: "pair", 3: "triple", 4: "quad"}


class Move:
    """One logged solver step."""
    def __init__(self, strategy, description, placements=(), eliminations=()):
        self.strategy = strategy            # e.g. "hidden single"
        self.description = description      # the "why" sentence
        self.placements = list(placements)      # [(cell, digit)]
        self.eliminations = list(eliminations)  # [(cell, digit)]

    def __str__(self):
        return f"[{self.strategy}] {self.description}"


class Solver:
    def __init__(self, grid):
        """grid: 81-char string, digits 1-9, '0' or '.' for empty."""
        s = grid.replace(".", "0")
        if len(s) != 81 or not s.isdigit():
            raise ValueError("grid must be 81 chars of 0-9 or .")
        self.values = [int(ch) for ch in s]
        self.cands = [0] * 81
        self.log = []
        for cell in range(81):
            if self.values[cell] == 0:
                used = {self.values[p] for p in PEERS[cell]} - {0}
                self.cands[cell] = mask_of(set(range(1, 10)) - used)
                if self.cands[cell] == 0:
                    raise ValueError(f"contradiction: {rc(cell)} has no candidates")

    # ------------------------------------------------------ primitives

    def place(self, cell, digit, move):
        """Set a digit and propagate the trivial peer eliminations."""
        self.values[cell] = digit
        self.cands[cell] = 0
        move.placements.append((cell, digit))
        bit = 1 << (digit - 1)
        for p in PEERS[cell]:
            if self.cands[p] & bit:
                self.cands[p] &= ~bit
                if self.cands[p] == 0 and self.values[p] == 0:
                    raise ValueError(f"contradiction at {rc(p)} after placing "
                                     f"{digit} in {rc(cell)}")

    def eliminate(self, cell, digits, move):
        removed = []
        for d in digits:
            bit = 1 << (d - 1)
            if self.cands[cell] & bit:
                self.cands[cell] &= ~bit
                removed.append(d)
                move.eliminations.append((cell, d))
        if self.cands[cell] == 0 and self.values[cell] == 0:
            raise ValueError(f"contradiction: {rc(cell)} emptied")
        return removed

    # ------------------------------------------------------ strategies
    # Each returns a Move (and applies it) or None. First hit wins.

    def naked_single(self):
        for cell in range(81):
            if self.values[cell] == 0 and bin(self.cands[cell]).count("1") == 1:
                d = digits_of(self.cands[cell])[0]
                move = Move("naked single",
                            f"{rc(cell)} has only one remaining candidate, {d}: "
                            f"every other digit already appears in its row, "
                            f"column, or box.")
                self.place(cell, d, move)
                return move
        return None

    def hidden_single(self):
        for uname, unit in UNITS:
            for d in range(1, 10):
                bit = 1 << (d - 1)
                spots = [c for c in unit if self.cands[c] & bit]
                if len(spots) == 1 and self.values[spots[0]] == 0:
                    cell = spots[0]
                    move = Move("hidden single",
                                f"in {uname}, digit {d} can only go in "
                                f"{rc(cell)}: it is excluded from every other "
                                f"cell of the unit.")
                    self.place(cell, d, move)
                    return move
        return None

    def naked_subset(self, size):
        name = f"naked {SUBSET_NAME[size]}"
        for uname, unit in UNITS:
            empty = [c for c in unit if self.values[c] == 0]
            pool = [c for c in empty if bin(self.cands[c]).count("1") <= size]
            for combo in combinations(pool, size):
                union = 0
                for c in combo:
                    union |= self.cands[c]
                if bin(union).count("1") != size:
                    continue
                ds = digits_of(union)
                targets = [c for c in empty if c not in combo
                           and self.cands[c] & union]
                if not targets:
                    continue
                move = Move(
                    name,
                    f"in {uname}, cells {', '.join(rc(c) for c in combo)} "
                    f"only contain candidates {ds} between them, so those "
                    f"{size} digits must occupy those {size} cells; "
                    f"{ds} can be removed from the rest of the unit.")
                for c in targets:
                    self.eliminate(c, ds, move)
                return move
        return None

    def hidden_subset(self, size):
        name = f"hidden {SUBSET_NAME[size]}"
        for uname, unit in UNITS:
            empty = [c for c in unit if self.values[c] == 0]
            missing = [d for d in range(1, 10)
                       if not any(self.values[c] == d for c in unit)]
            for ds in combinations(missing, size):
                m = mask_of(ds)
                cells = [c for c in empty if self.cands[c] & m]
                if len(cells) != size:
                    continue
                # must eliminate something to count as a move
                if all(self.cands[c] & ~m == 0 for c in cells):
                    continue
                move = Move(
                    name,
                    f"in {uname}, digits {list(ds)} only fit in cells "
                    f"{', '.join(rc(c) for c in cells)}, so those cells are "
                    f"reserved for them; all other candidates can be removed "
                    f"from those cells.")
                for c in cells:
                    others = digits_of(self.cands[c] & ~m)
                    self.eliminate(c, others, move)
                return move
        return None

    def pointing(self):
        """Digit in a box confined to one row/col -> clear rest of the line."""
        for b, box in enumerate(BOXES):
            for d in range(1, 10):
                bit = 1 << (d - 1)
                spots = [c for c in box if self.cands[c] & bit]
                if not 2 <= len(spots) <= 3:
                    continue
                for lines, kind in ((ROWS, "row"), (COLS, "column")):
                    idxs = {c // 9 if kind == "row" else c % 9 for c in spots}
                    if len(idxs) != 1:
                        continue
                    li = idxs.pop()
                    targets = [c for c in lines[li]
                               if c not in box and self.cands[c] & bit]
                    if not targets:
                        continue
                    move = Move(
                        "pointing " + SUBSET_NAME.get(len(spots), "set"),
                        f"in box {b+1}, digit {d} is confined to "
                        f"{', '.join(rc(c) for c in spots)}, all in "
                        f"{kind} {li+1}; wherever it lands, it occupies that "
                        f"{kind} inside the box, so {d} can be removed from "
                        f"the rest of {kind} {li+1}.")
                    for c in targets:
                        self.eliminate(c, [d], move)
                    return move
        return None

    def box_line(self):
        """Digit in a line confined to one box -> clear rest of the box."""
        for lines, kind in ((ROWS, "row"), (COLS, "column")):
            for li, line in enumerate(lines):
                for d in range(1, 10):
                    bit = 1 << (d - 1)
                    spots = [c for c in line if self.cands[c] & bit]
                    if not 2 <= len(spots) <= 3:
                        continue
                    boxes = {next(bi for bi, bx in enumerate(BOXES)
                                  if c in bx) for c in spots}
                    if len(boxes) != 1:
                        continue
                    bi = boxes.pop()
                    targets = [c for c in BOXES[bi]
                               if c not in line and self.cands[c] & bit]
                    if not targets:
                        continue
                    move = Move(
                        "box-line reduction",
                        f"in {kind} {li+1}, digit {d} only appears within "
                        f"box {bi+1} ({', '.join(rc(c) for c in spots)}); "
                        f"since {kind} {li+1} must contain a {d}, it uses one "
                        f"of those cells, so {d} can be removed from the rest "
                        f"of box {bi+1}.")
                    for c in targets:
                        self.eliminate(c, [d], move)
                    return move
        return None

    def x_wing(self):
        """Digit's candidates in two lines confined to the same two cross-lines."""
        for lines, crosses, kind, xkind, li_of, xi_of in (
                (ROWS, COLS, "row", "column",
                 lambda c: c // 9, lambda c: c % 9),
                (COLS, ROWS, "column", "row",
                 lambda c: c % 9, lambda c: c // 9)):
            for d in range(1, 10):
                bit = 1 << (d - 1)
                two = []  # (line index, frozenset of cross indices)
                for li, line in enumerate(lines):
                    spots = [c for c in line if self.cands[c] & bit]
                    if len(spots) == 2:
                        two.append((li, frozenset(xi_of(c) for c in spots),
                                    spots))
                for i in range(len(two)):
                    for j in range(i + 1, len(two)):
                        l1, xs1, sp1 = two[i]
                        l2, xs2, sp2 = two[j]
                        if xs1 != xs2:
                            continue
                        corners = sp1 + sp2
                        targets = [c for x in xs1 for c in crosses[x]
                                   if li_of(c) not in (l1, l2)
                                   and self.cands[c] & bit]
                        if not targets:
                            continue
                        xa, xb = sorted(xs1)
                        move = Move(
                            "X-wing",
                            f"digit {d} appears exactly twice in {kind}s "
                            f"{l1+1} and {l2+1}, both times in {xkind}s "
                            f"{xa+1} and {xb+1} "
                            f"({', '.join(rc(c) for c in corners)}); the two "
                            f"placements must take opposite corners of this "
                            f"rectangle, covering both {xkind}s, so {d} can "
                            f"be removed from the rest of {xkind}s {xa+1} "
                            f"and {xb+1}.")
                        for c in targets:
                            self.eliminate(c, [d], move)
                        return move
        return None

    def xy_wing(self):
        """Pivot {x,y} with pincers {x,z} and {y,z}: z dies where both pincers see."""
        bival = [c for c in range(81)
                 if self.values[c] == 0 and bin(self.cands[c]).count("1") == 2]
        for pivot in bival:
            x, y = digits_of(self.cands[pivot])
            for p1 in bival:
                if p1 == pivot or p1 not in PEERS[pivot]:
                    continue
                d1 = digits_of(self.cands[p1])
                for a, b in ((x, y), (y, x)):
                    if a not in d1 or b in d1:
                        continue
                    z = next(d for d in d1 if d != a)
                    for p2 in bival:
                        if p2 in (pivot, p1) or p2 not in PEERS[pivot]:
                            continue
                        if set(digits_of(self.cands[p2])) != {b, z}:
                            continue
                        zbit = 1 << (z - 1)
                        targets = [c for c in PEERS[p1]
                                   if c in PEERS[p2] and c != pivot
                                   and self.cands[c] & zbit]
                        if not targets:
                            continue
                        move = Move(
                            "XY-wing",
                            f"{rc(pivot)} holds {{{x},{y}}}; if it is {a}, "
                            f"then {rc(p1)} {{{a},{z}}} becomes {z}, and if "
                            f"it is {b}, then {rc(p2)} {{{b},{z}}} becomes "
                            f"{z}. Either way one pincer is {z}, so {z} can "
                            f"be removed from every cell that sees both "
                            f"{rc(p1)} and {rc(p2)}.")
                        for c in targets:
                            self.eliminate(c, [z], move)
                        return move
        return None

    # ------------------------------------------------------ main loop

    def strategies(self):
        yield self.naked_single
        yield self.hidden_single
        for size in (2, 3, 4):
            yield lambda s=size: self.naked_subset(s)
            yield lambda s=size: self.hidden_subset(s)
        yield self.pointing
        yield self.box_line
        yield self.x_wing
        yield self.xy_wing

    def solve(self):
        """Fixpoint loop. Returns 'solved' or 'stalled'."""
        while any(v == 0 for v in self.values):
            for strat in self.strategies():
                move = strat()
                if move:
                    self.log.append(move)
                    break  # restart from cheapest strategy
            else:
                return "stalled"
        return "solved"

    # ------------------------------------------------------ display

    def grid_str(self):
        out = []
        for r in range(9):
            if r in (3, 6):
                out.append("------+-------+------")
            row = []
            for c in range(9):
                if c in (3, 6):
                    row.append("|")
                v = self.values[r * 9 + c]
                row.append(str(v) if v else ".")
            out.append(" ".join(row))
        return "\n".join(out)

    def print_log(self):
        for i, move in enumerate(self.log, 1):
            print(f"{i:3}. {move}")


if __name__ == "__main__":
    # A moderate puzzle that needs more than singles.
    puzzle = ("000000010"
              "400000000"
              "020000000"
              "000050407"
              "008000300"
              "001090000"
              "300400200"
              "050100000"
              "000806000")
    s = Solver(puzzle)
    print("Puzzle:")
    print(s.grid_str())
    result = s.solve()
    print(f"\nResult: {result} in {len(s.log)} logged moves\n")
    s.print_log()
    print("\nFinal grid:")
    print(s.grid_str())
