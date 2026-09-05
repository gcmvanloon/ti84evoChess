import unittest
from unittest import mock

from chess_test_support import load_chess_engine


def set_board(chess, pieces):
    """Replace the board with a minimal position and disable special moves."""
    chess.board = [["."]*8 for _ in range(8)]
    for (y, x), piece in pieces.items():
        chess.board[y][x] = piece

    chess.white_castle_k = chess.white_castle_q = False
    chess.black_castle_k = chess.black_castle_q = False
    chess.en_passant_x = chess.en_passant_y = -1


def score_black_moves(chess, depth):
    """Return exact root scores before difficulty randomization is applied."""
    scores = {}
    for move in chess.get_legal_moves(1):
        source = move & 63
        target = (move >> 6) & 63
        promotion_index = move >> 12
        promotion = (
            chess.PROMOTION_CHOICES[promotion_index-1]
            if promotion_index else None
        )
        state = chess.make_move(
            source >> 3,
            source & 7,
            target >> 3,
            target & 7,
            1,
            False,
            promotion,
            0,
        )
        score = chess.minimax(
            depth-1,
            -chess.AI_INFINITY,
            chess.AI_INFINITY,
            0,
            1,
        )
        chess.undo_move(state)
        scores[chess.unpack_move(move)] = score
    return scores


class EvaluationTests(unittest.TestCase):
    # Scenario: A freshly reset board contains the standard starting position.
    # Action: Evaluate the board before either player has moved.
    # Expected: White and Black have equal material and positional scores.
    def test_initial_position_is_equal(self):
        chess = load_chess_engine()

        self.assertEqual(chess.evaluate_board(), 0)

    # Scenario: Each minimal board has both kings and one unmatched major piece.
    # Action: Evaluate an extra Black queen and an extra White rook separately.
    # Expected: The scores equal the piece values with the correct side's sign.
    def test_material_advantage_has_expected_value_and_sign(self):
        chess = load_chess_engine()
        kings = {(0, 0): "K", (7, 7): "k"}

        cases = (
            ("black queen", {(0, 6): "Q"}, 900),
            ("white rook", {(7, 1): "r"}, -500),
        )
        for name, extra_pieces, expected in cases:
            with self.subTest(name=name):
                set_board(chess, {**kings, **extra_pieces})
                self.assertEqual(chess.evaluate_board(), expected)

    # Scenario: An asymmetric position is rotated and every piece changes color.
    # Action: Evaluate the original position and its color-swapped mirror.
    # Expected: The mirrored score is the exact negative of the original score.
    def test_rotating_and_swapping_colors_negates_evaluation(self):
        chess = load_chess_engine()
        set_board(
            chess,
            {
                (0, 0): "K",
                (7, 7): "k",
                (3, 3): "N",
                (4, 4): "P",
                (7, 1): "r",
            },
        )
        original_score = chess.evaluate_board()

        chess.board = [
            [piece.upper() if piece in chess.WHITE else piece.lower()
             for piece in row[::-1]]
            for row in chess.board[::-1]
        ]

        self.assertNotEqual(original_score, 0)
        self.assertEqual(chess.evaluate_board(), -original_score)

    # Scenario: Black can place its king in the center with only kings left.
    # Action: Compare corner and central king positions in Hard's endgame.
    # Expected: The active central king receives the higher evaluation.
    def test_hard_activates_the_king_in_the_endgame(self):
        chess = load_chess_engine()
        set_board(chess, {(0, 0): "K", (7, 7): "k"})
        corner_score = chess.evaluate_board()

        set_board(chess, {(3, 3): "K", (7, 7): "k"})
        center_score = chess.evaluate_board()

        self.assertGreater(center_score, corner_score)

    # Scenario: Both queens remain while Black considers centralizing its king.
    # Action: Compare corner and central king positions in Hard's middlegame.
    # Expected: With major attacking material present, the center is penalized.
    def test_hard_keeps_the_king_safer_while_queens_remain(self):
        chess = load_chess_engine()
        queens = {(0, 7): "Q", (7, 0): "q", (7, 7): "k"}
        set_board(chess, {**queens, (0, 0): "K"})
        corner_score = chess.evaluate_board()

        set_board(chess, {**queens, (3, 3): "K"})
        center_score = chess.evaluate_board()

        self.assertLess(center_score, corner_score)

    # Scenario: The same advanced pawn is either passed or stopped nearby.
    # Action: Compare the score difference at all three difficulty depths.
    # Expected: Passed-pawn awareness increases from Easy to Medium to Hard.
    def test_passed_pawn_weight_increases_with_difficulty(self):
        chess = load_chess_engine()
        kings_and_pawn = {(0, 0): "K", (7, 7): "k", (4, 3): "P"}
        differences = []
        for depth in (1, 2, 3):
            chess.AI_DEPTH = depth
            set_board(chess, {**kings_and_pawn, (5, 2): "p"})
            blocked_score = chess.evaluate_board()

            set_board(chess, {**kings_and_pawn, (5, 1): "p"})
            passed_score = chess.evaluate_board()
            differences.append(passed_score-blocked_score)

        self.assertLess(differences[0], differences[1])
        self.assertLess(differences[1], differences[2])


