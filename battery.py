#!/usr/bin/env python3
"""AI usage battery meter.

Shows your remaining AI usage limits as batteries, from data already saved on this computer:
  - Claude: the snapshot statusline.py saves each time Claude Code replies (~/.usage-battery/claude.json)
  - Codex / ChatGPT: rate-limit snapshots Codex CLI writes into ~/.codex/sessions

No logins are read and nothing is sent over the network.

Run:  python3 battery.py          -> http://127.0.0.1:8765
      python3 battery.py --demo   -> fake data, for trying the UI
"""
import glob, json, os, sys, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
DEMO = "--demo" in sys.argv
HOME = os.path.expanduser("~")

LABELS = {"five_hour": "5-hour session", "seven_day": "Weekly (all models)"}


CLAUDE_SNAPSHOT = os.path.join(HOME, ".usage-battery", "claude.json")


def claude_usage():
    """Read the usage snapshot statusline.py saves each time Claude Code replies."""
    if not os.path.exists(CLAUDE_SNAPSHOT):
        return {"name": "Claude", "error": "No usage saved yet. Set up statusline.py (see README), "
                                           "then send Claude Code one message."}
    try:
        snap = json.load(open(CLAUDE_SNAPSHOT))
    except (OSError, ValueError) as e:
        return {"name": "Claude", "error": f"Couldn't read {CLAUDE_SNAPSHOT}: {e}"}
    rl = snap.get("rate_limits") or {}
    meters = []
    for key, label in LABELS.items():
        v = rl.get(key)
        if isinstance(v, dict) and v.get("used_percentage") is not None:
            resets = v.get("resets_at")
            if isinstance(resets, (int, float)):
                resets = datetime.fromtimestamp(resets, timezone.utc).isoformat()
            meters.append(recharged({"label": label, "used": float(v["used_percentage"]), "resets_at": resets}))
    return {"name": "Claude", "meters": meters, "note": f"From your last Claude Code reply, {ago(snap.get('saved_at'))}"}


def ago(ts):
    if not ts:
        return "at an unknown time"
    mins = int((time.time() - ts) / 60)
    return ("just now" if mins < 1 else f"{mins} min ago" if mins < 60 else
            f"{mins // 60} h ago" if mins < 1440 else f"{mins // 1440} days ago")


def codex_usage():
    files = sorted(glob.glob(os.path.join(HOME, ".codex", "sessions", "**", "*.jsonl"), recursive=True),
                   key=os.path.getmtime, reverse=True)
    if not files:
        return {"name": "ChatGPT / Codex", "error": "No Codex sessions found. Use `codex` once while signed in with ChatGPT."}
    for path in files[:20]:
        snap = None
        for line in open(path, errors="ignore"):
            if '"rate_limits"' in line:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                rl = find_key(obj, "rate_limits")
                if rl:
                    snap = (rl, os.path.getmtime(path))
        if snap:
            rl, mtime = snap
            meters = []
            for slot in ("primary", "secondary"):
                w = rl.get(slot)
                if not w or w.get("used_percent") is None:
                    continue
                mins = w.get("window_minutes")
                label = (f"{mins // 60}-hour window" if mins and mins < 1440 else
                         "Weekly" if mins == 10080 else f"{slot} window")
                resets = w.get("resets_at")
                if isinstance(resets, (int, float)):
                    resets = datetime.fromtimestamp(resets, timezone.utc).isoformat()
                elif resets is None and w.get("resets_in_seconds") is not None:
                    resets = datetime.fromtimestamp(mtime + w["resets_in_seconds"], timezone.utc).isoformat()
                meters.append(recharged({"label": label, "used": float(w["used_percent"]), "resets_at": resets}))
            return {"name": "ChatGPT / Codex", "meters": meters,
                    "note": f"From your last Codex run, {ago(mtime)}"}
    return {"name": "ChatGPT / Codex", "error": "Codex sessions have no rate-limit data yet."}


def recharged(meter):
    """A window whose reset time has passed is full again, even if the snapshot is older."""
    try:
        if meter["resets_at"] and datetime.fromisoformat(meter["resets_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            meter.update(used=0.0, resets_at=None)
    except ValueError:
        pass
    return meter


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], dict):
            return obj[key]
        obj = obj.values()
    if isinstance(obj, (list, type({}.values()))):
        for v in obj:
            r = find_key(v, key)
            if r:
                return r
    return None


def demo():
    soon = lambda h: datetime.fromtimestamp(time.time() + h * 3600, timezone.utc).isoformat()
    return [{"name": "Claude", "meters": [
                {"label": "5-hour session", "used": 37, "resets_at": soon(2.3)},
                {"label": "Weekly (all models)", "used": 81, "resets_at": soon(70)},
                {"label": "Weekly (Opus)", "used": 94, "resets_at": soon(70)}]},
            {"name": "ChatGPT / Codex", "meters": [
                {"label": "5-hour window", "used": 12, "resets_at": soon(4)},
                {"label": "Weekly", "used": 55, "resets_at": soon(120)}]}]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/usage"):
            body = json.dumps({"demo": DEMO, "services": demo() if DEMO else [claude_usage(), codex_usage()]}).encode()
            ctype = "application/json"
        elif self.path in ("/", "/index.html"):
            body = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery.html"), "rb").read()
            ctype = "text/html; charset=utf-8"
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        if e.errno in (48, 98):  # address already in use (macOS, Linux)
            sys.exit(f"Port {PORT} is already in use - Usage Battery is probably already running.\n"
                     f"Open http://127.0.0.1:{PORT}, or stop the other copy (Ctrl+C in its window) and try again.")
        raise
    print(f"Usage battery running at http://127.0.0.1:{PORT}{'  (demo data)' if DEMO else ''}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
