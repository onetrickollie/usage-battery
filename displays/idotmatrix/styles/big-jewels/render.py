"""Both services; page 0 = 5H, page 1 = WEEK. Rotation is opt-in."""
from styles.common import canvas, centered, gauge, word, color, finish

def render(snapshot, page=0, amount=None, motion='hold', tick=0):
    im = canvas()
    px = im.load()
    centered(px, 15, 0, ('5H', 'WEEK')[page], (158, 175, 199))
    for k, cx in enumerate((8, 24)):
        svc = snapshot.services[k]
        gauge(px, cx, 15, svc, page, k, 'diamond', 7)
        centered(px, cx, 26, word(svc, page), color(svc, page))
    return finish(im, snapshot)