class SearchTests(unittest.TestCase):
    # Scenario: The initial position gives all Black pawn moves the same score.
    # Action: Apply production ordering to those equal-scored moves.
    # Expected: Equal-scored moves retain move-generator order on every runtime.
    def test_move_ordering_stabilizes_equal_scores(self):
        chess = load_chess_engine()
        moves = [move for move in chess.get_legal_moves(1)
                 if chess.board[(move&63)>>3][move&7] == "P"]
        expected = moves[:]

        chess.order_moves(moves, 0)

        self.assertEqual(moves, expected)

    # Scenario: A quiet knight can move toward the center or toward the rim.
    # Action: Compare the production ordering scores before minimax runs.
    # Expected: The positionally stronger central move is searched first.
    def test_move_ordering_prefers_quiet_piece_square_improvement(self):
        chess = load_chess_engine()
        central = chess.pack_move(0, 6, 2, 5)
        rim = chess.pack_move(0, 6, 2, 7)

        self.assertGreater(
            chess.move_order_score(central),
            chess.move_order_score(rim),
        )

    # Scenario: White's two initial knight moves have equal exact Hard scores.
    # Action: Force random selection of the second fully searched tie.
    # Expected: Root equality search restores safe opening variety.
    def test_hard_randomizes_a_verified_exact_root_tie(self):
        chess = load_chess_engine()
        chess.ai_random_tries = 0

        with mock.patch.object(
            chess.random,
            "choice",
            side_effect=lambda moves: moves[-1],
        ):
            selected = chess.find_best_move(3, 0)

        self.assertEqual(selected, (7, 6, 5, 5, "."))
        self.assertEqual(chess.ai_random_tries, 1)

    # Scenario: A Black rook has a clear line to an undefended White queen.
    # Action: Score every legal Black move with a full two-ply minimax window.
    # Expected: Capturing the queen is the unique highest-scoring move.
    def test_search_prefers_a_free_queen_capture(self):
        chess = load_chess_engine()
        set_board(
            chess,
            {
                (0, 0): "K",
                (7, 7): "k",
                (3, 0): "R",
                (3, 3): "q",
            },
        )

        scores = score_black_moves(chess, depth=2)
        queen_capture = (3, 0, 3, 3, ".")

        self.assertEqual(scores[queen_capture], max(scores.values()))
        self.assertEqual(
            [move for move, score in scores.items() if score == max(scores.values())],
            [queen_capture],
        )

    # Scenario: A Black rook can take a pawn but the White queen can recapture it.
    # Action: Score the position at one ply and again at Medium's two-ply depth.
    # Expected: One ply favors the pawn capture; two plies prefer a safe move.
    def test_medium_search_rejects_a_poisoned_capture(self):
        chess = load_chess_engine()
        set_board(
            chess,
            {
                (0, 0): "K",
                (7, 7): "k",
                (3, 0): "R",
                (3, 3): "p",
                (3, 4): "q",
            },
        )
        poisoned_capture = (3, 0, 3, 3, ".")

        shallow_scores = score_black_moves(chess, depth=1)
        medium_scores = score_black_moves(chess, depth=2)

        self.assertEqual(
            shallow_scores[poisoned_capture],
            max(shallow_scores.values()),
        )
        self.assertLess(
            medium_scores[poisoned_capture],
            max(medium_scores.values()),
        )

    # Scenario: Black can move a rook next to the White king, undefended.
    # Action: Score every Black move at Medium and Hard depths.
    # Expected: Minimax sees the king capture and rejects the rook sacrifice.
    def test_search_sees_an_immediate_enemy_king_capture(self):
        chess = load_chess_engine()
        set_board(
            chess,
            {
                (0, 0): "K",
                (4, 4): "k",
                (5, 7): "R",
            },
        )
        sacrifice = (5, 7, 5, 5, ".")

        for depth in (2, 3):
            with self.subTest(depth=depth):
                chess.AI_DEPTH = depth
                scores = score_black_moves(chess, depth=depth)
                self.assertLess(scores[sacrifice], max(scores.values()))

    # Scenario: A depth-limit position has an undefended rook beside a king.
    # Action: Evaluate the leaf for either side to move at Hard's third ply.
    # Expected: Search returns static evaluation without simulating a capture.
    def test_depth_limit_uses_static_evaluation(self):
        chess = load_chess_engine()
        set_board(chess, {(0, 0): "K", (4, 4): "k", (5, 5): "R"})
        expected = chess.evaluate_board()
        for side in (0, 1):
            with self.subTest(side=side), mock.patch.object(chess, "make_move") as make:
                score = chess.minimax(0, -chess.AI_INFINITY, chess.AI_INFINITY, side, 3)
            self.assertEqual(score, expected)
            make.assert_not_called()

    # Scenario: The standard board includes castling and en-passant state.
    # Action: Search for Black's best move while forcing deterministic selection.
    # Expected: Search restores the board and every saved special-move flag.
    def test_search_restores_game_state(self):
        chess = load_chess_engine()
        before = (
            tuple(tuple(row) for row in chess.board),
            chess.white_castle_k,
            chess.white_castle_q,
            chess.black_castle_k,
            chess.black_castle_q,
            chess.en_passant_x,
            chess.en_passant_y,
        )

        with mock.patch.object(chess.random, "choice", side_effect=lambda moves: moves[0]):
            chess.find_best_move(2, 1)

        after = (
            tuple(tuple(row) for row in chess.board),
            chess.white_castle_k,
            chess.white_castle_q,
            chess.black_castle_k,
            chess.black_castle_q,
            chess.en_passant_x,
            chess.en_passant_y,
        )
        self.assertEqual(after, before)

    # Scenario: Evo-T keyed sorting can reverse equal stored scores.
    # Action: Force selection of the last exactly best move in the bug position.
    # Expected: The losing knight move is absent from Hard's verified candidates.
    def test_hard_root_choice_does_not_depend_on_keyed_sort_stability(self):
        chess = load_chess_engine()
        chess.board = [list(row) for row in (
            "R.BQ.RK.",
            "PPPP.P.P",
            "..N..N..",
            "......P.",
            "...p....",
            "bpn.p...",
            "p....ppp",
            "r..qkb.r",
        )]
        chess.white_castle_q = False
        chess.black_castle_k = chess.black_castle_q = False
        chess.en_passant_x = chess.en_passant_y = -1
        chess.update_material_state()
        knight_blunder = (2, 2, 3, 4, ".")

        with mock.patch.object(chess.random, "choice", side_effect=lambda moves: moves[-1]):
            selected = chess.find_best_move(3, 1)

        scores = score_black_moves(chess, 3)
        self.assertGreater(scores[selected], scores[knight_blunder])


