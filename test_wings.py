"""Verify the wing strategies: soundness vs brute force, and ablation."""
from sudoku_solver import Solver, PEERS
from collections import Counter

def brute(values):
    """Backtracking reference solver. Returns (count up to 2, one solution)."""
    values = list(values)
    sols = []
    def rec():
        if len(sols) >= 2:
            return
        best, best_opts = None, None
        for cell in range(81):
            if values[cell] == 0:
                used = {values[p] for p in PEERS[cell]}
                opts = [d for d in range(1, 10) if d not in used]
                if best is None or len(opts) < len(best_opts):
                    best, best_opts = cell, opts
                    if len(opts) <= 1:
                        break
        if best is None:
            sols.append(list(values)); return
        for d in best_opts:
            values[best] = d
            rec()
            values[best] = 0
    rec()
    return len(sols), (sols[0] if sols else None)

PUZZLES = [
    # earlier test set
    "000000010400000000020000000000050407008000300001090000300400200050100000000806000",
    "400000805030000000000700000020000060000080400000010000000603070500200000104000000",
    "000000907000420180000705026100904000050000040000507009920108000034059000507000000",
    "100007090030020008009600500005300900010080002600004000300000010040000007007000300",
    # hard bank (top95-style)
    "4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......",
    "52...6.........7.13...........4..8..6......5...........418.........3..2...87.....",
    "48.3............71.2.......7.5....6....2..8.............1.76...3.....4......5....",
    "....14....3....2...7..........9...3.6.1.............8.2.....1.4....5.6.....7.8...",
    "6.....8.3.4.7.................5.4.7.3..2.....1.6.......2.....5.....8.6......1....",
    # the user's puzzle from earlier
    "...5..3...2....91.93..1...7..9628.....4...1...5.9...........87......34.....752...",
]

wings_on_extra = 0
for i, p in enumerate(PUZZLES):
    s0 = Solver(p)
    n, sol = brute(s0.values)
    if n != 1:
        print(f"#{i}: SKIP (not a proper puzzle: {n} solutions)")
        continue

    # full pipeline
    s = Solver(p)
    result = s.solve()
    # soundness: every placement must match the unique solution
    ok = all(v == 0 or v == sol[c] for c, v in enumerate(s.values))
    assert ok, f"#{i}: UNSOUND placement!"

    # ablation: same puzzle without the wing strategies
    s2 = Solver(p)
    s2.strategies = lambda self=s2: iter(list(Solver.strategies(self))[:-2])
    result2 = s2.solve()

    used = Counter(m.strategy for m in s.log)
    wings = used.get("X-wing", 0) + used.get("XY-wing", 0)
    if result == "solved" and result2 == "stalled":
        wings_on_extra += 1
        tag = "  << wings made the difference"
    else:
        tag = ""
    print(f"#{i}: {result:8} (no-wings: {result2:8}) "
          f"X-wing×{used.get('X-wing',0)} XY-wing×{used.get('XY-wing',0)}, "
          f"sound=OK{tag}")

print(f"\npuzzles solved only because of wings: {wings_on_extra}")
