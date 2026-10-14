#!/usr/bin/env python3
"""Usage Battery for an iDotMatrix 32x32 LED panel (Bluetooth).

Runs on the same computer as the hub. Every minute it reads /api/display, draws Claude's
batteries as a 32x32 picture (with the time the numbers are from and when each limit
resets), and sends it to the panel when anything changed, plus a refresh every 10 minutes
in case the panel was switched to another mode. With --all, it sends a looping animation
of every service instead, so the panel cycles them by itself.

  python bridge.py                 # find the panel (name starts with IDM-) and run
  python bridge.py --once          # send one update and exit
  python bridge.py --all           # cycle Claude, Codex, ... instead of Claude only
  python bridge.py --address <id>  # use a specific panel
"""
import argparse, asyncio, hashlib, io, json, os, sys, time, urllib.request
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import render  # noqa: E402

CONFIG = os.path.expanduser("~/.usage-battery/idotmatrix.json")
CHECK_SECONDS = 60
RESEND_SECONDS = 600


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load_config():
    try:
        return json.load(open(CONFIG))
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f)


async def find_panel():
    from bleak import BleakScanner
    log("looking for an iDotMatrix panel (name starts with IDM-)...")
    for device in await BleakScanner.discover(timeout=10.0):
        if (device.name or "").startswith("IDM-"):
            log(f"found {device.name}")
            return device.address
    return None


class Hub:
    """Reads /api/display and remembers the last good answer."""

    def __init__(self, url, key, only=None):
        self.url, self.key, self.only = url.rstrip("/") + "/api/display", key, only
        self.data, self.ok = None, False
        self.as_of = {}  # service name -> time.time() its numbers are from

    def fetch(self):
        req = urllib.request.Request(self.url, headers={"X-Battery-Key": self.key} if self.key else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.data, self.ok = json.load(resp), True
        except Exception as e:
            if self.ok:
                log(f"hub not answering ({e.__class__.__name__}); showing last numbers")
            self.ok = False

    def frames(self):
        services = [s for s in (self.data or {}).get("services") or [] if not self.only or s["name"] == self.only]
        out = []
        for svc in services:
            if self.ok and svc.get("age_seconds") is not None:
                self.as_of[svc["name"]] = time.time() - svc["age_seconds"]
            as_of = self.as_of.get(svc["name"])
            freshness = "offline" if not self.ok else "stale" if as_of and time.time() - as_of > 180 else "fresh"
            updated = time.strftime("%-I:%M", time.localtime(as_of)) if as_of else ""
            out.append(render(svc, freshness, updated))
        return out


def encode(frames, seconds):
    """One frame -> PNG for image mode; several -> a looping GIF."""
    buf = io.BytesIO()
    if len(frames) == 1:
        frames[0].save(buf, format="PNG")
        return "png", buf.getvalue()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=int(seconds * 1000), loop=0, optimize=False, disposal=1)
    return "gif", buf.getvalue()


async def send(address, kind, data):
    from idotmatrix import ConnectionManager, Gif, Image as IdmImage
    path = os.path.join(os.path.dirname(CONFIG), f"idotmatrix-frame.{kind}")
    with open(path, "wb") as f:
        f.write(data)
    conn = ConnectionManager()
    await conn.connectByAddress(address)
    try:
        if kind == "png":
            ok = await IdmImage().setMode(1) is not False and await IdmImage().uploadUnprocessed(path) is not False
        else:
            ok = await Gif().uploadUnprocessed(path) is not False
        await asyncio.sleep(1)  # let the last packets go out
    finally:
        await conn.disconnect()
    return ok


async def run(args):
    cfg = load_config()
    address = args.address or cfg.get("address")
    if not address:
        address = await find_panel()
        if not address:
            sys.exit("No iDotMatrix panel found. Make sure it's on, nearby, and not connected to the phone app.")
        cfg["address"] = address
        save_config(cfg)

    hub = Hub(args.hub, args.key, None if args.all else "Claude")
    last_sig, last_sent, failures = None, 0.0, 0
    log(f"running: hub {args.hub}, panel {address}, " + (f"all services, {args.seconds:g}s each" if args.all else "Claude only"))
    while True:
        hub.fetch()
        frames = hub.frames()
        if frames:
            kind, data = encode(frames, args.seconds)
            sig = hashlib.sha1(data).hexdigest()
            if sig != last_sig or time.time() - last_sent > RESEND_SECONDS:
                try:
                    if await send(address, kind, data):
                        if sig != last_sig:
                            log(f"sent {len(frames)} screen(s)")
                        last_sig, last_sent, failures = sig, time.time(), 0
                    else:
                        raise RuntimeError("panel rejected the upload")
                except Exception as e:
                    failures += 1
                    if failures in (1, 5) or failures % 30 == 0:
                        log(f"couldn't reach the panel ({e}); will keep trying")
        if args.once:
            return
        await asyncio.sleep(CHECK_SECONDS)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hub", default=os.environ.get("BATTERY_HUB", "http://127.0.0.1:8765"))
    p.add_argument("--key", default=os.environ.get("BATTERY_KEY", ""), help="passcode, if the hub is on another computer")
    p.add_argument("--address", help="panel's Bluetooth id (found automatically the first time)")
    p.add_argument("--all", action="store_true", help="cycle every service instead of showing Claude only")
    p.add_argument("--seconds", type=float, default=10, help="with --all, seconds each service stays on screen")
    p.add_argument("--once", action="store_true", help="send one update and exit")
    args = p.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