class DifficultySelectionTests(unittest.TestCase):
    # Scenario: Ranked moves straddle Medium's 40-point score cutoff.
    # Action: Capture the candidate list passed to the mocked random selector.
    # Expected: Cutoff ties remain eligible while moves outside the margin do not.
    def test_medium_candidate_window_honors_rank_margin_and_cutoff_ties(self):
        chess = load_chess_engine()
        chess.AI_SCORE_MARGIN = 40
        moves = [chess.pack_move(0, x, 1, x) for x in range(5)]

        def candidates_seen(scored):
            seen = []

            def choose_first(candidates):
                seen.extend(candidates)
                return candidates[0]

            with mock.patch.object(chess.random, "choice", side_effect=choose_first):
                chess.choose_ranked_move(scored, True)
            return seen

        inside_cutoff = list(zip(moves, (100, 90, 70, 70, 65)))
        margin_cutoff = list(zip(moves, (100, 90, 50, 45, 40)))

        self.assertEqual(candidates_seen(inside_cutoff), inside_cutoff)
        self.assertEqual(candidates_seen(margin_cutoff), margin_cutoff[:2])

    # Scenario: A bound-only tie fails before another equal-best move is drawn.
    # Action: Reject the first candidate, then draw the other tie for both sides.
    # Expected: Selection retries without fallback, counts searches, restores board.
    def test_random_verification_retries_after_rejection(self):
        for side in (0, 1):
            chess = load_chess_engine()
            chess.AI_SCORE_MARGIN = 0
            chess.ai_random_tries = 0
            moves = chess.get_legal_moves(side)[:3]
            scored = [(move, 100) for move in moves]
            before = [row[:] for row in chess.board]
            pools = []

            def draw(candidates):
                pools.append([item[0] for item in candidates])
                return candidates[1]

            rejected_score = 90 if side else 110
            with mock.patch.object(chess.random, "choice", side_effect=draw), \
                 mock.patch.object(chess, "minimax", side_effect=[rejected_score, 100]) as search:
                selected = chess.choose_ranked_move(scored, bool(side), 3, side, moves[0])
            self.assertEqual(selected, chess.unpack_move(moves[2]))
            self.assertEqual(pools, [moves, [moves[0], moves[2]]])
            self.assertEqual(chess.ai_random_tries, 2)
            self.assertEqual(search.call_count, 2)
            self.assertEqual(chess.board, before)

    # Scenario: An opening move fails opening safety but fits Medium's margin.
    # Action: Draw it again when selection falls back to the normal pool.
    # Expected: Its exact score is reused and only one search is counted.
    def test_opening_fallback_reuses_verified_score(self):
        chess = load_chess_engine()
        chess.AI_SCORE_MARGIN = 40
        chess.ai_random_tries = 0
        moves = chess.get_legal_moves(1)
        opening_move = next(move for move in moves
                            if chess.is_opening_development_move(1, move))
        best_move = next(move for move in moves
                         if not chess.is_opening_development_move(1, move))
        scored = [(best_move, 100), (opening_move, 100)]
        with mock.patch.object(chess.random, "choice", side_effect=lambda pool: pool[-1]), \
             mock.patch.object(chess, "minimax", return_value=65) as search:
            selected = chess.choose_ranked_move(scored, True, 2, 1, best_move, True)
        self.assertEqual(selected, chess.unpack_move(opening_move))
        self.assertEqual(search.call_count, 1)
        self.assertEqual(chess.ai_random_tries, 1)

    # Scenario: The known best move is drawn immediately on Hard.
    # Action: Choose it from a provisional pool.
    # Expected: No extra minimax call and RT remains zero.
    def test_known_best_needs_no_random_verification(self):
        chess = load_chess_engine()
        chess.ai_random_tries = 0
        move = chess.get_legal_moves(1)[0]
        with mock.patch.object(chess, "minimax") as search:
            selected = chess.choose_ranked_move([(move, 100)], True, 3, 1, move)
        self.assertEqual(selected, chess.unpack_move(move))
        search.assert_not_called()
        self.assertEqual(chess.ai_random_tries, 0)


