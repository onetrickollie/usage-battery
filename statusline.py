#!/usr/bin/env python3
"""Claude Code status line that also saves your usage limits for Usage Battery.

Claude Code runs this after each reply and passes session data as JSON on stdin,
including `rate_limits` (5-hour and weekly % used) for Pro/Max subscribers.
We save that snapshot to ~/.usage-battery/claude.json and print a short status line.

Install: add to ~/.claude/settings.json
  "statusLine": {"type": "command", "command": "python3 /path/to/usage-battery/statusline.py"}
"""
import json, os, sys, tempfile, time

SNAPSHOT = os.path.join(os.path.expanduser("~"), ".usage-battery", "claude.json")


def save(rate_limits):
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    # Write to a temp file and rename, so battery.py never reads a half-written file.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(SNAPSHOT), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump({"saved_at": time.time(), "rate_limits": rate_limits}, f)
    os.replace(tmp, SNAPSHOT)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    rl = data.get("rate_limits") or {}
    if rl:
        try:
            save(rl)
        except OSError:
            pass  # never break the status line over a failed save
    parts = []
    for key, name in (("five_hour", "5h"), ("seven_day", "week")):
        pct = (rl.get(key) or {}).get("used_percentage")
        if pct is not None:
            parts.append(f"{name} {100 - pct:.0f}% left")
    model = (data.get("model") or {}).get("display_name")
    print(" · ".join(filter(None, [model, *parts])) or "Usage Battery: waiting for first reply")


if __name__ == "__main__":
    main()
