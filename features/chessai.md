# Chess AI

## Purpose and source of truth

This document explains the current chess AI: how it searches and evaluates
positions, how difficulty changes its play, and how it chooses varied moves.
Separate chapters record implemented performance optimizations and experiments
that were not retained, including the evidence and limitations of measurements.

The implementation in `../chess_evo.py` is the source of truth. The AI can play
either color. Positive scores favor Black; negative scores favor White. Black
therefore maximizes the score and White minimizes it.

## From position to move

1. Generate legal root moves for the AI's side, including special moves such
   as castling, en passant and promotion.
2. Clear the per-search killer table and order promising moves first.
3. Temporarily make each move, search the resulting position, and undo it,
   restoring board and special-move state.
4. Use the best score found so far as the alpha/beta bound for later moves.
5. Select a random eligible move, verifying candidates when needed as described
   below. Return the move for the gameplay code to execute.

The search is fixed-depth minimax with alpha-beta pruning. Each ply is one move
by one side; three plies mean our move, the opponent's reply, then our next move.
At interior nodes with no legal moves, checkmate receives a large losing score
for the mated side and stalemate scores zero. Mate scores include remaining
depth to favor earlier wins and postpone losses. Missing kings are also handled
because the game's current rules permit king capture.

At the ordinary depth limit, the engine evaluates the position without
expanding all legal replies. This is a limited lookahead, not a guarantee that
a move remains good beyond the selected depth.

## Difficulty and tactical safeguards

| Difficulty | Search depth | Allowed score loss from best |
| --- | ---: | ---: |
| Easy | 1 ply | 150 |
| Medium | 2 plies | 40 |
| Hard | 3 plies | 0 |

Easy evaluates every legal root move and checks whether its destination is
attacked. If so, it subtracts one third of the moved piece's value from that
side's result before selection. This is an attack test, not a search of the
opponent's capture; an attacked piece can still be selected within the margin.

Medium and Hard search the opponent's immediate reply, including legal king
captures. At the depth limit they use static evaluation; there are no capture
extensions beyond the selected depth.

Medium and Hard also enable passed-pawn evaluation and endgame king activity;
Hard weights those terms more strongly. Difficulty therefore affects both
lookahead and selected evaluation terms, as well as the random-choice margin.

## Position evaluation

`evaluate_board()` combines material with small positional preferences:

- Centralization, strongest for knights, then bishops, then rooks and queens.
- Central pawns and pawn advancement. Medium and Hard add a bonus for advanced
  passed pawns with no opposing pawn ahead on their or adjacent files.
- King safety while substantial material remains. With less than 900 points
  of combined knight/bishop/rook/queen material, Medium and Hard instead reward
  king centralization.
- Development, approximated by checking whether knights and bishops have left
  their starting squares.
- A small castling-position bonus for a king on its home-rank c or g square.
- A bishop-pair bonus.

These are inexpensive heuristics: for example, the castling-position check
recognizes the king's square, not its move history. Material remains the main
component. Search propagates these scores through the opponent's best replies;
move-ordering bonuses are separate and never added to the evaluated score.

## Opening preference

On Easy and Medium, normal development has priority while at least two of the
side's original central pawns and knights remain undeveloped. Preferred moves
are the d/e pawn's initial two-square advance and knight development to c3/f3
for White or c6/f6 for Black.

Only developments within 30 points (`OPENING_SAFETY_MARGIN`) of the best score
qualify. Choose uniformly among those that qualify; if none does, use the normal
difficulty pool. This prevents a built-in preference for knight development
from making every opening identical. Hard uses its normal zero-margin policy.

## Move selection and game variety

Candidate verification is related to search cost but is not a move-ordering
heuristic. It was added to preserve real randomness among all moves allowed by
the selected difficulty.