class MoveGenerationTests(unittest.TestCase):
    # Scenario: A White rook shields its king from a Black rook on the same file.
    # Action: Generate every legal White move from the pinned position.
    # Expected: Sideways rook moves are rejected, but blocking moves remain legal.
    def test_pinned_rook_cannot_expose_its_king(self):
        chess = load_chess_engine()
        set_board(
            chess,
            {
                (0, 0): "K",
                (0, 4): "R",
                (6, 4): "r",
                (7, 4): "k",
            },
        )

        moves = {chess.unpack_move(move) for move in chess.get_legal_moves(0)}

        self.assertNotIn((6, 4, 6, 3, "."), moves)
        self.assertIn((6, 4, 5, 4, "."), moves)

    # Scenario: An undefended Black rook is adjacent to the White king.
    # Action: Generate White's legal replies.
    # Expected: The opposing king attacks and can capture the rook.
    def test_king_can_capture_an_undefended_adjacent_piece(self):
        chess = load_chess_engine()
        set_board(chess, {(0, 0): "K", (4, 4): "k", (4, 5): "R"})

        moves = {chess.unpack_move(move) for move in chess.get_legal_moves(0)}

        self.assertIn((4, 4, 4, 5, "."), moves)

    # Scenario: The adjacent rook is protected by the distant Black king.
    # Action: Generate White's legal replies.
    # Expected: White cannot capture onto a square attacked by that king.
    def test_king_cannot_capture_a_piece_defended_by_the_enemy_king(self):
        chess = load_chess_engine()
        set_board(chess, {(3, 6): "K", (4, 4): "k", (4, 5): "R"})

        moves = {chess.unpack_move(move) for move in chess.get_legal_moves(0)}

        self.assertNotIn((4, 4, 4, 5, "."), moves)


if __name__ == "__main__":
    unittest.main()
