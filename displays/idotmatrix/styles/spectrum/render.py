"""Four centered spectrum rings; all readings stay visible."""
from styles.common import four

def render(snapshot, page=0, amount=None, motion='hold', tick=0):
    return four(snapshot, 'ring')