During the first root pass, the best score found so far becomes the alpha or
beta bound for subsequent root moves. This is efficient, but later branches
may return cutoff values rather than independent exact full-window scores.
Those values are sufficient to identify one best move, but are not sufficient
evidence that several apparently equal moves really are equal.

At depths greater than one, selection now uses lazy full-window verification.
The first root pass establishes an exact best score and a pool of provisional
candidates inside the difficulty margin. Draw uniformly from that pool:

1. If the selected move is the already-exact best move, play it immediately.
2. Otherwise search that move with a full alpha-beta window.
3. If its exact score is inside the original margin, play it immediately.
4. Otherwise remove it from the pool and draw again without replacement.

A failed draw does not immediately select the known best move. Repeated uniform
draws preserve uniform selection among the actually eligible moves, without
needing to discover the entire eligible set. Root bounds cannot exclude a
truly eligible move; verification rejects false positives. The exact best
score remains the reference throughout selection.

Easy's direct one-ply evaluations already include the moved-piece attack
penalty and need no second search. Easy and Medium retain their opening
policy: first try normal development moves within `OPENING_SAFETY_MARGIN` of
the best score. If none passes, use the normal difficulty pool. Exact scores
from rejected opening candidates are retained, so fallback never re-searches
the same move. Uniformity applies within the preferred opening pool when it
contains eligible moves, and otherwise within the normal pool.

Hard can still require many retries when cutoff bounds hide weaker moves.
With N provisional candidates and K truly eligible candidates, the expected
number of draws is (N+1)/(K+1). A draw of the known best move needs no search.
For N=30 and K=1, this means 14.5 additional searches on average instead of
29 exhaustive verifications. Actual time depends on branch cost and search
ordering; physical Evo-T measurements are still required.

## Debug metrics

`AI` reports elapsed AI-turn time.

`MV` counts minimax calls across both the
initial search and candidate verification; it is not the number of root moves
or only the number of leaf evaluations.

`RT` (Random Tries) counts additional searches of randomly selected candidates,
including successful verification. Selecting an already-exact move does not
increment it.

## Implemented performance optimizations

### Verify only until a random candidate succeeds

The selection policy above replaces exhaustive verification of every apparent
candidate with verification of only the random draws needed to find one valid
move. It retains the score margin and uniform choice within the eligible pool.
Already-exact scores are reused, including during opening fallback.

### Compact state and evaluation

The engine retains its array/list board and encoded moves. Search makes and
undoes moves instead of copying an entire position at every node. Evaluation
collects material, positional terms, phase and bishop counts in one board scan;
fixed-square development checks avoid generating extra moves for that purpose.

### Alpha-beta and move ordering

Without useful ordering, alpha-beta may examine most legal continuations before
finding the move that establishes a strong bound. If a strong move is searched
first, later branches can often stop as soon as they prove they cannot beat
that bound.

Ordering does not make a depth-three search see a fourth normal ply. It reduces
the amount of work needed to obtain the depth-three result. This distinction is
important when evaluating playing strength: a lower node count with the same
eligible candidate set is an improvement, while a lower count caused by
silently omitting candidates is not.

The benefit is position-dependent. A heuristic can improve the aggregate node
count while making a minority of individual positions slower. Benchmarks must
therefore use both known troublesome positions and a varied collection of
legal positions.

### Tactical moves

`move_order_score()` gives priority to:

- captures, ordered approximately by most-valuable victim and least-valuable
  attacker;
- promotions, weighted by the promoted piece value; and
- castling.

Searching forcing tactical moves first is inexpensive and commonly produces
useful alpha-beta bounds. En-passant captures are recognized even though the
destination square is empty.

### Quiet positional moves

For a non-capturing move, the ordering score uses the change in the existing
`AI_CENTER_TABLE` value from source square to destination square. The change is
weighted by piece type:

```text
knight: center change x 6
bishop: center change x 4
rook or queen: center change x 1
```

