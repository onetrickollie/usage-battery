#!/usr/bin/env python3
"""AI usage battery meter.

Shows your remaining AI usage limits as batteries:
  - Claude: every minute, asks Claude Code for your usage (`claude -p /usage`), which reports
    account-wide numbers without sending a message to the model. Falls back to the snapshot
    statusline.py saves when Claude Code replies (~/.usage-battery/claude.json).
  - Codex / ChatGPT: rate-limit snapshots Codex CLI writes into ~/.codex/sessions

This script never reads your logins itself.

Run:  python3 battery.py          -> http://127.0.0.1:8765
      python3 battery.py --demo   -> fake data, for trying the UI
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
REFRESH_SECONDS = 60
DEMO = "--demo" in sys.argv
HOME = os.path.expanduser("~")

LABELS = {"five_hour": "5-hour session", "seven_day": "Weekly (all models)"}


CLAUDE_SNAPSHOT = os.path.join(HOME, ".usage-battery", "claude.json")


def claude_usage():
    """Prefer the live /usage reading; fall back to the status line snapshot."""
    live = LIVE.get("result")
    if live and time.time() - live["at"] < 3 * REFRESH_SECONDS:
        return {"name": "Claude", "meters": [recharged(dict(m)) for m in live["meters"]],
                "note": f"Live from Claude Code, checked {ago(live['at'])}"}
    snap = snapshot_usage()
    if LIVE.get("error") and (snap.get("error") or not snap.get("meters")):
        snap = {"name": "Claude", "error": LIVE["error"]}
    elif LIVE.get("error"):
        snap["note"] += f" (live check unavailable: {LIVE['error']})"
    return snap


def snapshot_usage():
    """Read the usage snapshot statusline.py saves each time Claude Code replies."""
    if not os.path.exists(CLAUDE_SNAPSHOT):
        return {"name": "Claude", "error": "No usage yet. Make sure Claude Code is installed and signed in."}
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


# --- Live refresh via `claude -p /usage` -------------------------------------------------

LIVE = {}
USAGE_LINE = re.compile(r"^Current (session|week \((?P<scope>[^)]+)\)): (?P<pct>[\d.]+)% used(?: · resets (?P<resets>.+))?$")


def find_claude():
    for path in (shutil.which("claude"), os.path.join(HOME, ".claude", "local", "claude"),
                 os.path.join(HOME, ".local", "bin", "claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if path and os.path.exists(path):
            return path
    return None


def parse_reset(text):
    """'Oct 12 at 8:30pm (America/Los_Angeles)' -> ISO timestamp, or None if the format changed."""
    m = re.match(r"(\w{3} \d{1,2}) at (\d{1,2}(?::\d{2})?[ap]m)(?: \(([^)]+)\))?", text.strip())
    if not m:
        return None
    day, clock, tz = m.groups()
    try:
        zone = ZoneInfo(tz) if tz else datetime.now().astimezone().tzinfo
        fmt = "%b %d %I:%M%p" if ":" in clock else "%b %d %I%p"
        now = datetime.now(zone)
        when = datetime.strptime(f"{day} {clock.upper()}", fmt).replace(year=now.year, tzinfo=zone)
        if (now - when).days > 180:  # e.g. a Jan 2 reset seen on Dec 30
            when = when.replace(year=now.year + 1)
        return when.isoformat()
    except (ValueError, KeyError):
        return None


def parse_usage(output):
    meters = []
    for line in output.splitlines():
        m = USAGE_LINE.match(line.strip())
        if not m:
            continue
        scope = m.group("scope")
        label = "5-hour session" if scope is None else f"Weekly ({scope})"
        meters.append({"label": label, "used": float(m.group("pct")),
                       "resets_at": parse_reset(m.group("resets")) if m.group("resets") else None})
    return meters


def refresh_live():
    claude = find_claude()
    if not claude:
        LIVE["error"] = "Claude Code not found"
        return
    try:
        out = subprocess.run([claude, "-p", "/usage"], capture_output=True, text=True,
                             timeout=60, cwd=tempfile.gettempdir()).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        LIVE["error"] = f"couldn't run Claude Code ({e.__class__.__name__})"
        return
    meters = parse_usage(out)
    if meters:
        LIVE.update(result={"meters": meters, "at": time.time()}, error=None)
    else:
        LIVE["error"] = "Claude Code's /usage output wasn't recognized (signed in with a Pro/Max plan?)"


def refresh_loop():
    while True:
        refresh_live()
        time.sleep(REFRESH_SECONDS)


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
    if not DEMO:
        threading.Thread(target=refresh_loop, daemon=True).start()
    print(f"Usage battery running at http://127.0.0.1:{PORT}{'  (demo data)' if DEMO else ''}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
