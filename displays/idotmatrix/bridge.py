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
from render import render, render_both, needs_warning  # noqa: E402

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

    def __init__(self, url, key, mode="both"):
        self.url, self.key, self.mode = url.rstrip("/") + "/api/display", key, mode
        self.data, self.ok = None, False
        self.frame_seconds = None  # set when the picture should animate (warning blink)
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
        services = (self.data or {}).get("services") or []
        if self.mode == "claude":
            services = [s for s in services if s["name"] == "Claude"]
        if self.mode == "both":
            return self.both(services)
        out = []
        for svc in services:
            if self.ok and svc.get("age_seconds") is not None:
                self.as_of[svc["name"]] = time.time() - svc["age_seconds"]
            as_of = self.as_of.get(svc["name"])
            freshness = "offline" if not self.ok else "stale" if as_of and time.time() - as_of > 180 else "fresh"
            updated = time.strftime("%-I:%M", time.localtime(as_of)) if as_of else ""
            out.append(render(svc, freshness, updated))
        return out

    def both(self, services):
        """Claude and Codex together on one screen; old numbers drawn dimmer."""
        services = sorted(services, key=lambda s: s["name"] != "Claude")[:2]
        if not services:
            return []
        now = time.time()
        stale = []
        for svc in services:
            if self.ok and svc.get("age_seconds") is not None:
                self.as_of[svc["name"]] = now - svc["age_seconds"]
            as_of = self.as_of.get(svc["name"])
            if as_of and now - as_of > 180:
                stale.append(svc["name"])
        main = self.as_of.get(services[0]["name"])
        freshness = "offline" if not self.ok else "stale" if services[0]["name"] in stale else "fresh"
        updated = time.strftime("%-I:%M", time.localtime(main)) if main else ""
        codex = next((s for s in services if "Codex" in s["name"]), {})
        args = (services, stale, freshness, updated, codex.get("credits"))
        if needs_warning(services):
            self.frame_seconds = 0.5  # nearly empty: blink the battery (on, off, ...)
            return [render_both(*args), render_both(*args, blink_off=True)]
        self.frame_seconds = None
        return [render_both(*args)]


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
    """Send one picture over a connection kept open between updates.

    Every new Bluetooth connection makes the panel flash its own "connected" screen, so we
    connect once and reuse the link; only a dropped link (panel unplugged, out of range)
    causes a reconnect.
    """
    from idotmatrix import ConnectionManager, Gif, Image as IdmImage
    path = os.path.join(os.path.dirname(CONFIG), f"idotmatrix-frame.{kind}")
    with open(path, "wb") as f:
        f.write(data)
    conn = ConnectionManager()
    fresh = not (conn.client and conn.client.is_connected)
    if fresh:
        # The library keeps one client forever and it goes stale after a drop: start a new one.
        conn.client = None
        await asyncio.wait_for(conn.connectByAddress(address), timeout=20)
        log("connected to the panel")
        # A new connection makes the panel play its own "connected" screen; a picture sent
        # during it gets replaced by the panel's default screen. Let it finish first.
        await asyncio.sleep(4)
    try:
        if kind == "png":
            # Re-enter picture mode every time: the panel's mode button (or the phone app) can
            # switch it away, and a picture sent in another mode only flashes for a moment.
            await IdmImage().setMode(1)
            ok = await IdmImage().uploadUnprocessed(path) is not False
        else:
            ok = await Gif().uploadUnprocessed(path) is not False
    except Exception:
        await disconnect()
        raise
    if not ok:
        await disconnect()
    elif fresh and kind == "png":
        await asyncio.sleep(5)  # and once more, in case the panel was still settling
        await IdmImage().setMode(1)
        await IdmImage().uploadUnprocessed(path)
    return ok


async def disconnect():
    from idotmatrix import ConnectionManager
    conn = ConnectionManager()
    try:
        await conn.disconnect()
    except Exception:
        pass
    conn.client = None


async def run(args):
    cfg = load_config()
    address = args.address or cfg.get("address")
    if not address:
        address = await find_panel()
        if not address:
            sys.exit("No iDotMatrix panel found. Make sure it's on, nearby, and not connected to the phone app.")
        cfg["address"] = address
        save_config(cfg)

    hub = Hub(args.hub, args.key, "all" if args.all else "claude" if args.claude else "both")
    last_sig, last_sent, failures = None, 0.0, 0
    log(f"running: hub {args.hub}, panel {address}, " + (f"cycling services, {args.seconds:g}s each" if args.all else "Claude only" if args.claude else "Claude + Codex"))
    while True:
        hub.fetch()
        frames = hub.frames()
        if frames:
            kind, data = encode(frames, hub.frame_seconds or args.seconds)
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
                        log(f"couldn't reach the panel ({e.__class__.__name__}: {e}); will keep trying")
                    if failures == 1:
                        last_sig = None  # resend as soon as it's back, even if nothing changed
        if args.once:
            return
        await asyncio.sleep(CHECK_SECONDS)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hub", default=os.environ.get("BATTERY_HUB", "http://127.0.0.1:8765"))
    p.add_argument("--key", default=os.environ.get("BATTERY_KEY", ""), help="passcode, if the hub is on another computer")
    p.add_argument("--address", help="panel's Bluetooth id (found automatically the first time)")
    p.add_argument("--claude", action="store_true", help="show only Claude, with reset times")
    p.add_argument("--all", action="store_true", help="cycle every service full-screen instead of showing them together")
    p.add_argument("--seconds", type=float, default=10, help="with --all, seconds each service stays on screen")
    p.add_argument("--once", action="store_true", help="send one update and exit")
    args = p.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
