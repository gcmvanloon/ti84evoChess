# TI-84 EVO-T CHESS
#
# Configuration selects calculator features before the remaining source is
# optimized and minified.
#
# ARROWS = move cursor
# ENTER  = select / move
# DEL    = undo
# CLEAR  = back / menu
# TRACE  = toggle debug panel
#
# The entire board is drawn only once.
# Afterwards only changed squares are redrawn.
# The release style uses compact primitive renderers; debug can select glyphs.

import ti_draw
import ti_system
import random

def build_feature(name):
    # Readable-source defaults keep the complete debug panel available. The
    # desktop preprocessor removes this marker and every disabled branch.
    return True

def build_choice(option,value):
    # The readable source uses the existing graphical piece implementation.
    return option == "piece_style" and value == "graphical"

if build_feature("debug_panel.metrics.free_memory"):
    import gc

if build_feature("debug_panel.metrics.ai_time"):
    import time

def const(value):
    # The desktop build preprocessor removes this marker and inlines the value.
    # It remains an identity function so the readable source can run as-is.
    return value

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

WHITE = const("prnbqk")
BLACK = const("PRNBQK")

# Player 1 uses white, player 2 uses black, and a checked king uses red.
# Graphical pieces also reverse the player colors for their outlines.
WHITE_RGB = const((255,255,255))
BLACK_RGB = const((0,0,0))
CHECK_RGB = const((220,0,0))

KEY_LEFT  = const(24)
KEY_UP    = const(25)
KEY_RIGHT = const(26)
KEY_DOWN  = const(34)
KEY_CLEAR = const(45)
KEY_ENTER = const(105)
if build_feature("debug_panel"):
    KEY_TRACE = const(14)
KEY_DEL   = const(23)

BOARD_X = const(115)
BOARD_Y = const(26)
SQUARE = const(18)

# On the current TI-84 Evo ti_draw implementation,
# rectangle primitives appear one square (18 px) lower
# than draw_text. Apply one central correction so
# rectangles and text use the same logical coordinates.
SHAPE_Y_FIX = const(-18)

# ------------------------------------------------------------
# MATERIAL SCORE
# ------------------------------------------------------------
PIECE_VALUES = const({
    "p":1,
    "n":3,
    "b":3,
    "r":5,
    "q":9,
    "k":0
})

# ------------------------------------------------------------
# AI SETTINGS
# ------------------------------------------------------------
# Defaults. One-player difficulty selection overrides these values.
AI_DEPTH = 3
AI_RANDOMNESS = 1
AI_SCORE_MARGIN = 0
OPENING_SAFETY_MARGIN = const(30)

# Evaluation values use centipawn-like units. They are deliberately
# separate from the visible capture score above.
AI_PIECE_VALUES = const({
    "p":100,
    "n":320,
    "b":330,
    "r":500,
    "q":900,
    "k":20000
})

AI_MATE_SCORE = const(100000)
AI_INFINITY = const(1000000)

# Lightweight piece-square data. One shared 8x8 center table keeps
# memory use low; piece-specific multipliers turn it into positional
# values for knights, bishops, rooks and queens. Pawns and kings use
# a few direct positional rules below.
AI_CENTER_TABLE = const((
    0,0,0,0,0,0,0,0,
    0,1,1,1,1,1,1,0,
    0,1,2,2,2,2,1,0,
    0,1,2,4,4,2,1,0,
    0,1,2,4,4,2,1,0,
    0,1,2,2,2,2,1,0,
    0,1,1,1,1,1,1,0,
    0,0,0,0,0,0,0,0
))

AI_DEVELOPMENT_BONUS = const(12)
AI_CASTLED_BONUS = const(25)
AI_BISHOP_PAIR_BONUS = const(20)

if build_feature("show_captures"):
    # Right side of the 320-pixel drawing area.
    CAPTURE_X = const(260)
    CAPTURE_Y = const(26)
    CAPTURE_W = const(59)
    CAPTURE_ROW = const(18)

# Score and move count share the line below the board.
SCORE_Y = const(190)

# Light blue-gray for every non-board part of the game screen.
UI_BG = const((232,236,244))
LEFT_PANEL_W = const(100)

# ------------------------------------------------------------
# CHESS PIECE DRAWING
# ------------------------------------------------------------
# Exactly one build-time style remains in generated source. px,py is the
# top-left of the 16x16 colored tile interior. white_piece is True for player 1
# and False for player 2; the king also receives checked.

if build_choice("piece_style","graphical"):
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
        fill = WHITE_RGB if white_piece else BLACK_RGB
        outline = BLACK_RGB if white_piece else WHITE_RGB
        xs = (7,9,11,11,10,9,9,11,13,14,1,2,4,6,6,5,4,4,6,7)
        ys = (0,0,2,4,5,6,8,11,13,15,15,13,11,8,6,5,4,2,0,0)

        ti_draw.set_color(fill[0],fill[1],fill[2])
        draw_offset_fill_poly(px,py,xs,ys)
        ti_draw.set_color(outline[0],outline[1],outline[2])
        draw_offset_poly(px,py,xs,ys)


    def draw_rook(px,py,white_piece):
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
        # Compact body/cut and flat pedestal.
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
        # queen silhouette: crown, and king-style base.
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
        # king silhouette. CHECK changes only the fill color.
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
else:
    def draw_piece_shape(p,px,py,white_piece,checked=False):
        # One character from the board representation replaces every
        # graphical silhouette. Case continues to distinguish the sides.
        if checked:
            ti_draw.set_color(CHECK_RGB[0],CHECK_RGB[1],CHECK_RGB[2])
        elif white_piece:
            ti_draw.set_color(WHITE_RGB[0],WHITE_RGB[1],WHITE_RGB[2])
        else:
            ti_draw.set_color(BLACK_RGB[0],BLACK_RGB[1],BLACK_RGB[2])
        ti_draw.draw_text(px+4,py,p)

cursor_x = 4
cursor_y = 6

# Each human side remembers its own cursor position as (x,y).
white_cursor = (4,6)
black_cursor = (4,1)

