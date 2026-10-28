"""Both limits for one service; page 0 = Claude, page 1 = Codex."""
from styles.common import canvas, centered, gauge, word, color, finish, LOGOS, LABEL, shade

def render(snapshot, page=0, amount=None, motion='hold', tick=0):
    im = canvas()
    px = im.load()
    svc = snapshot.services[page]
    centered(px, 15, 0, ('CLAUDE', 'CODEX')[page], shade(LOGOS[page][1], svc.dim))
    for row, cx in enumerate((8, 24)):
        gauge(px, cx, 13, svc, row, page, 'ring', 5.5)
        centered(px, cx, 21, word(svc, row), color(svc, row))
        centered(px, cx, 27, ('5H', 'WK')[row], LABEL)
    return finish(im, snapshot)
