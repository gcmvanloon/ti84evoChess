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
            target,
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
    # Action: Score every Black move at Hard's full three-ply depth.
    # Expected: Minimax sees the king capture and rejects the rook sacrifice.
    def test_hard_search_sees_an_enemy_king_capture(self):
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

        scores = score_black_moves(chess, depth=3)

        self.assertLess(scores[sacrifice], max(scores.values()))

    # Scenario: Hard's third ply can leave its rook beside the White king.
    # Action: Score the root moves with the bounded king-capture extension.
    # Expected: The move is no longer preferred beyond the depth-3 horizon.
    def test_hard_horizon_rejects_a_delayed_enemy_king_capture(self):
        chess = load_chess_engine()
        set_board(
            chess,
            {
                (3, 3): "K",
                (0, 5): "k",
                (6, 6): "R",
                (7, 2): "B",
                (7, 7): "p",
                (1, 5): "p",
            },
        )
        hanging_line = (6, 6, 6, 5, ".")

        scores = score_black_moves(chess, depth=3)

        self.assertLess(scores[hanging_line], max(scores.values()))

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


class DifficultySelectionTests(unittest.TestCase):
    # Scenario: Ranked moves straddle Medium's top-three and 40-point cutoffs.
    # Action: Capture the candidate list passed to the mocked random selector.
    # Expected: Cutoff ties remain eligible while moves outside the margin do not.
    def test_medium_candidate_window_honors_rank_margin_and_cutoff_ties(self):
        chess = load_chess_engine()
        chess.AI_RANDOMNESS = 3
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

        tied_cutoff = list(zip(moves, (100, 90, 70, 70, 65)))
        margin_cutoff = list(zip(moves, (100, 90, 50, 45, 40)))

        self.assertEqual(candidates_seen(tied_cutoff), tied_cutoff[:4])
        self.assertEqual(candidates_seen(margin_cutoff), margin_cutoff[:2])


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