# Last completed move, retained undo states, and selected square.
last_move = player_move_state = ai_move_state = selected = None

turn = player_count = 0
# 0 = white
# 1 = black

# Game mode. 0 means a setup menu is active.
# Setup page: 0 = player count, 1 = human color, 2 = difficulty.
menu_page = menu_select = human_side = 0
ai_side = 1
thinking = False
if build_feature("debug_panel"):
    debug_panel = False
if build_feature("debug_panel.metrics.ai_time"):
    # A negative time means no AI move has been measured in this game.
    ai_think_time = -1
if build_feature("debug_panel.metrics.ai_evaluated_moves"):
    ai_evaluated_moves = -1

message = "SELECT PIECE"
winner = ""
stalemate = quit_confirm = False
check_turn = -1
# -1 = no check, 0 = white in check, 1 = black in check

# Pawn promotion state.
promotion_pending = False
promotion_x = promotion_y = promotion_side = -1
promotion_index = 0
PROMOTION_CHOICES = const("qrbn")
YES_NO_CHOICES = const(("YES","NO"))

# Standard full moves completed; incremented after each black move.
white_score = black_score = move_count = 0

if build_feature("show_captures"):
    # Keys are lowercase piece types. Promoted pieces are recorded as pawns
    # when captured, without tracking the identity of individual pieces.
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
white_castle_k = white_castle_q = black_castle_k = black_castle_q = True

# En-passant target square.
# -1,-1 means there is currently no en-passant capture available.
en_passant_x = en_passant_y = -1

def is_white(p):
    return p in WHITE

def is_black(p):
    return p in BLACK

def same_color(a,b):
    return (is_white(a) and is_white(b)) or (is_black(a) and is_black(b))

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

def last_move_color(x,y):
    # Keep the move tint in the same light/dark family as the board.
    if (x+y)%2 == 0:
        return (170,200,135)
    return (80,115,60)

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
    # The ONLY drawing path for yellow, cyan board highlights.
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
    elif selected is not None and x == selected[0] and y == selected[1]:
        draw_tile_highlight(x,y,(0,200,255))
    elif last_move is not None and ((x == last_move[0] and y == last_move[1]) or \
         (x == last_move[2] and y == last_move[3])):
        draw_tile_highlight(x,y,last_move_color(x,y))


def draw_square(x,y,col):
    # Gameplay redraw: repaint only this tile's 16x16 interior and its piece.
    # The 1-pixel outer edge is owned by the independent highlight system.
    px = BOARD_X + x*SQUARE
    py = BOARD_Y + y*SQUARE

    ti_draw.set_color(col[0],col[1],col[2])
    fill_rect_at(px,py,SQUARE-1,SQUARE-1)
    draw_piece(x,y)

def redraw_square(x,y):
    # Repaint a changed interior, preserving a last-move tint when applicable.
    col = square_color(x,y)
    if last_move is not None and ((x == last_move[0] and y == last_move[1]) or \
       (x == last_move[2] and y == last_move[3])):
        col = last_move_color(x,y)
    draw_square(x,y,col)

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
            x += 2

def draw_starting_pieces():
    # draw_empty_board() creates a completely clean board first. Only after
    # that do we add the 32 pieces from the normal starting position.
    for y in (0,1,6,7):
        for x in range(8):
            draw_piece(x,y)

def draw_panel_separator():
    # Static game-screen chrome. Panel fills stop at x=99, so view changes do
    # not overwrite this divider at x=100.
    ti_draw.set_color(0,0,0)
    ti_draw.draw_line(LEFT_PANEL_W,0,LEFT_PANEL_W,209)


def draw_status_panel_frame():
    # The title and key hint belong to the status view, but are static while
    # that view remains active.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(0,18,LEFT_PANEL_W-1,209)
    draw_rect_at(0,18,LEFT_PANEL_W-1,209)
    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(5,26,"CHESS")
    ti_draw.draw_text(5,153,"CLEAR")
    ti_draw.draw_text(5,169,"MENU")


def clear_status_content():
    # Clear only the changing middle of the status view. Screen rows above 45
    # contain the title; rows from 153 down contain the static key hint.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(0,45,LEFT_PANEL_W,108)

def draw_status_panel():
    if build_feature("debug_panel"):
        global debug_panel
        # Routine status changes stay hidden while debugging. Only an
        # interactive prompt takes priority over the debug view.
        if debug_panel:
            if not (quit_confirm or winner or stalemate or promotion_pending):
                return
            debug_panel = False
            draw_status_panel_frame()
        else:
            clear_status_content()
    else:
        clear_status_content()

    if quit_confirm:
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,53,"RETURN?")
        ti_draw.draw_line(5,76+SHAPE_Y_FIX,95,76+SHAPE_Y_FIX)
        draw_panel_option(0,"YES",False,2)
        draw_panel_option(1,"NO",True,2)
        return

    if winner != "" or stalemate:
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,53,"GO AGAIN")
        ti_draw.draw_line(5,76+SHAPE_Y_FIX,95,76+SHAPE_Y_FIX)
        draw_panel_option(0,"YES",True,2)
        draw_panel_option(1,"NO",False,2)
        draw_game_over_popup()
        return

    if promotion_pending:
        ti_draw.set_color(0,0,0)
        ti_draw.draw_text(5,53,"PROMOTE")
        ti_draw.draw_line(5,76+SHAPE_Y_FIX,95,76+SHAPE_Y_FIX)

        i = 0

        while i < 4:
            draw_promotion_choice(i,PROMOTION_CHOICES[i],i == promotion_index,4)
            i += 1

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