Pawns and kings receive no quiet positional ordering bonus. This deliberately
reuses information that the leaf evaluation already rewards and avoids a
second expensive board analysis. It tends to search sensible development and
centralization moves before retreats to the rim.

This is an ordering preference only. A positionally attractive move does not
receive these points in its minimax result; the points only determine when its
branch is searched.

### One killer move per ply

`KILLER_MOVES` remembers one quiet move at each search ply that caused an
alpha-beta cutoff. If the same encoded move is legal in a sibling position at
that ply, it receives a large ordering bonus and is tried early. Captures and
promotions remain ahead when their tactical score is higher.

The four-entry table covers the ply indices used by the current depth-three
search. It is cleared at the start of every root
search, so information does not leak between calculator turns.

This heuristic has a positive aggregate result but is less reliable than quiet
positional ordering. It is the first retained ordering feature to reconsider
if AST headroom becomes too small.

### Native sorting with explicit stable ties

The former insertion sort repeatedly called `move_order_score()` while moving
items into place. The current implementation instead decorates each move once:

```text
(ordering score, negative original index, encoded move)
```

It then uses the runtime's native reverse sort and removes the decorations.
Every tuple key is unique, so equal ordering scores retain move-generator order
without relying on sort stability.

The explicit index is required for correctness on the Evo-T. Hardware testing
proved that keyed sorting with `reverse=True` can reverse equal-key items even
though CPython keeps them stable. A calculator test produced results such as:

```text
got:      302, 301, 202, 103, 101
expected: 301, 302, 202, 103, 101
```

Do not simplify the implementation to `moves.sort(key=..., reverse=True)` and
then rely on equal keys retaining their input order.

## Performance measurements and their limits

### Physical Evo-T

An early retained ordering build reduced the initial Hard search from roughly
25 seconds to 19.6-19.7 seconds in three physical-calculator runs. The build
reported 732 evaluated search nodes for each run. This is approximately a 21%
hardware time reduction.

That measurement predates some later candidate-verification work and must not
be treated as a timing prediction for every current position. It does prove
that improved ordering and the native decorated sort can produce a material
speedup on the target runtime rather than only on desktop CPython.

### Reported game sequence ablation

A desktop ablation used the seven Black positions from a reported slow game and
changed only the two ordering heuristics. With the implementation used for that experiment, the totals were:

| Configuration | Minimax calls |
| --- | ---: |
| Quiet positional ordering and killer move | 6,502 |
| Killer move only | 9,184 |
| Quiet positional ordering only | 6,965 |
| Neither heuristic | 10,342 |

Together the retained heuristics reduced this workload by about 37% relative
to using neither. Quiet positional ordering provided most of the improvement
in this sequence.

### Varied legal-position ablation

A deterministic sample of 100 positions from legal random playouts produced:

| Configuration | Minimax calls | Saving in that experiment |
| --- | ---: | ---: |
| Positional and killer | 118,076 | - |
| No positional ordering | 127,135 | 7.1% |
| No killer move | 123,897 | 4.7% |
| Neither heuristic | 139,692 | 15.5% |

Compared with no positional ordering, the tested implementation was better in
64 positions, worse in 17, and unchanged in 19. Compared with no killer move,
it was better in 35, worse in 30, and unchanged in 35. This is why positional
ordering is considered strongly supported while the killer heuristic is only
provisionally retained.

The percentages are not additive because either heuristic can change which
cutoffs the other heuristic makes possible.

### Historical compiler checkpoint

The earlier release build checkpoint reported:

```text
minified bytes:       27,599
minified AST nodes:   14,049
minified statements:   1,506
```

That leaves 951 AST nodes below the working 15,000-node ceiling. This is the
complete release-build count, not the isolated cost of move ordering. Future
work must rerun the build rather than assuming this headroom remains available.

These measurements predate lazy random-candidate verification. They document
the ordering experiments, not the current implementation's total search cost.
The release build after lazy verification reported 27,331 bytes, 13,921 AST
nodes and 1,491 statements; rerun the build for later changes.

