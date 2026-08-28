# TI-84 EVO-T CHESS v96
# v9.6 - knight silhouette reshaped from simplified horse-head reference
#
# The compact build is generated from this version using only
# semantics-preserving source transformations: identifier shortening,
# drawing-call aliases, whitespace removal and safe statement packing.
# Minimax depth, alpha-beta pruning, evaluation and randomness are unchanged.
# Optimized redraw version
#
# ARROWS = move cursor
# ENTER  = select / move
# CLEAR  = back / menu
#
# The entire board is drawn only once.
# Afterwards only changed squares are redrawn.
# All six chess pieces now use compact primitive renderers.

import ti_draw
import ti_system
import random

# Thin pen for tile highlights.
ti_draw.set_pen("thin","solid")

board = [
    ["R","N","B","Q","K","B","N","R"],
    ["P","P","P","P","P","P","P","P"],
    [".",".",".",".",".",".",".","."],
    [".",".",".",".",".",".",".","."],
    [".",".",".",".",".",".",".","."],
    [".",".",".",".",".",".",".","."],
    ["p","p","p","p","p","p","p","p"],
    ["r","n","b","q","k","b","n","r"]
]

WHITE = "prnbqk"
BLACK = "PRNBQK"

# Piece colors are shared by all six renderers. Player 1 uses a white fill
# with a black outline; player 2 uses the reverse.
WHITE_RGB = (255,255,255)
BLACK_RGB = (0,0,0)
CHECK_RGB = (220,0,0)

KEY_LEFT  = 24
KEY_UP    = 25
KEY_RIGHT = 26
KEY_DOWN  = 34
KEY_CLEAR = 45
KEY_ENTER = 105

BOARD_X = 115
BOARD_Y = 26
SQUARE = 18

# On the current TI-84 Evo ti_draw implementation,
# rectangle primitives appear one square (18 px) lower
# than draw_text. Apply one central correction so
# rectangles and text use the same logical coordinates.
SHAPE_Y_FIX = -18

# ------------------------------------------------------------
# SCORE + CAPTURE PANEL
# ------------------------------------------------------------
PIECE_VALUES = {
    "p":1,
    "n":3,
    "b":3,
    "r":5,
    "q":9,
    "k":0
}

# ------------------------------------------------------------
# AI SETTINGS
# ------------------------------------------------------------
# Defaults. One-player difficulty selection overrides these values.
AI_DEPTH = 3
AI_RANDOMNESS = 1
OPENING_SAFETY_MARGIN = 30

# Evaluation values use centipawn-like units. They are deliberately
# separate from the visible capture score above.
AI_PIECE_VALUES = {
    "p":100,
    "n":320,
    "b":330,
    "r":500,
    "q":900,
    "k":20000
}

AI_MATE_SCORE = 100000
AI_INFINITY = 1000000

# Lightweight piece-square data. One shared 8x8 center table keeps
# memory use low; piece-specific multipliers turn it into positional
# values for knights, bishops, rooks and queens. Pawns and kings use
# a few direct positional rules below.
AI_CENTER_TABLE = (
    0,0,0,0,0,0,0,0,
    0,1,1,1,1,1,1,0,
    0,1,2,2,2,2,1,0,
    0,1,2,4,4,2,1,0,
    0,1,2,4,4,2,1,0,
    0,1,2,2,2,2,1,0,
    0,1,1,1,1,1,1,0,
    0,0,0,0,0,0,0,0
)

AI_DEVELOPMENT_BONUS = 12
AI_CASTLED_BONUS = 25
AI_BISHOP_PAIR_BONUS = 20

# Right side of the 320-pixel drawing area.
CAPTURE_X = 260
CAPTURE_Y = 26
CAPTURE_W = 59
CAPTURE_ROW = 18

# Score difference below the board.
SCORE_Y = 190

# Light gray for the non-board UI panels.
UI_BG = (255,255,255)
LEFT_BG = (232,236,244)
LEFT_PANEL_W = 100

# ------------------------------------------------------------
# SPECIALIZED CHESS PIECE DRAWING
# ------------------------------------------------------------
# All six pieces now use compact primitive-based silhouettes.
# Relative coordinate tuples keep parser/compiler syntax complexity low.
#
# px,py is the top-left of the 16x16 colored tile interior. white_piece is
# True for player 1 and False for player 2; the king also receives checked.

def draw_offset_fill_poly(px,py,x_offsets,y_offsets):
    # Offset helpers only translate the compact relative coordinates. Each
    # piece renderer owns its color selection and drawing order.
    sy = py + SHAPE_Y_FIX
    xs = [px+i for i in x_offsets]
    ys = [sy+i for i in y_offsets]
    ti_draw.fill_poly(xs,ys)


def draw_offset_poly(px,py,x_offsets,y_offsets):
    sy = py + SHAPE_Y_FIX
    xs = [px+i for i in x_offsets]
    ys = [sy+i for i in y_offsets]
    ti_draw.draw_poly(xs,ys)


def draw_pawn(px,py,white_piece):
    # Same v92 pawn silhouette, expressed as relative coordinates so the
    # function has much less syntax for MicroPython to parse and compile.
    fill = WHITE_RGB if white_piece else BLACK_RGB
    outline = BLACK_RGB if white_piece else WHITE_RGB
    xs = (7,9,11,11,10,9,9,11,13,14,1,2,4,6,6,5,4,4,6,7)
    ys = (0,0,2,4,5,6,8,11,13,15,15,13,11,8,6,5,4,2,0,0)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,xs,ys)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,xs,ys)


def draw_rook(px,py,white_piece):
    # Same v92 rook silhouette.
    fill = WHITE_RGB if white_piece else BLACK_RGB
    outline = BLACK_RGB if white_piece else WHITE_RGB
    xs = (1,4,4,6,6,10,10,12,12,15,15,13,12,12,14,15,1,2,4,4,3,1,1)
    ys = (1,1,4,4,1,1,4,4,1,1,6,6,8,11,13,15,15,13,11,8,6,6,1)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,xs,ys)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,xs,ys)


def draw_knight(px,py,white_piece):
    # Simplified left-facing knight based on the reference silhouette. The
    # forehead drops vertically into a long muzzle, the underside cuts back
    # sharply into the neck, and the rear slopes down into a flat base.
    # One closed polygon keeps both draw-call and parser overhead low.
    fill = WHITE_RGB if white_piece else BLACK_RGB
    outline = BLACK_RGB if white_piece else WHITE_RGB
    xs = (6,6,1,3,9,9,6,5,14,13,12,10,6)
    ys = (0,2,6,9,8,9,10,15,15,9,4,1,0)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,xs,ys)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,xs,ys)


def draw_bishop(px,py,white_piece):
    # Same v92 bishop: round finial, compact body/cut and flat pedestal.
    sy = py + SHAPE_Y_FIX
    fill = WHITE_RGB if white_piece else BLACK_RGB
    outline = BLACK_RGB if white_piece else WHITE_RGB
    body_x = (8,6,5,4,3,3,4,5,7,9,11,12,13,13,12,11,10,9,8)
    body_y = (4,4,5,6,8,9,10,11,12,12,11,10,9,7,6,5,4,4,4)
    base_x = (2,14,14,2,2)
    base_y = (13,13,15,15,13)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    ti_draw.fill_circle(px+8,sy+2,2)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    ti_draw.draw_circle(px+8,sy+2,2)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,body_x,body_y)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,body_x,body_y)
    ti_draw.draw_line(px+10,sy+5,px+7,sy+9)
    ti_draw.draw_line(px+11,sy+5,px+8,sy+9)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,base_x,base_y)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,base_x,base_y)


def draw_queen(px,py,white_piece):
    # Same v92 queen silhouette: detached finial, crown, and king-style base.
    sy = py + SHAPE_Y_FIX
    fill = WHITE_RGB if white_piece else BLACK_RGB
    outline = BLACK_RGB if white_piece else WHITE_RGB
    xs = (2,3,5,6,8,10,11,13,14,15,14,11,13,14,2,3,5,2,1,2)
    ys = (5,5,4,3,5,3,4,5,5,6,8,12,14,15,15,14,12,8,6,5)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    ti_draw.fill_circle(px+8,sy+1,1)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    ti_draw.draw_circle(px+8,sy+1,1)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,xs,ys)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,xs,ys)


def draw_king(px,py,white_piece,checked):
    # Same v92 king silhouette. CHECK changes only the fill color.
    fill = WHITE_RGB if white_piece else BLACK_RGB
    outline = BLACK_RGB if white_piece else WHITE_RGB
    if checked:
        fill = CHECK_RGB
    xs = (7,9,9,11,11,9,9,14,15,14,11,13,14,2,3,5,2,1,2,7,7,5,5,7,7)
    ys = (0,0,2,2,4,4,5,5,6,8,12,14,15,15,14,12,8,6,5,5,4,4,2,2,0)

    ti_draw.set_color(fill[0],fill[1],fill[2])
    draw_offset_fill_poly(px,py,xs,ys)
    ti_draw.set_color(outline[0],outline[1],outline[2])
    draw_offset_poly(px,py,xs,ys)