if build_feature("debug_panel"):
    def draw_debug_panel_frame():
        # Enabled rows are packed from the top without per-combination panels.
        ti_draw.set_color(240,165,70)
        fill_rect_at(0,18,LEFT_PANEL_W-1,209)
        draw_rect_at(0,18,LEFT_PANEL_W-1,209)
        ti_draw.set_color(0,60,170)
        ti_draw.draw_text(5,26,"DEBUG")
        debug_row = 0
        if build_feature("debug_panel.metrics.last_key"):
            draw_debug_key("--")
            debug_row += 1
        if build_feature("debug_panel.metrics.free_memory"):
            draw_debug_metric(debug_row,"FM "+str(gc.mem_free()))
            debug_row += 1
        if player_count == 1:
            if build_feature("debug_panel.metrics.ai_time"):
                draw_ai_debug_metrics(debug_row)
            else:
                if build_feature("debug_panel.metrics.ai_evaluated_moves"):
                    draw_ai_debug_metrics(debug_row)


    def draw_debug_metric(index,text):
        y = 53+index*16
        ti_draw.set_color(240,165,70)
        fill_rect_at(4,y,91,16)
        ti_draw.set_color(0,60,170)
        ti_draw.draw_text(5,y,text)


    def draw_ai_debug_metrics(debug_row):
        if build_feature("debug_panel.metrics.ai_time"):
            if ai_think_time < 0:
                time_text = "AI --"
            else:
                tenths = int(ai_think_time*10)
                time_text = "AI "+str(tenths//10)+"."+str(tenths%10)+"S"
                if text_width(time_text) > LEFT_PANEL_W-10:
                    time_text = "AI "+str(int(ai_think_time))+"S"
            draw_debug_metric(debug_row,time_text)
            debug_row += 1
        if build_feature("debug_panel.metrics.ai_evaluated_moves"):
            move_text = "MV --" if ai_evaluated_moves < 0 else "MV "+str(ai_evaluated_moves)
            draw_debug_metric(debug_row,move_text)


    if build_feature("debug_panel.metrics.last_key"):
        def draw_debug_key(key):
            draw_debug_metric(0,"LK "+str(key))


def draw_game_over_popup():
    result = winner + " WON" if winner != "" else "NO ONE WON"

    box_w = text_width(result)+16
    box_h = 38
    box_x = BOARD_X + (SQUARE*8-box_w)//2
    box_y = BOARD_Y + (SQUARE*8-box_h)//2

    ti_draw.set_color(245,245,245)
    fill_rect_at(box_x,box_y,box_w,box_h)

    ti_draw.set_color(255,220,0)
    draw_rect_at(box_x,box_y,box_w-1,box_h-1)
    draw_rect_at(box_x+1,box_y+1,box_w-3,box_h-3)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(box_x+(box_w-text_width(result))//2,box_y+11,result)


def score_text():
    diff = white_score - black_score

    if diff > 0:
        return "W+" + str(diff)

    if diff < 0:
        return "B+" + str(-diff)

    return "+0"

def text_width(text):
    # Evo-T text glyphs are 8 pixels wide with 2 pixels between characters.
    return len(text)*10-2

def draw_score():
    # Promotions can make the material lead exceed the starting 39 points.
    # Clear room for five characters such as W+103. The extra pixel
    # compensates for fill_rect() excluding its far edge.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(
        BOARD_X,
        SCORE_Y-3,
        49,
        19
    )

    text = score_text()

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
        BOARD_X,
        SCORE_Y,
        text
    )

def draw_moves():
    text = "MOVES " + str(move_count)
    # Hardware testing places ti_draw text two pixels beyond its calculated
    # ink width, so inset the shared right edge by two pixels.
    right = BOARD_X + SQUARE*8-2
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(BOARD_X+50,SCORE_Y-3,SQUARE*8-49,19)
    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(right-text_width(text),SCORE_Y,text)

if build_feature("show_captures"):
    def draw_capture_column(x,captures,white_piece):
        # Highest-value captured pieces first.
        order = ["q","r","b","n","p"]
        row = 0

        for piece in order:
            count = captures[piece]

            if count > 0:
                py = CAPTURE_Y + 22 + row*CAPTURE_ROW

                # Show the opposing piece color captured by this player.
                draw_piece_shape(piece,x,py,white_piece)

                ti_draw.set_color(0,0,0)
                ti_draw.draw_text(
                    x+16,
                    py+1,
                    str(count)
                )

                row += 1

    def draw_captures(side=-1):
        # A move changes only the capturing player's column. side=-1 is the
        # full-panel draw used during setup/reset.
        ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])

        if side < 0:
            fill_rect_at(CAPTURE_X,CAPTURE_Y,CAPTURE_W,120)

            ti_draw.set_color(0,0,180)
            ti_draw.draw_text(CAPTURE_X+3,CAPTURE_Y,"W")
            ti_draw.set_color(180,0,0)
            ti_draw.draw_text(CAPTURE_X+34,CAPTURE_Y,"B")

            draw_capture_column(CAPTURE_X,white_captures,False)
            draw_capture_column(CAPTURE_X+30,black_captures,True)
        else:
            x = CAPTURE_X+side*30
            fill_rect_at(x,CAPTURE_Y+22,29,98)
            draw_capture_column(
                x,
                white_captures if side == 0 else black_captures,
                side == 1
            )

def update_material_state():
    # Rebuild the material score from the pieces currently on the board.
    global white_score, black_score

    white_score = black_score = 0

    for row in board:
        for piece in row:
            kind = piece.lower()

            if kind in PIECE_VALUES:
                value = PIECE_VALUES[kind]

                if is_white(piece):
                    white_score += value
                else:
                    black_score += value

if build_feature("show_captures"):
    def record_capture(captured_piece,side):
        # If remaining pieces plus earlier captures account for all original
        # pieces of this type, this capture must consume a promoted pawn.
        kind = captured_piece.lower()
        if kind == "k":
            return "."

        captures = white_captures if side == 0 else black_captures
        start_count = 1 if kind == "q" else 8 if kind == "p" else 2
        count = 0

        for row in board:
            for piece in row:
                if piece == captured_piece:
                    count += 1

        if count+captures[kind] >= start_count:
            kind = "p"

        captures[kind] += 1
        return kind

def save_active_cursor():
    global white_cursor, black_cursor

    if turn == 0:
        white_cursor = (cursor_x,cursor_y)
    else:
        black_cursor = (cursor_x,cursor_y)


