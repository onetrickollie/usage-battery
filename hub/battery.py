#!/usr/bin/env python3
"""AI usage battery meter.

Shows your remaining AI usage limits as batteries:
  - Claude: every minute, asks Claude Code for your usage (`claude -p /usage`), which reports
    account-wide numbers without sending a message to the model. Falls back to the snapshot
    statusline.py saves when Claude Code replies (~/.usage-battery/claude.json).
  - Codex / ChatGPT: rate-limit snapshots Codex CLI writes into ~/.codex/sessions

This script never reads your logins itself.

Run:  python3 battery.py          -> http://127.0.0.1:8765 (this computer only)
      python3 battery.py --lan    -> also reachable from devices on your Wi-Fi, with a passcode
      python3 battery.py --demo   -> fake data, for trying the UI
"""
import glob, hmac, json, os, re, secrets, socket, shutil, subprocess, sys, tempfile, threading, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8765
REFRESH_SECONDS = 60
DEMO = "--demo" in sys.argv
LAN = "--lan" in sys.argv
HOME = os.path.expanduser("~")

LABELS = {"five_hour": "5-hour session", "seven_day": "Weekly (all models)"}


CLAUDE_SNAPSHOT = os.path.join(HOME, ".usage-battery", "claude.json")
STATE_FILE = os.path.join(HOME, ".usage-battery", "hub-state.json")  # last live reading + recent history


def claude_usage():
    """Newest of: the live /usage reading (kept across restarts) or the status line snapshot."""
    live = LIVE.get("result")
    snap = snapshot_usage()
    if live and live["at"] >= snap.get("as_of", 0):
        meters = []
        for m in live["meters"]:
            m = recharged(dict(m))
            m["empty_in_seconds"] = time_to_empty(m)
            meters.append(m)
        fresh = time.time() - live["at"] < 3 * REFRESH_SECONDS
        svc = {"name": "Claude", "meters": meters, "as_of": live["at"],
               "note": f"{'Live from' if fresh else 'Last reading from'} Claude Code, checked {ago(live['at'])}"}
    elif snap.get("meters"):
        svc = snap
    else:
        return {"name": "Claude", "error": LIVE.get("error") or snap.get("error")}
    if LIVE.get("error"):
        svc["note"] += f" (live check unavailable: {LIVE['error']})"
    return svc


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
    return {"name": "Claude", "meters": meters, "as_of": snap.get("saved_at") or 0,
            "note": f"From your last Claude Code reply, {ago(snap.get('saved_at'))}"}


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
        fmt = "%Y %b %d %I:%M%p" if ":" in clock else "%Y %b %d %I%p"
        now = datetime.now(zone)
        when = datetime.strptime(f"{now.year} {day} {clock.upper()}", fmt).replace(tzinfo=zone)
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
        now = time.time()
        LIVE.update(result={"meters": meters, "at": now}, error=None)
        record_history(meters, now)
        save_state()
    else:
        LIVE["error"] = "Claude Code's /usage output wasn't recognized (signed in with a Pro/Max plan?)"


# --- Remembering readings: survive restarts and estimate time left ----------------------

HISTORY = {}             # label -> [[time, used%], ...], oldest first
HISTORY_KEEP = 7 * 3600  # seconds of readings to keep


def record_history(meters, now):
    for m in meters:
        points = HISTORY.setdefault(m["label"], [])
        if points and m["used"] < points[-1][1] - 5:  # the window reset: start over
            points.clear()
        points.append([now, m["used"]])
        while points and now - points[0][0] > HISTORY_KEEP:
            points.pop(0)


def time_to_empty(meter):
    """Seconds until this limit runs out at the recent pace, or None if it will last until reset."""
    window = 3600 if meter["label"].startswith("5-hour") else 6 * 3600
    now = time.time()
    points = [p for p in HISTORY.get(meter["label"], []) if now - p[0] <= window]
    if len(points) < 2:
        return None
    (t0, u0), (t1, u1) = points[0], points[-1]
    if t1 - t0 < 600 or u1 - u0 < 2:  # need 10+ minutes and a real change before guessing
        return None
    seconds = (100 - u1) / ((u1 - u0) / (t1 - t0)) - (now - t1)
    resets = seconds_until(meter.get("resets_at"))
    if seconds <= 0 or (resets is not None and seconds >= resets):
        return None
    return int(seconds)