def draw_piece_shape(p,px,py,white_piece,checked=False):
    lower = p.lower()
    if lower == "p":
        draw_pawn(px,py,white_piece)
    elif lower == "r":
        draw_rook(px,py,white_piece)
    elif lower == "n":
        draw_knight(px,py,white_piece)
    elif lower == "b":
        draw_bishop(px,py,white_piece)
    elif lower == "q":
        draw_queen(px,py,white_piece)
    elif lower == "k":
        draw_king(px,py,white_piece,checked)

cursor_x = 4
cursor_y = 6

# Each human side remembers its own cursor position.
white_cursor_x = 4
white_cursor_y = 6
black_cursor_x = 4
black_cursor_y = 1

# Last completed move highlight (AI in 1-player, every move in 2-player).
last_ai_from_x = -1
last_ai_from_y = -1
last_ai_to_x = -1
last_ai_to_y = -1

selected_x = -1
selected_y = -1

turn = 0
# 0 = white
# 1 = black

# Game mode. 0 means the player-count menu is active.
player_count = 0
player_select = 1
difficulty_select = 1
difficulty_menu = False
color_select = 0
color_menu = False
human_side = 0
ai_side = 1
thinking = False

message = "SELECT PIECE"
winner = ""
stalemate = False
quit_confirm = False
check_turn = -1
# -1 = no check, 0 = white in check, 1 = black in check

# Pawn promotion state.
promotion_pending = False
promotion_x = -1
promotion_y = -1
promotion_side = -1
promotion_index = 0
PROMOTION_CHOICES = "qrbn"

white_score = 0
black_score = 0

# Keys are always lowercase piece types.
white_captures = {
    "p":0,
    "n":0,
    "b":0,
    "r":0,
    "q":0
}

black_captures = {
    "p":0,
    "n":0,
    "b":0,
    "r":0,
    "q":0
}

# ------------------------------------------------------------
# SPECIAL MOVE STATE
# ------------------------------------------------------------
# Castling rights are permanently lost when the king moves,
# when the original rook moves, or when that rook is captured.
white_castle_k = True
white_castle_q = True
black_castle_k = True
black_castle_q = True

# En-passant target square.
# -1,-1 means there is currently no en-passant capture available.
en_passant_x = -1
en_passant_y = -1

def is_white(p):
    return p in WHITE

def is_black(p):
    return p in BLACK

def same_color(a,b):
    if is_white(a) and is_white(b):
        return True
    if is_black(a) and is_black(b):
        return True
    return False

def read_key():
    try:
        return int(ti_system.get_key(0))
    except:
        return 0

def wait_for_key():
    # Wait until no previous key is held.
    while read_key() != 0:
        pass

    while True:
        k = read_key()

        if k != 0:
            # One physical press = one cursor movement.
            while read_key() != 0:
                pass
            return k

def fill_rect_at(x,y,w,h):
    ti_draw.fill_rect(
        x,
        y + SHAPE_Y_FIX,
        w,
        h
    )

def draw_rect_at(x,y,w,h):
    ti_draw.draw_rect(
        x,
        y + SHAPE_Y_FIX,
        w,
        h
    )

def square_color(x,y):
    if (x+y)%2 == 0:
        return (205,185,145)
    return (120,80,45)

def draw_piece(x,y):
    p = board[y][x]
    if p == ".":
        return

    # The piece origin is the top-left of the 16x16 colored interior.
    px = BOARD_X + x*SQUARE + 1
    py = BOARD_Y + y*SQUARE + 1

    checked = (p == "k" and check_turn == 0) or \
              (p == "K" and check_turn == 1)
    draw_piece_shape(p,px,py,is_white(p),checked)


def draw_tile_highlight(x,y,color):
    # The ONLY drawing path for yellow, cyan and green board highlights.
    # x,y are tile coordinates: 0,0 upper-left through 7,7 lower-right.
    # The highlight occupies the outer edge of the 18x18 tile, while pieces
    # remain confined to the inner 16x16 area.
    ti_draw.set_color(color[0],color[1],color[2])
    draw_rect_at(
        BOARD_X + x*SQUARE,
        BOARD_Y + y*SQUARE,
        SQUARE-1,
        SQUARE-1
    )


def clear_tile_highlight(x,y):
    # Restore the exact same border pixels using this tile's own board color.
    col = square_color(x,y)
    draw_tile_highlight(x,y,col)


def refresh_tile_highlight(x,y):
    # Re-evaluate only the highlight state for this tile. Piece/square drawing
    # is completely independent from this path.
    clear_tile_highlight(x,y)

    if x == cursor_x and y == cursor_y:
        draw_tile_highlight(x,y,(255,220,0))
    elif x == selected_x and y == selected_y:
        draw_tile_highlight(x,y,(0,200,255))
    elif (x == last_ai_from_x and y == last_ai_from_y) or \
         (x == last_ai_to_x and y == last_ai_to_y):
        draw_tile_highlight(x,y,(0,180,0))


def draw_square(x,y):
    # Gameplay redraw: repaint only this tile's 16x16 interior and its piece.
    # The 1-pixel outer edge is owned by the independent highlight system.
    px = BOARD_X + x*SQUARE
    py = BOARD_Y + y*SQUARE

    col = square_color(x,y)
    ti_draw.set_color(col[0],col[1],col[2])
    fill_rect_at(px,py,SQUARE-1,SQUARE-1)
    draw_piece(x,y)

def draw_empty_board():
    # Initial board paint is much cheaper than drawing all 64 tiles. First
    # paint the complete 144x144 board in the light color, then overwrite only
    # the 32 dark tiles. On this Evo-T fill_rect() paints inside the requested
    # rectangle boundary, so the tile-sized fills must start one pixel up/left
    # of the logical tile origin to align with draw_rect()-based highlights.
    ti_draw.set_color(205,185,145)
    fill_rect_at(
        BOARD_X-1,
        BOARD_Y-1,
        SQUARE*8+1,
        SQUARE*8+1
    )

    ti_draw.set_color(120,80,45)
    for y in range(8):
        x = 1 if y%2 == 0 else 0
        while x < 8:
            fill_rect_at(
                BOARD_X + x*SQUARE-1,
                BOARD_Y + y*SQUARE-1,
                SQUARE+1,
                SQUARE+1
            )
            x = x+2

def draw_starting_pieces():
    # draw_empty_board() creates a completely clean board first. Only after
    # that do we add the 32 pieces from the normal starting position.
    for y in (0,1,6,7):
        for x in range(8):
            draw_piece(x,y)

def draw_left_panel():
    # Repaint the COMPLETE left panel in one solid block.
    # This is intentionally drawn before all left-side text so
    # no old white erase rectangles can remain visible.
    ti_draw.set_color(
        LEFT_BG[0],
        LEFT_BG[1],
        LEFT_BG[2]
    )

    # Logical y=18 maps to screen y=0 because of SHAPE_Y_FIX.
    # Height 210 covers the complete ti_draw area.
    fill_rect_at(
        0,
        18,
        LEFT_PANEL_W,
        210
    )

    # Static text must be redrawn after painting the background.
    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(5,26,"CHESS")
    ti_draw.draw_text(5,153,"CLEAR")
    ti_draw.draw_text(5,169,"MENU")

def draw_status():
    # Put the blue-gray panel on top of any previous left-side drawing.
    draw_left_panel()

    if quit_confirm:
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,53,"RETURN?")

        # Keep the complete confirmation inside the area that
        # draw_status() clears when the dialog is dismissed.
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,85,"ENTER")

        ti_draw.set_color(0,170,0)
        ti_draw.draw_text(57,85,"YES")

        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,105,"CLEAR")

        ti_draw.set_color(220,0,0)
        ti_draw.draw_text(57,105,"NO")
        return

    if winner != "" or stalemate:
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,53,"GAME")
        ti_draw.draw_text(5,69,"OVER")
        draw_game_over_popup()
        return

    if promotion_pending:
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,53,"PROMOTE")

        i = 0

        while i < 4:
            x = 6 + i*22
            y = 84

            if i == promotion_index:
                ti_draw.set_color(255,180,0)
                draw_rect_at(x-2,y-2,20,20)
                draw_rect_at(x-1,y-1,18,18)

            choice = PROMOTION_CHOICES[i]

            if promotion_side == 0:
                piece = choice
            else:
                piece = choice.upper()

            # Always draw promotion choices as player 2 pieces for readability.
            draw_piece_shape(piece,x,y,False)

            i = i + 1

        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,111,"ENTER")
        return

    if thinking:
        if ai_side == 0:
            ti_draw.set_color(0,0,180)
            ti_draw.draw_text(5,53,"WHITE")
        else:
            ti_draw.set_color(180,0,0)
            ti_draw.draw_text(5,53,"BLACK")
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,69,"THINKING")
        return

    if turn == 0:
        ti_draw.set_color(0,0,180)
        ti_draw.draw_text(5,53,"WHITE")
    else:
        ti_draw.set_color(180,0,0)
        ti_draw.draw_text(5,53,"BLACK")

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(5,69,"TO MOVE")

    if check_turn == turn:
        ti_draw.set_color(220,0,0)
        ti_draw.draw_text(5,85,"CHECK")

    ti_draw.set_color(0,0,0)

    if message == "SELECT PIECE":
        ti_draw.draw_text(5,103,"SELECT")
        ti_draw.draw_text(5,119,"PIECE")
    elif message == "SELECT TARGET":
        ti_draw.draw_text(5,103,"SELECT")
        ti_draw.draw_text(5,119,"TARGET")
    elif message == "ILLEGAL MOVE":
        ti_draw.draw_text(5,103,"ILLEGAL")
        ti_draw.draw_text(5,119,"MOVE")
    else:
        ti_draw.draw_text(5,103,message)