def switch_to_turn_cursor():
    global cursor_x, cursor_y

    old_x = cursor_x
    old_y = cursor_y

    # Switch the logical cursor first. Border restoration then knows that the
    # old square must no longer receive the yellow cursor frame.
    cursor_x, cursor_y = white_cursor if turn == 0 else black_cursor

    refresh_tile_highlight(old_x,old_y)
    draw_tile_highlight(cursor_x,cursor_y,(255,220,0))


def clear_ai_move_highlight():
    global last_move

    old_move = last_move

    # Clear the state before repainting so both interiors return to their
    # normal board colors. Then restore any cursor/selection borders.
    last_move = None

    if old_move is not None:
        old_from_x, old_from_y, old_to_x, old_to_y = old_move
        redraw_square(old_from_x,old_from_y)
        refresh_tile_highlight(old_from_x,old_from_y)

        if old_to_x != old_from_x or old_to_y != old_from_y:
            redraw_square(old_to_x,old_to_y)
            refresh_tile_highlight(old_to_x,old_to_y)


def draw_choice_box(x,y,w,h,selected):
    # Selection geometry is independent of its text or piece content. The
    # extra fill pixel compensates for fill_rect() excluding its far edge.
    if selected:
        ti_draw.set_color(255,210,90)
    else:
        ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(x,y,w+1,h+1)


