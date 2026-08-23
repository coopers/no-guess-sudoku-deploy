# No-Guess Sudoku

A sudoku solver that never guesses. Every move is derived by a named logical
strategy and logged with a human-readable justification. If pure logic runs
out, it says so instead of backtracking.

**Live app:** `index.html` (deployed via GitHub Pages)

## Strategies

Naked/hidden singles → naked/hidden pairs, triples, quads → pointing pairs →
box-line reduction → X-wing → XY-wing. This covers the full technique range
of NYT Easy/Medium/Hard. The pipeline restarts from the cheapest strategy
after every move, so advanced techniques only fire when genuinely needed —
which makes "hardest technique used" an honest difficulty rating.

## Files

- `index.html` — the web app, fully self-contained (React via CDN, pre-compiled)
- `sudoku_solver.py` — the same engine in Python, with a CLI demo
- `test_wings.py` — soundness tests (logic placements verified against a
  brute-force reference solver) and ablation tests (proving the wing
  strategies are necessary on wing-critical puzzles)

## Loading puzzles

Paste an 81-character string (0 or `.` = blank), upload any text file
containing one, or click cells and type.