def seconds_until(iso):
    if not iso:
        return None
    try:
        return (datetime.fromisoformat(iso.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()
    except ValueError:
        return None


def save_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE_FILE), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump({"live": LIVE.get("result"), "history": HISTORY}, f)
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def load_state():
    try:
        state = json.load(open(STATE_FILE))
    except (OSError, ValueError):
        return
    if state.get("live"):
        LIVE["result"] = state["live"]
    HISTORY.update(state.get("history") or {})


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
            return {"name": "ChatGPT / Codex", "meters": meters, "as_of": mtime,
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


def all_services():
    return demo() if DEMO else [claude_usage(), codex_usage()]


def display_payload():
    """Compact data for small screens: only services that have numbers, times pre-formatted."""
    services = []
    for svc in all_services():
        meters = []
        for m in svc.get("meters") or []:
            left = round(max(0.0, min(100.0, 100 - m["used"])))
            resets_in = seconds_until(m.get("resets_at"))
            empty_in = m.get("empty_in_seconds")
            meters.append({"label": m["label"], "left": left, "resets": short_time(m.get("resets_at")),
                           "resets_in": None if resets_in is None else max(0, int(resets_in)),
                           "empty_in": empty_in, "empty_text": duration_text(empty_in) if empty_in else "",
                           "level": "ok" if left > 50 else "low" if left > 20 else "critical"})
        if meters:
            as_of = svc.get("as_of")
            services.append({"name": svc["name"], "meters": meters, "note": svc.get("note", ""),
                             "age_seconds": int(time.time() - as_of) if as_of else None})
    return {"updated": time.time(), "updated_text": datetime.now().strftime("%-I:%M %p"), "services": services}


def duration_text(seconds):
    """3720 -> '1h 2m', 200000 -> '2d 7h'."""
    mins = int(seconds // 60)
    if mins < 60:
        return f"{max(mins, 1)}m"
    if mins < 1440:
        return f"{mins // 60}h {mins % 60}m"
    return f"{mins // 1440}d {mins % 1440 // 60}h"


def short_time(iso):
    """'2026-10-12T20:30:00-07:00' -> '8:30 PM' today, 'Sun 4:00 AM' otherwise."""
    if not iso:
        return ""
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return ""
    clock = when.strftime("%-I:%M %p")
    return clock if when.date() == datetime.now().date() else f"{when.strftime('%a')} {clock}"


TOKEN_FILE = os.path.join(HOME, ".usage-battery", "lan_passcode")


def lan_passcode():
    """Load the passcode other devices must send, creating one on first use."""
    try:
        code = open(TOKEN_FILE).read().strip()
        if code:
            return code
    except OSError:
        pass
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    code = secrets.token_urlsafe(9)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(code)
    return code


def lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packets sent; just picks the Wi-Fi interface
            return s.getsockname()[0]
    except OSError:
        return None


PASSCODE = None


class Handler(BaseHTTPRequestHandler):
    def allowed(self, query):
        """This computer is always allowed; other devices need the passcode."""
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return True
        sent = self.headers.get("X-Battery-Key") or (query.get("key") or [""])[0]
        return bool(PASSCODE) and hmac.compare_digest(sent.encode(), PASSCODE.encode())

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path.startswith("/api/") and not self.allowed(query):
            self.send_error(401, "Passcode required"); return
        if url.path == "/api/usage":
            body = json.dumps({"demo": DEMO, "services": all_services()}).encode()
            ctype = "application/json"
        elif url.path == "/api/display":
            body = json.dumps(display_payload()).encode()
            ctype = "application/json"
        elif url.path in ("/", "/index.html"):
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
        server = ThreadingHTTPServer(("0.0.0.0" if LAN else "127.0.0.1", PORT), Handler)
    except OSError as e:
        if e.errno in (48, 98):  # address already in use (macOS, Linux)
            sys.exit(f"Port {PORT} is already in use - Usage Battery is probably already running.\n"
                     f"Open http://127.0.0.1:{PORT}, or stop the other copy (Ctrl+C in its window) and try again.")
        raise
    if not DEMO:
        load_state()
        threading.Thread(target=refresh_loop, daemon=True).start()
    print(f"Usage battery running at http://127.0.0.1:{PORT}{'  (demo data)' if DEMO else ''}  (Ctrl+C to stop)")
    if LAN:
        PASSCODE = lan_passcode()
        host = socket.gethostname()
        host = host if host.endswith(".local") else host + ".local"
        print(f"Other devices on your Wi-Fi: http://{host}:{PORT}/?key={PASSCODE}"
              + (f"  (or http://{lan_address()}:{PORT}/?key={PASSCODE})" if lan_address() else ""))
        print(f"Passcode: {PASSCODE}   (saved in {TOKEN_FILE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