def draw_text_choice(x,y,w,text,selected):
    draw_choice_box(x,y,w,24,selected)
    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(x+(w-text_width(text))//2,y+4,text)


def draw_promotion_choice(index,piece,selected,count):
    # Promotion uses the same selected piece style as the board.
    x = 4 + index*22
    y = 82
    draw_choice_box(x,y,20,20,selected)
    if promotion_side == 1:
        piece = piece.upper()
    draw_piece_shape(piece,x+2,y+2,promotion_side == 0)


def draw_panel_option(index,text,selected,count):
    draw_text_choice(5,83+index*28,90,text,selected)


def draw_setup_option(index,text,selected,count):
    # Two- and three-row menus share one centered column. Three-row menus
    # start higher so their complete group remains vertically balanced.
    y = 96 if count == 2 else 82
    draw_text_choice(70,y+index*30,180,text,selected)


def draw_menu_screen(title,choices,selected,back_text):
    ti_draw.clear()
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(0,18,320,210)

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text((320-text_width("CHESS"))//2,28,"CHESS")
    ti_draw.draw_text((320-text_width(title))//2,52,title)
    ti_draw.draw_line(70,76+SHAPE_Y_FIX,250,76+SHAPE_Y_FIX)

    i = 0
    while i < len(choices):
        draw_setup_option(i,choices[i],i == selected,len(choices))
        i += 1

    ti_draw.set_color(0,0,0)
    ti_draw.draw_text(48,178,"ARROWS: MOVE")
    ti_draw.draw_text(48,196,"ENTER: OK")
    ti_draw.draw_text(202,196,"CLEAR: "+back_text)


def draw_current_menu():
    if menu_page == 0:
        draw_menu_screen("NUMBER OF PLAYERS",("1 PLAYER","2 PLAYERS"),menu_select,"QUIT")
    elif menu_page == 1:
        draw_menu_screen("PLAY AS",("WHITE","BLACK"),menu_select,"BACK")
    else:
        draw_menu_screen("DIFFICULTY",("EASY","MEDIUM","HARD"),menu_select,"BACK")


def choose_option(selected,choices,draw_option):
    count = len(choices)

    while True:
        key = wait_for_key()
        old = selected

        if key == KEY_UP or key == KEY_LEFT:
            selected -= 1
            if selected < 0:
                selected = count-1
        elif key == KEY_DOWN or key == KEY_RIGHT:
            selected += 1
            if selected == count:
                selected = 0
        elif key == KEY_ENTER:
            return selected
        elif key == KEY_CLEAR:
            return KEY_CLEAR

        if selected != old:
            draw_option(old,choices[old],False,count)
            draw_option(selected,choices[selected],True,count)


def apply_difficulty():
    global AI_DEPTH, AI_RANDOMNESS, AI_SCORE_MARGIN
    if menu_select == 0:
        AI_DEPTH = 1
        AI_RANDOMNESS = 6
        AI_SCORE_MARGIN = 150
    elif menu_select == 1:
        AI_DEPTH = 2
        AI_RANDOMNESS = 3
        AI_SCORE_MARGIN = 40
    else:
        AI_DEPTH = 3
        AI_RANDOMNESS = 1
        AI_SCORE_MARGIN = 0


def reset_game_state():
    global board, cursor_x, cursor_y
    global white_cursor, black_cursor, last_move
    global player_move_state, ai_move_state
    global selected, turn, message
    global winner, stalemate, quit_confirm, check_turn
    global promotion_pending, promotion_x, promotion_y
    global promotion_side, promotion_index
    global white_score, black_score, move_count
    global white_castle_k, white_castle_q
    global black_castle_k, black_castle_q
    global en_passant_x, en_passant_y
    if build_feature("show_captures"):
        global white_captures, black_captures
    global thinking
    if build_feature("debug_panel"):
        global debug_panel
    if build_feature("debug_panel.metrics.ai_time"):
        global ai_think_time
    if build_feature("debug_panel.metrics.ai_evaluated_moves"):
        global ai_evaluated_moves
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

    white_cursor = (4,6)
    black_cursor = (4,1)
    cursor_x, cursor_y = black_cursor if player_count == 1 and human_side == 1 else white_cursor
    last_move = player_move_state = ai_move_state = selected = None
    turn = 0
    message = "SELECT PIECE"
    winner = ""
    stalemate = quit_confirm = False
    check_turn = -1
    thinking = False
    if build_feature("debug_panel"):
        debug_panel = False
    if build_feature("debug_panel.metrics.ai_time"):
        ai_think_time = -1
    if build_feature("debug_panel.metrics.ai_evaluated_moves"):
        ai_evaluated_moves = -1

    promotion_pending = False
    promotion_x = promotion_y = promotion_side = -1
    promotion_index = move_count = 0

    white_castle_k = white_castle_q = black_castle_k = black_castle_q = True

    en_passant_x = en_passant_y = -1

    if build_feature("show_captures"):
        white_captures = {"p":0,"n":0,"b":0,"r":0,"q":0}
        black_captures = {"p":0,"n":0,"b":0,"r":0,"q":0}
    update_material_state()


def finish_human_turn(old_check_turn):
    global turn, check_turn, winner, stalemate, message

    turn = 1-turn
    if player_count == 2:
        switch_to_turn_cursor()

    check_turn = turn if is_in_check(turn) else -1
    redraw_check_change(old_check_turn,check_turn)

    if not has_legal_move(turn):
        if check_turn == turn:
            winner = "BLACK" if turn == 0 else "WHITE"
        else:
            stalemate = True

    message = "SELECT PIECE"
    draw_status_panel()


def perform_ai_move(move):
    global turn, check_turn, winner, stalemate
    global message
    global last_move, ai_move_state
    global move_count

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
    ai_move_state = state
    if ai_side == 1:
        move_count += 1

    captured_piece = state[6]
    capture_y = state[7]
    capture_x = state[8]
    rook_from_x = state[9]
    rook_to_x = state[10]

    # Store the new AI move, redraw only the changed interiors, then update
    # the two independent highlight frames explicitly.
    last_move = (x1,y1,x2,y2)

    redraw_square(x1,y1)
    redraw_square(x2,y2)
    refresh_tile_highlight(x1,y1)
    refresh_tile_highlight(x2,y2)

    if captured_piece != "." and (capture_y != y2 or capture_x != x2):
        redraw_square(
            capture_x,
            capture_y
        )

    if rook_from_x >= 0:
        redraw_square(
            rook_from_x,
            y2
        )
        redraw_square(
            rook_to_x,
            y2
        )

    if captured_piece != ".":
        if build_feature("show_captures"):
            draw_captures(ai_side)
    if captured_piece != "." or promotion is not None:
        draw_score()
    if ai_side == 1:
        draw_moves()

    if captured_piece == "K":
        winner = "WHITE"
        check_turn = -1
        draw_status_panel()
        return
    if captured_piece == "k":
        winner = "BLACK"
        check_turn = -1
        draw_status_panel()
        return

    turn = human_side

    check_turn = turn if is_in_check(turn) else -1

    redraw_check_change(old_check_turn,check_turn)

    if not has_legal_move(turn):
        if check_turn == turn:
            winner = "BLACK"
        else:
            stalemate = True

    message = "SELECT PIECE"
    draw_status_panel()


def draw_initial_screen():
    ti_draw.clear()

    # Establish one consistent background around the board.
    ti_draw.set_color(UI_BG[0],UI_BG[1],UI_BG[2])
    fill_rect_at(0,18,320,210)

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

    draw_status_panel_frame()
    draw_status_panel()
    draw_panel_separator()
    if build_feature("show_captures"):
        draw_captures()
    draw_score()
    draw_moves()

    # Draw initial cursor last, independently from square rendering.
    draw_tile_highlight(cursor_x,cursor_y,(255,220,0))

def path_clear(y1,x1,y2,x2):
    step_x = step_y = 0

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

        x += step_x
        y += step_y

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
    if p in "nN":
        return (dx == 1 and dy == 2) or (dx == 2 and dy == 1)

    # King
    if p in "kK":
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
    if p in "rR":
        return (x1 == x2 or y1 == y2) and path_clear(y1,x1,y2,x2)

    # Bishop
    if p in "bB":
        return dx == dy and path_clear(y1,x1,y2,x2)

    # Queen
    if p in "qQ":
        return (x1 == x2 or y1 == y2 or dx == dy) and path_clear(y1,x1,y2,x2)

    return False


def find_king(side):
    # White king = lowercase k
    # Black king = uppercase K
    king = "k" if side == 0 else "K"

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
    if p in "nN":
        return (dx == 1 and dy == 2) or (dx == 2 and dy == 1)

    # King
    if p in "kK":
        return dx <= 1 and dy <= 1

    # Rook
    if p in "rR":
        return (x1 == x2 or y1 == y2) and path_clear(y1,x1,y2,x2)

    # Bishop
    if p in "bB":
        return dx == dy and path_clear(y1,x1,y2,x2)

    # Queen
    if p in "qQ":
        return (x1 == x2 or y1 == y2 or dx == dy) and path_clear(y1,x1,y2,x2)

    return False

def is_square_attacked(y,x,by_side):
    for sy in range(8):
        for sx in range(8):
            p = board[sy][sx]

            own_piece = is_white(p) if by_side == 0 else is_black(p)

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

    enemy = 1-side

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
        p in "kK" and
        y1 == y2 and
        abs(x2-x1) == 2
    )

    is_en_passant = (
        p in "pP" and
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
    rook_from_x = rook_to_x = -1
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
# 12 packed old castling rights, 13 packed old en-passant target
# 14 capture-panel piece type when show_captures is enabled (gameplay only)

def make_move(y1,x1,y2,x2,side,update_material=True,promotion_piece=None,search_slot=0):
    global white_castle_k, white_castle_q
    global black_castle_k, black_castle_q
    global en_passant_x, en_passant_y

    p = board[y1][x1]
    target = board[y2][x2]

    old_castle_bits = (1 if white_castle_k else 0) | \
                      (2 if white_castle_q else 0) | \
                      (4 if black_castle_k else 0) | \
                      (8 if black_castle_q else 0)

    old_ep = -1 if en_passant_x < 0 else en_passant_x + en_passant_y*8

    castling_move = (p in "kK" and y1 == y2 and abs(x2-x1) == 2)
    en_passant_move = (p in "pP" and target == "." and
                       abs(x2-x1) == 1 and x2 == en_passant_x and y2 == en_passant_y)

    captured_piece = target
    capture_x = x2
    capture_y = y2

    if en_passant_move:
        capture_y = y1
        captured_piece = board[capture_y][x2]

    if p == "k":
        white_castle_k = white_castle_q = False
    elif p == "K":
        black_castle_k = black_castle_q = False
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

    rook_from_x = rook_to_x = -1
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
        board[y2][x2] = promotion_piece.lower() if side == 0 else promotion_piece.upper()

    en_passant_x = en_passant_y = -1
    if p in "pP" and abs(y2-y1) == 2:
        en_passant_x = x1
        en_passant_y = (y1+y2)//2

    if build_feature("show_captures"):
        capture_kind = "."
        if update_material and captured_piece != ".":
            capture_kind = record_capture(captured_piece,side)

    if update_material and (captured_piece != "." or promotion_piece is not None):
        update_material_state()

    # Search nodes reuse a fixed buffer instead of allocating a new list.
    if not update_material:
        state = SEARCH_STATES[search_slot]
        state[0]=p; state[1]=y1; state[2]=x1; state[3]=y2; state[4]=x2
        state[5]=target; state[6]=captured_piece; state[7]=capture_y; state[8]=capture_x
        state[9]=rook_from_x; state[10]=rook_to_x; state[11]=rook_piece
        state[12]=old_castle_bits; state[13]=old_ep
        return state

    if build_feature("show_captures"):
        return [p,y1,x1,y2,x2,target,captured_piece,capture_y,capture_x,
                rook_from_x,rook_to_x,rook_piece,old_castle_bits,old_ep,capture_kind]
    else:
        return [p,y1,x1,y2,x2,target,captured_piece,capture_y,capture_x,
                rook_from_x,rook_to_x,rook_piece,old_castle_bits,old_ep]


def undo_move(state,played=False):
    global white_castle_k, white_castle_q
    global black_castle_k, black_castle_q
    global en_passant_x, en_passant_y

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
        en_passant_x = en_passant_y = -1
    else:
        en_passant_x = old_ep % 8
        en_passant_y = old_ep // 8

    if played:
        if build_feature("show_captures"):
            capture_kind = state[14]
            if capture_kind != ".":
                captures = white_captures if is_white(p) else black_captures
                captures[capture_kind] -= 1

        for x,y in ((x1,y1),(x2,y2),(capture_x,capture_y),
                    (rook_from_x,y2),(rook_to_x,y2)):
            if x >= 0:
                redraw_square(x,y)
                refresh_tile_highlight(x,y)


def undo_played_moves():
    global turn, check_turn, message, selected, last_move, move_count
    global player_move_state, ai_move_state

    if player_move_state is None or (player_count == 1 and ai_move_state is None):
        message = "NO UNDO"
        draw_status_panel()
        return

    old_selected = selected
    old_check_turn = check_turn
    selected = last_move = None
    state = player_move_state
    if player_count == 1:
        undo_move(ai_move_state,True)
    undo_move(state,True)
    player_move_state = ai_move_state = None

    turn = human_side if player_count == 1 else is_black(state[0])
    move_count -= 1 if player_count == 1 else turn
    check_turn = turn if is_in_check(turn) else -1
    update_material_state()

    if old_selected is not None:
        refresh_tile_highlight(old_selected[0],old_selected[1])

    redraw_check_change(old_check_turn,check_turn)
    if player_count == 2:
        switch_to_turn_cursor()
    else:
        draw_tile_highlight(cursor_x,cursor_y,(255,220,0))

    if build_feature("show_captures"):
        draw_captures()
    draw_score()
    draw_moves()
    message = "SELECT PIECE"
    draw_status_panel()

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
    promo = PROMOTION_CHOICES[promotion-1] if promotion else "."
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
            y2 += dy
            x2 += dx


def get_legal_moves(side):
    moves = []
    for y1 in range(8):
        for x1 in range(8):
            p = board[y1][x1]
            own_piece = is_white(p) if side == 0 else is_black(p)
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
                        dx += 1
                    dy += 1
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
    if captured == "." and p in "pP" and x1 != x2:
        if x2 == en_passant_x and y2 == en_passant_y:
            captured = board[y1][x2]
    if captured != ".":
        score += AI_PIECE_VALUES[captured.lower()]*10
        score -= AI_PIECE_VALUES[p.lower()]
    if promotion:
        score += AI_PIECE_VALUES[PROMOTION_CHOICES[promotion-1]]*10
    if p.lower() == "k" and abs(x2-x1) == 2:
        score += 50
    return score


def order_moves(moves):
    i = 1
    while i < len(moves):
        move = moves[i]
        score = move_order_score(move)
        j = i-1
        while j >= 0 and move_order_score(moves[j]) < score:
            moves[j+1] = moves[j]
            j -= 1
        moves[j+1] = move
        i += 1

def evaluate_board():
    # Positive = good for black (the AI).
    # Negative = good for white.
    #
    # Keep this deliberately cheap: one board scan calculates material,
    # piece-square value and bishop counts. Development and king safety
    # are then determined with only a few fixed-square checks.
    score = 0
    white_king = black_king = False
    white_bishops = black_bishops = 0

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
                white_bishops += 1
            elif p == "B":
                black_bishops += 1

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
                    positional += 8
                elif x == 2 or x == 5:
                    positional += 3

                advancement = y-1 if is_black(p) else 6-y

                if advancement > 0:
                    positional += advancement*3

            elif lower == "k":
                # Mild preference against wandering into the centre.
                positional = -center*3

            if is_black(p):
                score += value + positional
            else:
                score -= value + positional

    # The current game also permits king capture, so handle that state
    # safely even though normal chess search should end at checkmate.
    if not white_king:
        return AI_MATE_SCORE

    if not black_king:
        return -AI_MATE_SCORE

    # Development: reward knights and bishops for leaving their original
    # squares. Fixed-square checks are much cheaper than generating moves.
    if board[7][1] != "n":
        score -= AI_DEVELOPMENT_BONUS
    if board[7][6] != "n":
        score -= AI_DEVELOPMENT_BONUS
    if board[7][2] != "b":
        score -= AI_DEVELOPMENT_BONUS
    if board[7][5] != "b":
        score -= AI_DEVELOPMENT_BONUS

    if board[0][1] != "N":
        score += AI_DEVELOPMENT_BONUS
    if board[0][6] != "N":
        score += AI_DEVELOPMENT_BONUS
    if board[0][2] != "B":
        score += AI_DEVELOPMENT_BONUS
    if board[0][5] != "B":
        score += AI_DEVELOPMENT_BONUS

    # King safety: a king on c/g after castling gets a small bonus.
    if board[7][2] == "k" or board[7][6] == "k":
        score -= AI_CASTLED_BONUS

    if board[0][2] == "K" or board[0][6] == "K":
        score += AI_CASTLED_BONUS

    # Bishop pair is a useful positional signal and nearly free because
    # bishop counts were gathered during the normal material scan.
    if white_bishops >= 2:
        score -= AI_BISHOP_PAIR_BONUS

    if black_bishops >= 2:
        score += AI_BISHOP_PAIR_BONUS

    return score


def minimax(depth,alpha,beta,side,ply=1):
    if build_feature("debug_panel.metrics.ai_evaluated_moves"):
        global ai_evaluated_moves
        # Every call evaluates the position reached by one simulated move.
        ai_evaluated_moves += 1
    white_king = find_king(0)
    black_king = find_king(1)
    if white_king is None:
        return AI_MATE_SCORE + depth
    if black_king is None:
        return -AI_MATE_SCORE - depth
    if depth <= 0:
        return evaluate_board()
    moves = get_legal_moves(side)
    if not moves:
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
    # Randomize within both the top-N window and the difficulty's score
    # margin. Exact ties at the window edge remain eligible.
    limit = AI_RANDOMNESS
    if limit > len(scored):
        limit = len(scored)

    cutoff = scored[limit-1][1]
    if maximizing:
        margin_cutoff = scored[0][1]-AI_SCORE_MARGIN
        if margin_cutoff > cutoff:
            cutoff = margin_cutoff
    else:
        margin_cutoff = scored[0][1]+AI_SCORE_MARGIN
        if margin_cutoff < cutoff:
            cutoff = margin_cutoff
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
    if not moves:
        return None
    order_moves(moves)
    opening = opening_development_active(side)
    scored = []
    if side == 1:
        best_score = alpha = -AI_INFINITY
        beta = AI_INFINITY
        for move in moves:
            source = move & 63
            target = (move >> 6) & 63
            promotion_index = move >> 12
            promotion = PROMOTION_CHOICES[promotion_index-1] if promotion_index else None
            state = make_move(source>>3,source&7,target>>3,target&7,side,False,promotion,0)
            score = minimax(depth-1,alpha,beta,0,1)
            # Easy does not search the reply, so cheaply penalize leaving the
            # moved piece where White can capture it on the next turn. Use
            # one third of its value so Easy accepts trades and modest risks.
            if depth == 1 and is_square_attacked(target>>3,target&7,0):
                score -= AI_PIECE_VALUES[board[target>>3][target&7].lower()]//3
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
        if depth == 1 and is_square_attacked(target>>3,target&7,1):
            score += AI_PIECE_VALUES[board[target>>3][target&7].lower()]//3
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

            own_piece = is_white(p) if side == 0 else is_black(p)

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

            redraw_square(
                x,
                y
            )

    # If a king enters CHECK, redraw it red.
    if new_check != -1 and new_check != old_check:
        new_pos = find_king(new_check)

        if new_pos is not None:
            y = new_pos[0]
            x = new_pos[1]

            redraw_square(
                x,
                y
            )


draw_current_menu()

running = True

while running:
    # -------------------------
    # SETUP MENUS
    # -------------------------
    if player_count == 0:
        if menu_page == 0:
            options = ("1 PLAYER","2 PLAYERS")
        elif menu_page == 1:
            options = ("WHITE","BLACK")
        else:
            options = ("EASY","MEDIUM","HARD")

        choice = choose_option(menu_select,options,draw_setup_option)

        if choice == KEY_CLEAR:
            if menu_page == 0:
                running = False
            elif menu_page == 1:
                menu_page = 0
                menu_select = 0
                draw_current_menu()
            else:
                menu_page = 1
                menu_select = human_side
                draw_current_menu()
        else:
            menu_select = choice
            if menu_page == 0 and menu_select == 1:
                player_count = 2
                reset_game_state()
                draw_initial_screen()
            elif menu_page == 0:
                menu_page = 1
                menu_select = human_side
                draw_current_menu()
            elif menu_page == 1:
                human_side = menu_select
                ai_side = 1-human_side
                menu_page = 2
                menu_select = 1
                draw_current_menu()
            else:
                apply_difficulty()
                player_count = 1
                reset_game_state()
                draw_initial_screen()
        continue

    # -------------------------
    # QUIT CONFIRMATION
    # -------------------------

    if quit_confirm:
        choice = choose_option(1,YES_NO_CHOICES,draw_panel_option)
        quit_confirm = False

        if choice == 0:
            selected = None
            promotion_pending = False
            player_count = menu_page = menu_select = 0
            draw_current_menu()
        else:
            draw_status_panel()
        continue

    # -------------------------
    # GAME OVER
    # -------------------------

    if winner != "" or stalemate:
        choice = choose_option(0,YES_NO_CHOICES,draw_panel_option)

        if choice == 0:
            # Rematch with the same player count, color and difficulty.
            reset_game_state()
            draw_initial_screen()
        else:
            reset_game_state()
            player_count = menu_page = menu_select = human_side = 0
            ai_side = 1
            draw_current_menu()
        continue

    # -------------------------
    # PAWN PROMOTION
    # -------------------------

    if promotion_pending:
        choice = choose_option(
            promotion_index,
            PROMOTION_CHOICES,
            draw_promotion_choice
        )

        if choice == KEY_CLEAR:
            quit_confirm = True
            draw_status_panel()
            continue

        promotion_index = choice
        choice = PROMOTION_CHOICES[promotion_index]

        board[promotion_y][promotion_x] = choice if promotion_side == 0 else choice.upper()

        update_material_state()
        draw_score()

        # Draw the selected promoted piece.
        redraw_square(
            promotion_x,
            promotion_y
        )

        promotion_pending = False
        promotion_x = promotion_y = promotion_side = -1
        promotion_index = 0

        old_check_turn = check_turn

        # Promotion completes the current player's move.
        if turn == 1:
            move_count += 1
            draw_moves()

        finish_human_turn(old_check_turn)
        continue

    # In one-player mode the AI owns its selected side. No key input is read
    # while minimax is running.
    if player_count == 1 and turn == ai_side:
        thinking = True
        draw_status_panel()
        if build_feature("debug_panel.metrics.ai_evaluated_moves"):
            ai_evaluated_moves = 0
        if build_feature("debug_panel.metrics.ai_time"):
            ai_think_time = time.monotonic()
        ai_move = find_best_move(AI_DEPTH,ai_side)
        if build_feature("debug_panel.metrics.ai_time"):
            ai_think_time = time.monotonic()-ai_think_time
        thinking = False
        if build_feature("debug_panel"):
            if debug_panel:
                debug_row = 0
                if build_feature("debug_panel.metrics.last_key"):
                    debug_row += 1
                if build_feature("debug_panel.metrics.free_memory"):
                    debug_row += 1
                if build_feature("debug_panel.metrics.ai_time"):
                    draw_ai_debug_metrics(debug_row)
                else:
                    if build_feature("debug_panel.metrics.ai_evaluated_moves"):
                        draw_ai_debug_metrics(debug_row)
        perform_ai_move(ai_move)
        continue

    key = wait_for_key()

    if build_feature("debug_panel.metrics.last_key"):
        if debug_panel and key != KEY_TRACE:
            draw_debug_key(key)

    # First CLEAR press only asks to return to the main menu.
    if key == KEY_CLEAR:
        quit_confirm = True
        draw_status_panel()
        continue

    if build_feature("debug_panel"):
        if key == KEY_TRACE:
            if debug_panel:
                debug_panel = False
                draw_status_panel_frame()
                draw_status_panel()
            else:
                debug_panel = True
                draw_debug_panel_frame()
            continue

    if key == KEY_DEL:
        undo_played_moves()
        continue

    # -------------------------
    # CURSOR MOVEMENT
    # -------------------------

    if key == KEY_LEFT:
        if cursor_x > 0:
            old_x = cursor_x
            old_y = cursor_y

            cursor_x -= 1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    elif key == KEY_RIGHT:
        if cursor_x < 7:
            old_x = cursor_x
            old_y = cursor_y

            cursor_x += 1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    elif key == KEY_UP:
        if cursor_y > 0:
            old_x = cursor_x
            old_y = cursor_y

            cursor_y -= 1

            refresh_tile_highlight(old_x,old_y)
            draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
            save_active_cursor()

    elif key == KEY_DOWN:
        if cursor_y < 7:
            old_x = cursor_x
            old_y = cursor_y

            cursor_y += 1

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
        if selected is None:
            selected_piece = board[cursor_y][cursor_x]

            if selected_piece == ".":
                message = "NO PIECE"
                draw_status_panel()

            elif turn == 0 and not is_white(selected_piece):
                message = "NOT YOURS"
                draw_status_panel()

            elif turn == 1 and not is_black(selected_piece):
                message = "NOT YOURS"
                draw_status_panel()

            else:
                selected = (cursor_x,cursor_y)
                message = "SELECT TARGET"

                draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
                draw_status_panel()

        # Piece already selected.
        else:
            selected_piece = board[selected[1]][selected[0]]
            target = board[cursor_y][cursor_x]

            # ENTER on same square = cancel.
            if (cursor_x == selected[0] and
                cursor_y == selected[1]):

                selected = None
                message = "SELECT PIECE"

                draw_tile_highlight(cursor_x,cursor_y,(255,220,0))
                draw_status_panel()

            elif (target != "." and
                  same_color(selected_piece,target)):

                message = "OWN PIECE"
                draw_status_panel()

            elif not is_valid(
                selected_piece,
                selected[1],
                selected[0],
                cursor_y,
                cursor_x,
                target
            ):
                message = "ILLEGAL MOVE"
                draw_status_panel()

            elif would_leave_king_in_check(
                turn,
                selected[1],
                selected[0],
                cursor_y,
                cursor_x
            ):
                # You may not expose your own king or ignore CHECK.
                message = "ILLEGAL MOVE"
                draw_status_panel()

            else:
                # Remember source before clearing selection.
                old_selected_x = selected[0]
                old_selected_y = selected[1]
                move_y = cursor_y
                move_x = cursor_x

                # The previous green move marker lasts until the next move.
                clear_ai_move_highlight()

                # In two-player mode every completed move is highlighted.
                if player_count == 2:
                    last_move = (old_selected_x,old_selected_y,move_x,move_y)

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
                player_move_state = move_state

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

                selected = None
                save_active_cursor()

                # Redraw only the changed square interiors, then update their
                # highlight states independently.
                redraw_square(
                    old_selected_x,
                    old_selected_y
                )
                redraw_square(
                    move_x,
                    move_y
                )
                refresh_tile_highlight(old_selected_x,old_selected_y)
                refresh_tile_highlight(move_x,move_y)

                # Redraw the removed en-passant pawn.
                if en_passant_move:
                    redraw_square(
                        capture_x,
                        capture_y
                    )

                # Redraw rook source/destination after castling.
                if castling_move:
                    redraw_square(
                        rook_from_x,
                        move_y
                    )
                    redraw_square(
                        rook_to_x,
                        move_y
                    )

                if captured_piece != ".":
                    if build_feature("show_captures"):
                        draw_captures(turn)
                    draw_score()

                if captured_king:
                    if turn == 1:
                        move_count += 1
                        draw_moves()
                    check_turn = -1
                    draw_status_panel()

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

                    draw_status_panel()

                else:
                    # Remember the previous visual CHECK state.
                    old_check_turn = check_turn

                    # Give the turn to the other player.
                    if turn == 1:
                        move_count += 1
                        draw_moves()

                    finish_human_turn(old_check_turn)

ti_draw.clear()