def draw_game_over_popup():
    if winner != "":
        result = winner + " WON"
    else:
        result = "NO ONE WON"

    lines = (result,"ENTER  AGAIN","CLEAR  RETURN")
    longest = len(lines[0])
    if len(lines[1]) > longest:
        longest = len(lines[1])
    if len(lines[2]) > longest:
        longest = len(lines[2])

    # Preserve the original content position, but extend only the right
    # side of the popup by 20 pixels.
    content_w = longest*8 + 16
    box_w = content_w + 20
    box_h = 76
    box_x = BOARD_X + (SQUARE*8-content_w)//2
    box_y = BOARD_Y + (SQUARE*8-box_h)//2

    ti_draw.set_color(245,245,245)
    fill_rect_at(box_x,box_y,box_w,box_h)

    ti_draw.set_color(255,220,0)
    draw_rect_at(box_x,box_y,box_w-1,box_h-1)
    draw_rect_at(box_x+1,box_y+1,box_w-3,box_h-3)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(box_x+(content_w-len(lines[0])*8)//2,box_y+8,lines[0])
    ti_draw.draw_text(box_x+(content_w-len(lines[1])*8)//2,box_y+30,lines[1])
    ti_draw.draw_text(box_x+(content_w-len(lines[2])*8)//2,box_y+52,lines[2])


def score_text():
    diff = white_score - black_score

    if diff > 0:
        return "W+" + str(diff)

    if diff < 0:
        return "B+" + str(-diff)

    return "+0"

def draw_score():
    # Clear only the small area below the board.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(
        BOARD_X,
        SCORE_Y-3,
        144,
        19
    )

    text = score_text()

    # Center the score under the exact 144-pixel board width.
    board_width = SQUARE*8
    text_width = len(text)*8
    tx = BOARD_X + (board_width-text_width)//2

    # +0 remains neutral black.
    if text == "+0":
        ti_draw.set_color(0,0,0)
    elif text[0] == "W":
        # White side uses the same blue status color.
        ti_draw.set_color(0,0,180)
    else:
        # Black side uses the same red status color.
        ti_draw.set_color(180,0,0)

    ti_draw.draw_text(
        tx,
        SCORE_Y,
        text
    )

def draw_capture_column(x,captures):
    # Highest-value pieces first; only types that were actually captured.
    order = ["q","r","b","n","p"]
    row = 0

    for piece in order:
        count = captures[piece]

        if count > 0:
            py = CAPTURE_Y + 22 + row*CAPTURE_ROW

            # Black icon in both columns.
            # W/B heading indicates which player made the captures.
            draw_piece_shape(piece,x,py,False)

            ti_draw.set_color(0,0,0)
            ti_draw.draw_text(
                x+16,
                py+1,
                str(count)
            )

            row = row + 1

def draw_captures():
    # Clear the panel without touching the chessboard.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(
        CAPTURE_X,
        CAPTURE_Y,
        CAPTURE_W,
        120
    )

    # Player headings.
    ti_draw.set_color(0,0,180)
    ti_draw.draw_text(
        CAPTURE_X+3,
        CAPTURE_Y,
        "W"
    )

    ti_draw.set_color(180,0,0)
    ti_draw.draw_text(
        CAPTURE_X+34,
        CAPTURE_Y,
        "B"
    )

    # Two 24-pixel-ish columns.
    draw_capture_column(
        CAPTURE_X,
        white_captures
    )

    draw_capture_column(
        CAPTURE_X+30,
        black_captures
    )

def save_active_cursor():
    global white_cursor_x, white_cursor_y
    global black_cursor_x, black_cursor_y

    if turn == 0:
        white_cursor_x = cursor_x
        white_cursor_y = cursor_y
    else:
        black_cursor_x = cursor_x
        black_cursor_y = cursor_y


def switch_to_turn_cursor():
    global cursor_x, cursor_y

    old_x = cursor_x
    old_y = cursor_y

    # Switch the logical cursor first. Border restoration then knows that the
    # old square must no longer receive the yellow cursor frame.
    if turn == 0:
        cursor_x = white_cursor_x
        cursor_y = white_cursor_y
    else:
        cursor_x = black_cursor_x
        cursor_y = black_cursor_y

    refresh_tile_highlight(old_x,old_y)
    draw_tile_highlight(cursor_x,cursor_y,(255,220,0))


def clear_ai_move_highlight():
    global last_ai_from_x, last_ai_from_y
    global last_ai_to_x, last_ai_to_y

    old_from_x = last_ai_from_x
    old_from_y = last_ai_from_y
    old_to_x = last_ai_to_x
    old_to_y = last_ai_to_y

    # Clear the state before refreshing the frames so they are no longer
    # interpreted as green-highlighted squares.
    last_ai_from_x = -1
    last_ai_from_y = -1
    last_ai_to_x = -1
    last_ai_to_y = -1

    if old_from_x >= 0:
        refresh_tile_highlight(old_from_x,old_from_y)

    if old_to_x >= 0 and (old_to_x != old_from_x or old_to_y != old_from_y):
        refresh_tile_highlight(old_to_x,old_to_y)


def draw_menu_choice(text_x,text_y,text,selected,r,g,b):
    # Clear the complete option row, not merely the previous calculated box.
    # This guarantees that no edge of an old yellow frame can remain visible.
    ti_draw.set_color(LEFT_BG[0],LEFT_BG[1],LEFT_BG[2])
    fill_rect_at(64,text_y-7,112,28)

    # The Evo-T menu font is slightly wider than the estimate used in v66.
    # Keep seven pixels on the left and add four extra pixels on the right.
    box_x = text_x-7
    box_y = text_y-4
    box_w = len(text)*9+18
    box_h = 24

    if selected:
        ti_draw.set_color(255,180,0)

        # One native outline rectangle is cheaper than four Python line calls.
        draw_rect_at(box_x,box_y,box_w-1,box_h-1)

    ti_draw.set_color(r,g,b)
    ti_draw.draw_text(text_x,text_y,text)


def draw_player_choice(value,selected):
    if value == 1:
        draw_menu_choice(77,101,"1 PLAYER",selected,0,0,0)
    else:
        draw_menu_choice(77,129,"2 PLAYERS",selected,0,0,0)


def update_player_select(old_value,new_value):
    draw_player_choice(old_value,False)
    draw_player_choice(new_value,True)


def draw_color_choice(value,selected):
    if value == 0:
        draw_menu_choice(89,105,"WHITE",selected,0,0,0)
    else:
        draw_menu_choice(89,133,"BLACK",selected,0,0,0)


def update_color_select(old_value,new_value):
    draw_color_choice(old_value,False)
    draw_color_choice(new_value,True)


def draw_difficulty_choice(value,selected):
    if value == 1:
        draw_menu_choice(85,101,"EASY",selected,0,170,0)
    elif value == 2:
        draw_menu_choice(85,129,"MEDIUM",selected,220,160,0)
    else:
        draw_menu_choice(85,157,"HARD",selected,220,0,0)


def update_difficulty_select(old_value,new_value):
    draw_difficulty_choice(old_value,False)
    draw_difficulty_choice(new_value,True)


def draw_player_select_screen():
    ti_draw.clear()
    ti_draw.set_color(LEFT_BG[0],LEFT_BG[1],LEFT_BG[2])
    fill_rect_at(0,18,320,210)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(96,45,"CHESS")
    ti_draw.draw_text(72,73,"PLAYERS")
    draw_player_choice(1,player_select == 1)
    draw_player_choice(2,player_select == 2)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(70,166,"UP/DOWN")
    ti_draw.draw_text(82,182,"ENTER")
    ti_draw.draw_text(240,166,"CLEAR")
    ti_draw.draw_text(244,182,"QUIT")


def draw_color_screen():
    ti_draw.clear()
    ti_draw.set_color(LEFT_BG[0],LEFT_BG[1],LEFT_BG[2])
    fill_rect_at(0,18,320,210)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(96,45,"CHESS")
    ti_draw.draw_text(76,73,"YOUR COLOR")
    draw_color_choice(0,color_select == 0)
    draw_color_choice(1,color_select == 1)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(70,170,"UP/DOWN")
    ti_draw.draw_text(82,186,"ENTER")
    ti_draw.draw_text(240,170,"CLEAR")
    ti_draw.draw_text(244,186,"RETURN")


def draw_difficulty_screen():
    ti_draw.clear()
    ti_draw.set_color(LEFT_BG[0],LEFT_BG[1],LEFT_BG[2])
    fill_rect_at(0,18,320,210)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(96,45,"CHESS")
    ti_draw.draw_text(68,69,"DIFFICULTY")
    draw_difficulty_choice(1,difficulty_select == 1)
    draw_difficulty_choice(2,difficulty_select == 2)
    draw_difficulty_choice(3,difficulty_select == 3)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(70,184,"UP/DOWN")
    ti_draw.draw_text(82,200,"ENTER")
    ti_draw.draw_text(240,184,"CLEAR")
    ti_draw.draw_text(244,200,"RETURN")


def apply_difficulty():
    global AI_DEPTH, AI_RANDOMNESS
    if difficulty_select == 1:
        AI_DEPTH = 1
        AI_RANDOMNESS = 6
    elif difficulty_select == 2:
        AI_DEPTH = 2
        AI_RANDOMNESS = 3
    else:
        AI_DEPTH = 3
        AI_RANDOMNESS = 1


def reset_game_state():
    global board, cursor_x, cursor_y
    global white_cursor_x, white_cursor_y
    global black_cursor_x, black_cursor_y
    global last_ai_from_x, last_ai_from_y
    global last_ai_to_x, last_ai_to_y
    global selected_x, selected_y, turn, message
    global winner, stalemate, quit_confirm, check_turn
    global promotion_pending, promotion_x, promotion_y
    global promotion_side, promotion_index
    global white_score, black_score
    global white_castle_k, white_castle_q
    global black_castle_k, black_castle_q
    global en_passant_x, en_passant_y
    global white_captures, black_captures
    global thinking
    global human_side, ai_side

    board = [
        ["R","N","B","Q","K","B","N","R"],
        ["P","P","P","P","P","P","P","P"],
        [".",".",".",".",".",".",".","."],
        [".",".",".",".",".",".",".","."],
        [".",".",".",".",".",".",".","."],
        [".",".",".",".",".",".",".","."],
        ["p","p","p","p","p","p","p","p"],
        ["r","n","b","q","k","b","n","r"]
    ]

    white_cursor_x = 4
    white_cursor_y = 6
    black_cursor_x = 4
    black_cursor_y = 1
    if player_count == 1 and human_side == 1:
        cursor_x = black_cursor_x
        cursor_y = black_cursor_y
    else:
        cursor_x = white_cursor_x
        cursor_y = white_cursor_y
    last_ai_from_x = -1
    last_ai_from_y = -1
    last_ai_to_x = -1
    last_ai_to_y = -1
    selected_x = -1
    selected_y = -1
    turn = 0
    message = "SELECT PIECE"
    winner = ""
    stalemate = False
    quit_confirm = False
    check_turn = -1
    thinking = False

    promotion_pending = False
    promotion_x = -1
    promotion_y = -1
    promotion_side = -1
    promotion_index = 0

    white_score = 0
    black_score = 0

    white_castle_k = True
    white_castle_q = True
    black_castle_k = True
    black_castle_q = True

    en_passant_x = -1
    en_passant_y = -1

    white_captures = {"p":0,"n":0,"b":0,"r":0,"q":0}
    black_captures = {"p":0,"n":0,"b":0,"r":0,"q":0}


def perform_ai_move(move):
    global turn, check_turn, winner, stalemate
    global message
    global last_ai_from_x, last_ai_from_y
    global last_ai_to_x, last_ai_to_y

    if move is None:
        return

    y1 = move[0]
    x1 = move[1]
    y2 = move[2]
    x2 = move[3]
    promotion = move[4]

    if promotion == ".":
        promotion = None

    # Remove the previous green AI marker, but never move the human cursor.
    clear_ai_move_highlight()

    old_check_turn = check_turn
    state = make_move(y1,x1,y2,x2,ai_side,True,promotion)

    captured_piece = state[6]
    capture_y = state[7]
    capture_x = state[8]
    rook_from_x = state[9]
    rook_to_x = state[10]

    # Store the new AI move, redraw only the changed interiors, then update
    # the two independent highlight frames explicitly.
    last_ai_from_x = x1
    last_ai_from_y = y1
    last_ai_to_x = x2
    last_ai_to_y = y2

    draw_square(x1,y1)
    draw_square(x2,y2)
    refresh_tile_highlight(x1,y1)
    refresh_tile_highlight(x2,y2)

    if captured_piece != "." and (capture_y != y2 or capture_x != x2):
        draw_square(
            capture_x,
            capture_y
        )

    if rook_from_x >= 0:
        draw_square(
            rook_from_x,
            y2
        )
        draw_square(
            rook_to_x,
            y2
        )

    if captured_piece != ".":
        draw_captures()
        draw_score()

    if captured_piece == "K":
        winner = "WHITE"
        check_turn = -1
        draw_status()
        return
    if captured_piece == "k":
        winner = "BLACK"
        check_turn = -1
        draw_status()
        return

    turn = human_side

    if is_in_check(turn):
        check_turn = turn
    else:
        check_turn = -1

    redraw_check_change(old_check_turn,check_turn)

    if not has_legal_move(turn):
        if check_turn == turn:
            winner = "BLACK"
        else:
            stalemate = True

    message = "SELECT PIECE"
    draw_status()


def draw_initial_screen():
    ti_draw.clear()

    # Keep all non-left UI areas white.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(CAPTURE_X,18,320-CAPTURE_X,192)
    fill_rect_at(BOARD_X,190,144,20)

    # Paint a clean board first: one full-board fill plus only the 32 tiles
    # of the opposite color. Pieces are added only after the board is complete.
    draw_empty_board()
    draw_starting_pieces()

    # File labels
    ti_draw.set_color(0,0,0)
    letters = "abcdefgh"

    for x in range(8):
        px = BOARD_X + x*SQUARE + 5
        ti_draw.draw_text(
            px,
            BOARD_Y+145,
            letters[x]
        )

    # Rank labels
    for y in range(8):
        py = BOARD_Y + y*SQUARE + 1
        ti_draw.draw_text(
            BOARD_X-11,
            py,
            str(8-y)
        )

    draw_status()
    draw_captures()
    draw_score()

    # Draw initial cursor last, independently from square rendering.
    draw_tile_highlight(cursor_x,cursor_y,(255,220,0))

def path_clear(y1,x1,y2,x2):
    step_x = 0
    step_y = 0

    if x2 > x1:
        step_x = 1
    elif x2 < x1:
        step_x = -1

    if y2 > y1:
        step_y = 1
    elif y2 < y1:
        step_y = -1

    x = x1 + step_x
    y = y1 + step_y

    while x != x2 or y != y2:
        if board[y][x] != ".":
            return False

        x = x + step_x
        y = y + step_y

    return True

def is_valid(p,y1,x1,y2,x2,target):
    dx = abs(x2-x1)
    dy = abs(y2-y1)

    if x1 == x2 and y1 == y2:
        return False

    # White pawn
    if p == "p":
        if x1 == x2 and target == ".":
            if y2 == y1-1:
                return True

            if y1 == 6 and y2 == 4:
                if board[5][x1] == ".":
                    return True

        if dx == 1 and y2 == y1-1:
            # Normal capture
            if target != ".":
                return True

            # En passant
            if x2 == en_passant_x and y2 == en_passant_y:
                if board[y1][x2] == "P":
                    return True

        return False

    # Black pawn
    if p == "P":
        if x1 == x2 and target == ".":
            if y2 == y1+1:
                return True

            if y1 == 1 and y2 == 3:
                if board[2][x1] == ".":
                    return True

        if dx == 1 and y2 == y1+1:
            # Normal capture
            if target != ".":
                return True

            # En passant
            if x2 == en_passant_x and y2 == en_passant_y:
                if board[y1][x2] == "p":
                    return True

        return False

    # Knight
    if p == "n" or p == "N":
        if dx == 1 and dy == 2:
            return True
        if dx == 2 and dy == 1:
            return True
        return False

    # King
    if p == "k" or p == "K":
        # Normal king move
        if dx <= 1 and dy <= 1:
            return True

        # Castling: e-file to c-file or g-file.
        if dy == 0 and dx == 2:
            return can_castle(
                p,
                y1,
                x1,
                y2,
                x2
            )

        return False

    # Rook
    if p == "r" or p == "R":
        if x1 == x2 or y1 == y2:
            return path_clear(
                y1,x1,y2,x2
            )
        return False

    # Bishop
    if p == "b" or p == "B":
        if dx == dy:
            return path_clear(
                y1,x1,y2,x2
            )
        return False

    # Queen
    if p == "q" or p == "Q":
        if x1 == x2 or y1 == y2 or dx == dy:
            return path_clear(
                y1,x1,y2,x2
            )
        return False

    return False


def find_king(side):
    # White king = lowercase k
    # Black king = uppercase K
    if side == 0:
        king = "k"
    else:
        king = "K"

    for y in range(8):
        for x in range(8):
            if board[y][x] == king:
                return (y,x)

    return None

def attacks_square(p,y1,x1,y2,x2):
    dx = abs(x2-x1)
    dy = abs(y2-y1)

    if x1 == x2 and y1 == y2:
        return False

    # Pawns attack diagonally even when the square is empty.
    if p == "p":
        return dx == 1 and y2 == y1-1

    if p == "P":
        return dx == 1 and y2 == y1+1

    # Knight
    if p == "n" or p == "N":
        if dx == 1 and dy == 2:
            return True
        if dx == 2 and dy == 1:
            return True
        return False

    # King
    if p == "k" or p == "K":
        return dx <= 1 and dy <= 1

    # Rook
    if p == "r" or p == "R":
        if x1 == x2 or y1 == y2:
            return path_clear(y1,x1,y2,x2)
        return False

    # Bishop
    if p == "b" or p == "B":
        if dx == dy:
            return path_clear(y1,x1,y2,x2)
        return False

    # Queen
    if p == "q" or p == "Q":
        if x1 == x2 or y1 == y2 or dx == dy:
            return path_clear(y1,x1,y2,x2)
        return False

    return False

def is_square_attacked(y,x,by_side):
    for sy in range(8):
        for sx in range(8):
            p = board[sy][sx]

            if by_side == 0:
                own_piece = is_white(p)
            else:
                own_piece = is_black(p)

            if own_piece:
                if attacks_square(p,sy,sx,y,x):
                    return True

    return False

def is_in_check(side):
    pos = find_king(side)

    if pos is None:
        return False

    king_y = pos[0]
    king_x = pos[1]

    if side == 0:
        enemy = 1
    else:
        enemy = 0

    return is_square_attacked(
        king_y,
        king_x,
        enemy
    )

def can_castle(p,y1,x1,y2,x2):
    # Castling is only possible from the king's original square.
    if p == "k":
        side = 0
        home_y = 7
        rook = "r"

        if y1 != home_y or x1 != 4 or y2 != home_y:
            return False

        if x2 == 6:
            allowed = white_castle_k
            rook_x = 7
            empty_squares = [5,6]
            king_path = [5,6]
        elif x2 == 2:
            allowed = white_castle_q
            rook_x = 0
            empty_squares = [1,2,3]
            king_path = [3,2]
        else:
            return False

    elif p == "K":
        side = 1
        home_y = 0
        rook = "R"

        if y1 != home_y or x1 != 4 or y2 != home_y:
            return False

        if x2 == 6:
            allowed = black_castle_k
            rook_x = 7
            empty_squares = [5,6]
            king_path = [5,6]
        elif x2 == 2:
            allowed = black_castle_q
            rook_x = 0
            empty_squares = [1,2,3]
            king_path = [3,2]
        else:
            return False
    else:
        return False

    if not allowed:
        return False

    # The original rook must still be present.
    if board[home_y][rook_x] != rook:
        return False

    # Every square between king and rook must be empty.
    for x in empty_squares:
        if board[home_y][x] != ".":
            return False

    # A player may not castle while already in check.
    if is_in_check(side):
        return False

    # Test the king on every square it crosses.
    # Temporarily remove it from e1/e8 so discovered attacks
    # through the original king square are also detected.
    for x in king_path:
        old_target = board[home_y][x]

        board[home_y][4] = "."
        board[home_y][x] = p

        attacked = is_in_check(side)

        board[home_y][x] = old_target
        board[home_y][4] = p

        if attacked:
            return False

    return True


def would_leave_king_in_check(
    side,
    y1,
    x1,
    y2,
    x2
):
    p = board[y1][x1]
    target = board[y2][x2]

    # Detect special moves before modifying the board.
    is_castle = (
        (p == "k" or p == "K") and
        y1 == y2 and
        abs(x2-x1) == 2
    )

    is_en_passant = (
        (p == "p" or p == "P") and
        target == "." and
        abs(x2-x1) == 1 and
        x2 == en_passant_x and
        y2 == en_passant_y
    )

    captured_ep = "."
    ep_capture_y = -1

    if is_en_passant:
        ep_capture_y = y1
        captured_ep = board[ep_capture_y][x2]

    # Temporarily make the main move.
    board[y2][x2] = p
    board[y1][x1] = "."

    # Temporarily remove the en-passant pawn.
    if is_en_passant:
        board[ep_capture_y][x2] = "."

    # Temporarily move the rook during castling.
    rook_from_x = -1
    rook_to_x = -1
    rook_piece = "."

    if is_castle:
        if x2 == 6:
            rook_from_x = 7
            rook_to_x = 5
        else:
            rook_from_x = 0
            rook_to_x = 3

        rook_piece = board[y1][rook_from_x]
        board[y1][rook_to_x] = rook_piece
        board[y1][rook_from_x] = "."

    checked = is_in_check(side)

    # Restore castling rook.
    if is_castle:
        board[y1][rook_from_x] = rook_piece
        board[y1][rook_to_x] = "."

    # Restore en-passant pawn.
    if is_en_passant:
        board[ep_capture_y][x2] = captured_ep

    # Restore original source and destination.
    board[y1][x1] = p
    board[y2][x2] = target

    return checked



# Reused minimax state buffers. Hard mode needs at most three simultaneous
# simulated moves (root + two recursive plies); one spare slot is kept.
SEARCH_STATES = [[None]*14 for _ in range(4)]

# ------------------------------------------------------------
# MOVE ENGINE
# ------------------------------------------------------------
# make_move() changes only chess/game state. It does not draw anything,
# change the side to move, or handle the promotion-selection UI.
#
# The returned state is intentionally a compact list instead of a dict.
# minimax can later keep one such state per recursion level and call
# undo_move() after evaluating a branch.
#
# State indexes:
#  0 piece, 1 y1, 2 x1, 3 y2, 4 x2, 5 original target
#  6 captured piece, 7 capture y, 8 capture x
#  9 rook from x, 10 rook to x, 11 rook piece
# 12..15 old castling rights
# 16..17 old en-passant target
# 18 old white score, 19 old black score
# 20 capture side (-1 if none), 21 capture type, 22 old capture count

def make_move(y1,x1,y2,x2,side,update_score=True,promotion_piece=None,search_slot=0):
    global white_castle_k, white_castle_q
    global black_castle_k, black_castle_q
    global en_passant_x, en_passant_y
    global white_score, black_score

    p = board[y1][x1]
    target = board[y2][x2]

    old_castle_bits = (1 if white_castle_k else 0) | \
                      (2 if white_castle_q else 0) | \
                      (4 if black_castle_k else 0) | \
                      (8 if black_castle_q else 0)

    if en_passant_x < 0:
        old_ep = -1
    else:
        old_ep = en_passant_x + en_passant_y*8

    if update_score:
        old_white_score = white_score
        old_black_score = black_score

    castling_move = ((p == "k" or p == "K") and y1 == y2 and abs(x2-x1) == 2)
    en_passant_move = ((p == "p" or p == "P") and target == "." and
                       abs(x2-x1) == 1 and x2 == en_passant_x and y2 == en_passant_y)

    captured_piece = target
    capture_x = x2
    capture_y = y2

    if en_passant_move:
        capture_y = y1
        captured_piece = board[capture_y][x2]

    capture_side = -1
    capture_type = "."
    old_capture_count = 0

    if update_score and captured_piece != ".":
        capture_type = captured_piece.lower()
        if capture_type in PIECE_VALUES:
            value = PIECE_VALUES[capture_type]
            capture_side = side
            if side == 0:
                white_score = white_score + value
                if capture_type != "k":
                    old_capture_count = white_captures[capture_type]
                    white_captures[capture_type] = old_capture_count + 1
            else:
                black_score = black_score + value
                if capture_type != "k":
                    old_capture_count = black_captures[capture_type]
                    black_captures[capture_type] = old_capture_count + 1

    if p == "k":
        white_castle_k = False
        white_castle_q = False
    elif p == "K":
        black_castle_k = False
        black_castle_q = False
    elif p == "r":
        if y1 == 7 and x1 == 0:
            white_castle_q = False
        elif y1 == 7 and x1 == 7:
            white_castle_k = False
    elif p == "R":
        if y1 == 0 and x1 == 0:
            black_castle_q = False
        elif y1 == 0 and x1 == 7:
            black_castle_k = False

    if captured_piece == "r":
        if capture_y == 7 and capture_x == 0:
            white_castle_q = False
        elif capture_y == 7 and capture_x == 7:
            white_castle_k = False
    elif captured_piece == "R":
        if capture_y == 0 and capture_x == 0:
            black_castle_q = False
        elif capture_y == 0 and capture_x == 7:
            black_castle_k = False

    board[y2][x2] = p
    board[y1][x1] = "."

    if en_passant_move:
        board[capture_y][capture_x] = "."

    rook_from_x = -1
    rook_to_x = -1
    rook_piece = "."

    if castling_move:
        if x2 == 6:
            rook_from_x = 7
            rook_to_x = 5
        else:
            rook_from_x = 0
            rook_to_x = 3
        rook_piece = board[y2][rook_from_x]
        board[y2][rook_to_x] = rook_piece
        board[y2][rook_from_x] = "."

    if promotion_piece is not None:
        if side == 0:
            board[y2][x2] = promotion_piece.lower()
        else:
            board[y2][x2] = promotion_piece.upper()

    en_passant_x = -1
    en_passant_y = -1
    if (p == "p" or p == "P") and abs(y2-y1) == 2:
        en_passant_x = x1
        en_passant_y = (y1+y2)//2

    # Search nodes reuse a fixed buffer instead of allocating a new list.
    if not update_score:
        state = SEARCH_STATES[search_slot]
        state[0]=p; state[1]=y1; state[2]=x1; state[3]=y2; state[4]=x2
        state[5]=target; state[6]=captured_piece; state[7]=capture_y; state[8]=capture_x
        state[9]=rook_from_x; state[10]=rook_to_x; state[11]=rook_piece
        state[12]=old_castle_bits; state[13]=old_ep
        return state

    return [p,y1,x1,y2,x2,target,captured_piece,capture_y,capture_x,
            rook_from_x,rook_to_x,rook_piece,old_castle_bits,old_ep,
            old_white_score,old_black_score,capture_side,capture_type,old_capture_count]


def undo_move(state):
    global white_castle_k, white_castle_q
    global black_castle_k, black_castle_q
    global en_passant_x, en_passant_y
    global white_score, black_score

    p,y1,x1,y2,x2,target = state[0:6]
    captured_piece = state[6]
    capture_y = state[7]
    capture_x = state[8]
    rook_from_x = state[9]
    rook_to_x = state[10]
    rook_piece = state[11]

    board[y1][x1] = p
    board[y2][x2] = target

    if captured_piece != "." and (capture_y != y2 or capture_x != x2):
        board[capture_y][capture_x] = captured_piece

    if rook_from_x >= 0:
        board[y2][rook_from_x] = rook_piece
        board[y2][rook_to_x] = "."

    bits = state[12]
    white_castle_k = (bits & 1) != 0
    white_castle_q = (bits & 2) != 0
    black_castle_k = (bits & 4) != 0
    black_castle_q = (bits & 8) != 0

    old_ep = state[13]
    if old_ep < 0:
        en_passant_x = -1
        en_passant_y = -1
    else:
        en_passant_x = old_ep % 8
        en_passant_y = old_ep // 8

    # Search states stop at index 13.
    if len(state) == 14:
        return

    white_score = state[14]
    black_score = state[15]
    capture_side = state[16]
    capture_type = state[17]
    old_capture_count = state[18]

    if capture_side == 0 and capture_type != "." and capture_type != "k":
        white_captures[capture_type] = old_capture_count
    elif capture_side == 1 and capture_type != "." and capture_type != "k":
        black_captures[capture_type] = old_capture_count

# ------------------------------------------------------------
# AI SEARCH ENGINE
# ------------------------------------------------------------
# Move format:
# (y1, x1, y2, x2, promotion)
# promotion is "." for a normal move or q/r/b/n for promotion.
#
# Move generation uses piece-specific target squares instead of testing
# every piece against all 64 destinations. This matters on the Evo-T,
# where legal-move generation is called many thousands of times by
# minimax.

def pack_move(y1,x1,y2,x2,promotion=0):
    # 6 bits source, 6 bits target, 3 bits promotion. Max value < 32768.
    return (y1*8+x1) | ((y2*8+x2) << 6) | (promotion << 12)


def unpack_move(move):
    source = move & 63
    target = (move >> 6) & 63
    promotion = move >> 12
    if promotion:
        promo = PROMOTION_CHOICES[promotion-1]
    else:
        promo = "."
    return (source>>3,source&7,target>>3,target&7,promo)


def append_legal_move(moves,side,y1,x1,y2,x2):
    if y2 < 0 or y2 > 7 or x2 < 0 or x2 > 7:
        return
    p = board[y1][x1]
    target = board[y2][x2]
    if target != "." and same_color(p,target):
        return
    if not is_valid(p,y1,x1,y2,x2,target):
        return
    if would_leave_king_in_check(side,y1,x1,y2,x2):
        return
    if (p == "p" and y2 == 0) or (p == "P" and y2 == 7):
        moves.append(pack_move(y1,x1,y2,x2,1))
        moves.append(pack_move(y1,x1,y2,x2,2))
        moves.append(pack_move(y1,x1,y2,x2,3))
        moves.append(pack_move(y1,x1,y2,x2,4))
    else:
        moves.append(pack_move(y1,x1,y2,x2))


def append_sliding_moves(moves,side,y1,x1,directions):
    p = board[y1][x1]
    for direction in directions:
        dy = direction[0]
        dx = direction[1]
        y2 = y1 + dy
        x2 = x1 + dx
        while y2 >= 0 and y2 < 8 and x2 >= 0 and x2 < 8:
            target = board[y2][x2]
            if target != "." and same_color(p,target):
                break
            append_legal_move(moves,side,y1,x1,y2,x2)
            if target != ".":
                break
            y2 = y2 + dy
            x2 = x2 + dx


def get_legal_moves(side):
    moves = []
    for y1 in range(8):
        for x1 in range(8):
            p = board[y1][x1]
            if side == 0:
                own_piece = is_white(p)
            else:
                own_piece = is_black(p)
            if not own_piece:
                continue
            lower = p.lower()
            if lower == "p":
                direction = -1 if side == 0 else 1
                append_legal_move(moves,side,y1,x1,y1+direction,x1)
                append_legal_move(moves,side,y1,x1,y1+2*direction,x1)
                append_legal_move(moves,side,y1,x1,y1+direction,x1-1)
                append_legal_move(moves,side,y1,x1,y1+direction,x1+1)
            elif lower == "n":
                for offset in ((-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)):
                    append_legal_move(moves,side,y1,x1,y1+offset[0],x1+offset[1])
            elif lower == "b":
                append_sliding_moves(moves,side,y1,x1,((-1,-1),(-1,1),(1,-1),(1,1)))
            elif lower == "r":
                append_sliding_moves(moves,side,y1,x1,((-1,0),(1,0),(0,-1),(0,1)))
            elif lower == "q":
                append_sliding_moves(moves,side,y1,x1,((-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)))
            elif lower == "k":
                dy = -1
                while dy <= 1:
                    dx = -1
                    while dx <= 1:
                        if dx != 0 or dy != 0:
                            append_legal_move(moves,side,y1,x1,y1+dy,x1+dx)
                        dx = dx + 1
                    dy = dy + 1
                append_legal_move(moves,side,y1,x1,y1,x1-2)
                append_legal_move(moves,side,y1,x1,y1,x1+2)
    return moves


def move_order_score(move):
    source = move & 63
    target_sq = (move >> 6) & 63
    y1 = source >> 3
    x1 = source & 7
    y2 = target_sq >> 3
    x2 = target_sq & 7
    promotion = move >> 12
    p = board[y1][x1]
    target = board[y2][x2]
    score = 0
    captured = target
    if captured == "." and (p == "p" or p == "P") and x1 != x2:
        if x2 == en_passant_x and y2 == en_passant_y:
            captured = board[y1][x2]
    if captured != ".":
        score = score + AI_PIECE_VALUES[captured.lower()]*10
        score = score - AI_PIECE_VALUES[p.lower()]
    if promotion:
        score = score + AI_PIECE_VALUES[PROMOTION_CHOICES[promotion-1]]*10
    if p.lower() == "k" and abs(x2-x1) == 2:
        score = score + 50
    return score


def order_moves(moves):
    i = 1
    while i < len(moves):
        move = moves[i]
        score = move_order_score(move)
        j = i-1
        while j >= 0 and move_order_score(moves[j]) < score:
            moves[j+1] = moves[j]
            j = j-1
        moves[j+1] = move
        i = i+1

def evaluate_board():
    # Positive = good for black (the AI).
    # Negative = good for white.
    #
    # Keep this deliberately cheap: one board scan calculates material,
    # piece-square value and bishop counts. Development and king safety
    # are then determined with only a few fixed-square checks.
    score = 0
    white_king = False
    black_king = False
    white_bishops = 0
    black_bishops = 0

    for y in range(8):
        for x in range(8):
            p = board[y][x]

            if p == ".":
                continue

            lower = p.lower()

            if p == "k":
                white_king = True
            elif p == "K":
                black_king = True

            if p == "b":
                white_bishops = white_bishops + 1
            elif p == "B":
                black_bishops = black_bishops + 1

            value = AI_PIECE_VALUES[lower]
            center = AI_CENTER_TABLE[y*8+x]
            positional = 0

            # Piece-square values. These are intentionally small compared
            # with material so positional bonuses never justify losing a piece.
            if lower == "n":
                positional = center*6
            elif lower == "b":
                positional = center*4
            elif lower == "r":
                positional = center
            elif lower == "q":
                positional = center
            elif lower == "p":
                # Reward central pawns and safe advancement.
                if x == 3 or x == 4:
                    positional = positional + 8
                elif x == 2 or x == 5:
                    positional = positional + 3

                if is_black(p):
                    advancement = y-1
                else:
                    advancement = 6-y

                if advancement > 0:
                    positional = positional + advancement*3

            elif lower == "k":
                # Mild preference against wandering into the centre.
                positional = -center*3

            if is_black(p):
                score = score + value + positional
            else:
                score = score - value - positional

    # The current game also permits king capture, so handle that state
    # safely even though normal chess search should end at checkmate.
    if not white_king:
        return AI_MATE_SCORE

    if not black_king:
        return -AI_MATE_SCORE

    # Development: reward knights and bishops for leaving their original
    # squares. Fixed-square checks are much cheaper than generating moves.
    if board[7][1] != "n":
        score = score - AI_DEVELOPMENT_BONUS
    if board[7][6] != "n":
        score = score - AI_DEVELOPMENT_BONUS
    if board[7][2] != "b":
        score = score - AI_DEVELOPMENT_BONUS
    if board[7][5] != "b":
        score = score - AI_DEVELOPMENT_BONUS

    if board[0][1] != "N":
        score = score + AI_DEVELOPMENT_BONUS
    if board[0][6] != "N":
        score = score + AI_DEVELOPMENT_BONUS
    if board[0][2] != "B":
        score = score + AI_DEVELOPMENT_BONUS
    if board[0][5] != "B":
        score = score + AI_DEVELOPMENT_BONUS

    # King safety: a king on c/g after castling gets a small bonus.
    if board[7][2] == "k" or board[7][6] == "k":
        score = score - AI_CASTLED_BONUS

    if board[0][2] == "K" or board[0][6] == "K":
        score = score + AI_CASTLED_BONUS

    # Bishop pair is a useful positional signal and nearly free because
    # bishop counts were gathered during the normal material scan.
    if white_bishops >= 2:
        score = score - AI_BISHOP_PAIR_BONUS

    if black_bishops >= 2:
        score = score + AI_BISHOP_PAIR_BONUS

    return score


def minimax(depth,alpha,beta,side,ply=1):
    white_king = find_king(0)
    black_king = find_king(1)
    if white_king is None:
        return AI_MATE_SCORE + depth
    if black_king is None:
        return -AI_MATE_SCORE - depth
    if depth <= 0:
        return evaluate_board()
    moves = get_legal_moves(side)
    if len(moves) == 0:
        if is_in_check(side):
            if side == 0:
                return AI_MATE_SCORE + depth
            return -AI_MATE_SCORE - depth
        return 0
    order_moves(moves)
    if side == 1:
        best = -AI_INFINITY
        for move in moves:
            source = move & 63
            target = (move >> 6) & 63
            promotion_index = move >> 12
            promotion = PROMOTION_CHOICES[promotion_index-1] if promotion_index else None
            state = make_move(source>>3,source&7,target>>3,target&7,side,False,promotion,ply)
            value = minimax(depth-1,alpha,beta,0,ply+1)
            undo_move(state)
            if value > best:
                best = value
            if value > alpha:
                alpha = value
            if beta <= alpha:
                break
        return best
    best = AI_INFINITY
    for move in moves:
        source = move & 63
        target = (move >> 6) & 63
        promotion_index = move >> 12
        promotion = PROMOTION_CHOICES[promotion_index-1] if promotion_index else None
        state = make_move(source>>3,source&7,target>>3,target&7,side,False,promotion,ply)
        value = minimax(depth-1,alpha,beta,1,ply+1)
        undo_move(state)
        if value < best:
            best = value
        if value < beta:
            beta = value
        if beta <= alpha:
            break
    return best


def opening_development_active(side):
    # Keep the preference for up to the first three standard developments.
    # It stops once fewer than two centre pawns/knights remain undeveloped.
    if side == 1:
        remaining = (
            (board[1][3] == "P") +
            (board[1][4] == "P") +
            (board[0][1] == "N") +
            (board[0][6] == "N")
        )
    else:
        remaining = (
            (board[6][3] == "p") +
            (board[6][4] == "p") +
            (board[7][1] == "n") +
            (board[7][6] == "n")
        )

    return remaining >= 2


def is_opening_development_move(side,move):
    source = move & 63
    target = (move >> 6) & 63
    y1 = source >> 3
    x1 = source & 7
    y2 = target >> 3
    x2 = target & 7
    if side == 1:
        return ((y1 == 1 and y2 == 3 and x1 == x2 and x1 in (3,4)) or
                (y1 == 0 and x1 == 1 and y2 == 2 and x2 == 2) or
                (y1 == 0 and x1 == 6 and y2 == 2 and x2 == 5))
    return ((y1 == 6 and y2 == 4 and x1 == x2 and x1 in (3,4)) or
            (y1 == 7 and x1 == 1 and y2 == 5 and x2 == 2) or
            (y1 == 7 and x1 == 6 and y2 == 5 and x2 == 5))


def choose_ranked_move(scored,maximizing):
    # AI_RANDOMNESS selects a top-N window. Exact ties at the window edge
    # remain eligible, so Hard can still vary between genuinely equal moves
    # without ever accepting a lower score.
    limit = AI_RANDOMNESS
    if limit > len(scored):
        limit = len(scored)

    cutoff = scored[limit-1][1]
    candidates = []

    for item in scored:
        if maximizing:
            if item[1] < cutoff:
                break
        else:
            if item[1] > cutoff:
                break

        candidates.append(item)

    return unpack_move(random.choice(candidates)[0])


def find_best_move(depth=AI_DEPTH,side=1):
    moves = get_legal_moves(side)
    if len(moves) == 0:
        return None
    order_moves(moves)
    opening = opening_development_active(side)
    scored = []
    if side == 1:
        best_score = -AI_INFINITY
        alpha = -AI_INFINITY
        beta = AI_INFINITY
        for move in moves:
            source = move & 63
            target = (move >> 6) & 63
            promotion_index = move >> 12
            promotion = PROMOTION_CHOICES[promotion_index-1] if promotion_index else None
            state = make_move(source>>3,source&7,target>>3,target&7,side,False,promotion,0)
            score = minimax(depth-1,alpha,beta,0,1)
            undo_move(state)
            scored.append((move,score))
            if score > best_score:
                best_score = score
            if score > alpha:
                alpha = score
        scored.sort(key=lambda item:item[1], reverse=True)
        if opening:
            # All normal opening moves that minimax considers safe are given
            # the same root rank. This removes the built-in +24 preference of
            # Nc6/Nf6 over d5/e5 without modifying the general evaluation.
            opening_scored = [
                (item[0],best_score)
                for item in scored
                if is_opening_development_move(side,item[0]) and
                   item[1] >= best_score-OPENING_SAFETY_MARGIN
            ]
            if opening_scored:
                return choose_ranked_move(opening_scored,True)
        return choose_ranked_move(scored,True)
    best_score = AI_INFINITY
    alpha = -AI_INFINITY
    beta = AI_INFINITY
    for move in moves:
        source = move & 63
        target = (move >> 6) & 63
        promotion_index = move >> 12
        promotion = PROMOTION_CHOICES[promotion_index-1] if promotion_index else None
        state = make_move(source>>3,source&7,target>>3,target&7,side,False,promotion,0)
        score = minimax(depth-1,alpha,beta,1,1)
        undo_move(state)
        scored.append((move,score))
        if score < best_score:
            best_score = score
        if score < beta:
            beta = score
    scored.sort(key=lambda item:item[1])
    if opening:
        opening_scored = [
            (item[0],best_score)
            for item in scored
            if is_opening_development_move(side,item[0]) and
               item[1] <= best_score+OPENING_SAFETY_MARGIN
        ]
        if opening_scored:
            return choose_ranked_move(opening_scored,False)
    return choose_ranked_move(scored,False)

def has_legal_move(side):
    # Used to determine both checkmate and stalemate.
    for y1 in range(8):
        for x1 in range(8):
            p = board[y1][x1]

            if side == 0:
                own_piece = is_white(p)
            else:
                own_piece = is_black(p)

            if own_piece:
                for y2 in range(8):
                    for x2 in range(8):
                        target = board[y2][x2]

                        if x1 == x2 and y1 == y2:
                            continue

                        if target != "." and same_color(p,target):
                            continue

                        if is_valid(
                            p,
                            y1,
                            x1,
                            y2,
                            x2,
                            target
                        ):
                            if not would_leave_king_in_check(
                                side,
                                y1,
                                x1,
                                y2,
                                x2
                            ):
                                return True

    return False

def redraw_check_change(old_check,new_check):
    # Only redraw kings whose CHECK appearance actually changed.
    # -1 = no king was in check.
    #
    # If a king leaves CHECK, redraw it in its normal color.
    if old_check != -1 and old_check != new_check:
        old_pos = find_king(old_check)

        if old_pos is not None:
            y = old_pos[0]
            x = old_pos[1]

            draw_square(
                x,
                y
            )

    # If a king enters CHECK, redraw it red.
    if new_check != -1 and new_check != old_check:
        new_pos = find_king(new_check)

        if new_pos is not None:
            y = new_pos[0]
            x = new_pos[1]

            draw_square(
                x,
                y
            )


draw_player_select_screen()

running = True

while running:
    # In one-player mode the AI owns its selected side. No key input is read
    # while minimax is running.
    if player_count == 1 and turn == ai_side and winner == "" and not stalemate and not promotion_pending and not quit_confirm:
        thinking = True
        draw_status()
        ai_move = find_best_move(AI_DEPTH,ai_side)
        thinking = False
        perform_ai_move(ai_move)
        continue

    key = wait_for_key()

    # -------------------------
    # COLOR MENU
    # -------------------------

    if color_menu:
        if key == KEY_UP or key == KEY_DOWN:
            old_select = color_select
            color_select = 1-color_select
            update_color_select(old_select,color_select)
        elif key == KEY_ENTER:
            human_side = color_select
            ai_side = 1-human_side
            color_menu = False
            difficulty_select = 1
            difficulty_menu = True
            draw_difficulty_screen()
        elif key == KEY_CLEAR:
            color_menu = False
            draw_player_select_screen()
        continue

    # -------------------------
    # DIFFICULTY MENU
    # -------------------------

    if difficulty_menu:
        if key == KEY_UP:
            old_select = difficulty_select
            difficulty_select = difficulty_select-1
            if difficulty_select < 1:
                difficulty_select = 3
            update_difficulty_select(old_select,difficulty_select)
        elif key == KEY_DOWN:
            old_select = difficulty_select
            difficulty_select = difficulty_select+1
            if difficulty_select > 3:
                difficulty_select = 1
            update_difficulty_select(old_select,difficulty_select)
        elif key == KEY_ENTER:
            apply_difficulty()
            difficulty_menu = False
            player_count = 1
            reset_game_state()
            draw_initial_screen()
        elif key == KEY_CLEAR:
            difficulty_menu = False
            color_menu = True
            draw_color_screen()
        continue

    # -------------------------
    # PLAYER COUNT MENU
    # -------------------------

    if player_count == 0:
        if key == KEY_UP or key == KEY_DOWN:
            old_select = player_select
            if player_select == 1:
                player_select = 2
            else:
                player_select = 1
            update_player_select(old_select,player_select)
        elif key == KEY_ENTER:
            if player_select == 1:
                color_select = 0
                color_menu = True
                draw_color_screen()
            else:
                player_count = 2
                reset_game_state()
                draw_initial_screen()
        elif key == KEY_CLEAR:
            running = False
        continue

    # -------------------------
    # QUIT CONFIRMATION
    # -------------------------

    if quit_confirm:
        if key == KEY_ENTER:
            selected_x = -1
            selected_y = -1
            quit_confirm = False
            promotion_pending = False
            player_count = 0
            color_menu = False
            difficulty_menu = False
            draw_player_select_screen()
        elif key == KEY_CLEAR:
            quit_confirm = False
            draw_status()

        # Ignore all other keys while confirmation is visible.
        continue

    # On the game-over popup CLEAR returns directly to the main menu.
    if key == KEY_CLEAR and (winner != "" or stalemate):
        reset_game_state()
        player_count = 0
        player_select = 1
        difficulty_select = 1
        difficulty_menu = False
        color_select = 0
        color_menu = False
        human_side = 0
        ai_side = 1
        draw_player_select_screen()
        continue

    # First CLEAR press only asks to return to the main menu.
    if key == KEY_CLEAR:
        quit_confirm = True
        draw_status()
        continue

    # -------------------------
    # PAWN PROMOTION
    # -------------------------

    if promotion_pending:
        if key == KEY_LEFT:
            promotion_index = promotion_index-1

            if promotion_index < 0:
                promotion_index = 3

            draw_status()

        elif key == KEY_RIGHT:
            promotion_index = promotion_index+1

            if promotion_index > 3:
                promotion_index = 0

            draw_status()

        elif key == KEY_ENTER:
            choice = PROMOTION_CHOICES[promotion_index]

            if promotion_side == 0:
                board[promotion_y][promotion_x] = choice
            else:
                board[promotion_y][promotion_x] = choice.upper()

            # Draw the selected promoted piece.
            draw_square(
                promotion_x,
                promotion_y
            )

            promotion_pending = False
            promotion_x = -1
            promotion_y = -1
            promotion_side = -1
            promotion_index = 0

            old_check_turn = check_turn

            # Promotion completes the current player's move.
            if turn == 0:
                turn = 1
            else:
                turn = 0

            if player_count == 2:
                switch_to_turn_cursor()

            if is_in_check(turn):
                check_turn = turn
            else:
                check_turn = -1

            redraw_check_change(
                old_check_turn,
                check_turn
            )

            # No legal moves means either checkmate or stalemate.
            if not has_legal_move(turn):
                if check_turn == turn:
                    if turn == 0:
                        winner = "BLACK"
                    else:
                        winner = "WHITE"
                else:
                    stalemate = True

            message = "SELECT PIECE"
            draw_status()

        # UP/DOWN and other keys do nothing while choosing promotion.
        continue

    # -------------------------
    # GAME OVER
    # -------------------------

    if winner != "" or stalemate:
        if key == KEY_ENTER:
            # Rematch with the same player count, color and difficulty.
            reset_game_state()
            draw_initial_screen()

        # Arrow keys and other buttons do nothing after game over.
        continue

    # -------------------------
    # CURSOR MOVEMENT
    # -------------------------

    if key == KEY_LEFT:
        if cursor_x > 0:
            old_x = cursor_x
            old_y = cursor_y

            cursor_x = cursor_x-1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    elif key == KEY_RIGHT:
        if cursor_x < 7:
            old_x = cursor_x
            old_y = cursor_y

            cursor_x = cursor_x+1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    elif key == KEY_UP:
        if cursor_y > 0:
            old_x = cursor_x
            old_y = cursor_y

            cursor_y = cursor_y-1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    elif key == KEY_DOWN:
        if cursor_y < 7:
            old_x = cursor_x
            old_y = cursor_y

            cursor_y = cursor_y+1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    # -------------------------
    # QUIT
    # -------------------------

    # -------------------------
    # SELECT / MOVE
    # -------------------------

    elif key == KEY_ENTER:

        # No piece selected yet.
        if selected_x < 0:
            selected_piece = board[cursor_y][cursor_x]

            if selected_piece == ".":
                message = "NO PIECE"
                draw_status()

            elif turn == 0 and not is_white(selected_piece):
                message = "NOT YOURS"
                draw_status()

            elif turn == 1 and not is_black(selected_piece):
                message = "NOT YOURS"
                draw_status()

            else:
                selected_x = cursor_x
                selected_y = cursor_y
                message = "SELECT TARGET"

                draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
                draw_status()

        # Piece already selected.
        else:
            selected_piece = board[selected_y][selected_x]
            target = board[cursor_y][cursor_x]

            # ENTER on same square = cancel.
            if (cursor_x == selected_x and
                cursor_y == selected_y):

                selected_x = -1
                selected_y = -1
                message = "SELECT PIECE"

                draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
                draw_status()

            elif (target != "." and
                  same_color(selected_piece,target)):

                message = "OWN PIECE"
                draw_status()

            elif not is_valid(
                selected_piece,
                selected_y,
                selected_x,
                cursor_y,
                cursor_x,
                target
            ):
                message = "ILLEGAL MOVE"
                draw_status()

            elif would_leave_king_in_check(
                turn,
                selected_y,
                selected_x,
                cursor_y,
                cursor_x
            ):
                # You may not expose your own king or ignore CHECK.
                message = "ILLEGAL MOVE"
                draw_status()

            else:
                # Remember source before clearing selection.
                old_selected_x = selected_x
                old_selected_y = selected_y
                move_y = cursor_y
                move_x = cursor_x

                # The previous green move marker lasts until the next move.
                clear_ai_move_highlight()

                # In two-player mode every completed move is highlighted.
                if player_count == 2:
                    last_ai_from_x = old_selected_x
                    last_ai_from_y = old_selected_y
                    last_ai_to_x = move_x
                    last_ai_to_y = move_y

                # Apply the move through the central move engine.
                # The UI below only consumes the returned move details.
                move_state = make_move(
                    old_selected_y,
                    old_selected_x,
                    move_y,
                    move_x,
                    turn,
                    True
                )

                captured_piece = move_state[6]
                capture_y = move_state[7]
                capture_x = move_state[8]
                rook_from_x = move_state[9]
                rook_to_x = move_state[10]

                en_passant_move = (
                    captured_piece != "." and
                    (capture_y != move_y or capture_x != move_x)
                )

                castling_move = rook_from_x >= 0

                # Capturing a king ends the game.
                captured_king = False

                if captured_piece == "K":
                    winner = "WHITE"
                    captured_king = True
                elif captured_piece == "k":
                    winner = "BLACK"
                    captured_king = True

                selected_x = -1
                selected_y = -1
                save_active_cursor()

                # Redraw only the changed square interiors, then update their
                # highlight states independently.
                draw_square(
                    old_selected_x,
                    old_selected_y
                )
                draw_square(
                    move_x,
                    move_y
                )
                refresh_tile_highlight(old_selected_x,old_selected_y)
                refresh_tile_highlight(move_x,move_y)

                # Redraw the removed en-passant pawn.
                if en_passant_move:
                    draw_square(
                        capture_x,
                        capture_y
                    )

                # Redraw rook source/destination after castling.
                if castling_move:
                    draw_square(
                        rook_from_x,
                        move_y
                    )
                    draw_square(
                        rook_to_x,
                        move_y
                    )

                if captured_piece != ".":
                    draw_captures()
                    draw_score()

                if captured_king:
                    check_turn = -1
                    draw_status()

                elif (selected_piece == "p" and move_y == 0) or \
                     (selected_piece == "P" and move_y == 7):
                    # Pawn reached the last rank.
                    # The move is not complete until the player chooses
                    # Q, R, B or N.
                    promotion_pending = True
                    promotion_x = move_x
                    promotion_y = move_y
                    promotion_side = turn
                    promotion_index = 0

                    draw_status()

                else:
                    # Remember the previous visual CHECK state.
                    old_check_turn = check_turn

                    # Give the turn to the other player.
                    if turn == 0:
                        turn = 1
                    else:
                        turn = 0

                    if player_count == 2:
                        switch_to_turn_cursor()

                    # Is the new player in check?
                    if is_in_check(turn):
                        check_turn = turn
                    else:
                        check_turn = -1

                    # Only redraw a king if its CHECK appearance changed.
                    redraw_check_change(
                        old_check_turn,
                        check_turn
                    )

                    # No legal moves means either checkmate or stalemate.
                    if not has_legal_move(turn):
                        if check_turn == turn:
                            if turn == 0:
                                winner = "BLACK"
                            else:
                                winner = "WHITE"
                        else:
                            stalemate = True

                    message = "SELECT PIECE"
                    draw_status()

ti_draw.clear()