## Performance experiments not retained

### Unstable keyed sort

A direct keyed reverse sort looked correct on CPython but did not preserve ties
on the calculator. It was replaced by the unique decorated tuple sort described
above. Desktop-only stability tests are not sufficient for this behavior.

### Pawn-threat ordering

An extra heuristic attempted to prioritize moves according to immediate pawn
threats. Applying it throughout the tree made the reported game sequence worse.
A root-only version helped that particular game but saved only about 0.1% over
100 varied positions, with mixed wins and regressions. Its code and AST cost
were not justified, so it was removed.

### Narrow-window candidate proof

A narrower verification window was tested as a replacement for exact
full-window candidate scores. It saved only about 1.9% on the measured sample
and made the meaning of candidate proof harder to trust and explain. It was
reverted in favor of exact full-window verification.

### Dynamic depth four

Dynamic depth-four searching was compared with the normal initial Hard search,
not merely with a small selective extension. It was too expensive to keep
turns within the accepted initial-search time, so it was rejected.

### Selective king-capture horizon check

A former Hard-only check evaluated whether the opponent's king could legally
capture the piece moved at ply three, effectively checking one reply at ply
four. It protected a test position against delayed material loss, but did not
address the reported case of a piece being capturable immediately after the
AI's root move: that reply is already inside Medium and Hard's normal search.

The check and its last-destination argument were removed to reduce AST
complexity and leaf work. This deliberately gives up that protection beyond
the horizon; it is not evidence that all king-capture mistakes are resolved.
The tests retain coverage for immediate king captures within normal search.

### Bitboard representation

A calculator benchmark found the existing array/list representation about 85%
faster than the tested bitboard approach. Keep the current representation;
only reconsider bitboards after a new Evo-T benchmark demonstrates a gain.

### One random attempt followed by the known best move

An earlier approach, reported during gameplay testing, checked one random
candidate and fell back immediately to the known best move if it failed.
Although it limited verification cost, rejected candidates made the first
best move too common. The current retry-without-replacement policy replaces
that biased fallback while preserving the difficulty margin.

## How to evaluate future search changes

Use the following procedure for any proposed ordering or pruning optimization:

1. Change one search behavior at a time. Do not combine evaluation tuning,
   candidate selection, and ordering in one result.
2. Use identical legal positions, depth, side to move, difficulty margin, and
   random-selection boundary for the baseline and experiment.
3. Reset `KILLER_MOVES` exactly as the production root search does.
4. Count minimax calls, and separate the initial root pass from any candidate
   verification calls.
5. Compare exact final scores or verified candidate sets. A speedup that
   changes them unintentionally is a search bug, not an optimization.
6. Include the initial position, known slow middlegame positions, tactical
   positions, quieter positions, and reduced-material endgames. Do not approve
   a heuristic from one favorable game.
7. Report how many individual positions improved, worsened, or stayed equal in
   addition to the aggregate count.
8. Run `python -m unittest discover -s tests -p "test_*.py" -v` and add a
   focused regression test when behavior changes.
9. Run `bash tools/build_minified.sh --profile release` and record the minified
   AST node count. The practical limit is about 15,000 nodes; statement count
   and byte size are secondary metrics.
10. Measure representative searches on the physical Evo-T. Desktop timing is
    useful for iteration but does not replace calculator timing.

When comparing hardware runs, record at least the position or move sequence,
side to move, difficulty, elapsed `AI` time, `MV` count, and `RT` count. Without
all of them, a slow base search can easily be mistaken for verification cost or
an ordering regression.

All calculator-code changes belong in `chess_evo.py`; follow `AGENTS.md`.
Compiler pressure depends strongly on generated AST complexity. Approximately
15,000 minified AST nodes is a working project budget, not a guaranteed hardware
limit. Desktop tests and build checks do not replace physical Evo-T validation.
