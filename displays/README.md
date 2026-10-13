# Displays

The hub (`hub/battery.py`) gathers your usage and serves it. A display only shows it. Displays never talk to Claude, Codex or your logins; they ask the hub for numbers and draw them however suits the device.

```
             ┌──────────── hub/battery.py ────────────┐
 Claude ───► │ checks usage every 60 s                │ ──► /api/display ──► any display
 Codex  ───► │ keeps the latest numbers, one format   │
             └────────────────────────────────────────┘
```

| Folder | Device | How it gets the data |
|---|---|---|
| (built into the hub) | Browser, at http://127.0.0.1:8765 | `/api/usage` from the same computer |
| [whisplay](whisplay/README.md) | Raspberry Pi + PiSugar Whisplay HAT | `/api/display` over Wi-Fi, every 60 s |

## Adding a display

Make a new folder here, like `displays/eink/`, with the device code, an installer if it needs one, and a README. Nothing in `hub/` has to change.

A display needs to do four things:

1. **Ask the hub** for `GET http://<computer>.local:8765/api/display` every minute or so.
2. **Send the passcode** in an `X-Battery-Key` header (or `?key=` in the URL). The hub prints it when started with `--lan`. Requests from the hub's own computer don't need it.
3. **Draw each service** in `services`, using whatever layout fits the screen. A service is only listed if it has numbers, so cycling through the list covers everything the user has set up.
4. **Handle no answer.** Keep the last numbers on screen and show how long ago they arrived, for example "OFFLINE 25M AGO" (a simple timer since the last good answer is enough, no clock needed). When a battery's `resets_in` runs out while offline, show it full. Show "wrong passcode" on a `401`.

## What `/api/display` returns

```json
{
  "updated": 1791931326.76,
  "updated_text": "3:42 PM",
  "services": [
    {
      "name": "Claude",
      "note": "Live from Claude Code, checked just now",
      "meters": [
        {"label": "5-hour session", "left": 34, "resets": "8:30 PM", "resets_in": 9120,
         "empty_in": 6000, "empty_text": "1h 40m", "level": "low"},
        {"label": "Weekly (all models)", "left": 81, "resets": "Sun 4:00 AM", "resets_in": 388212,
         "empty_in": null, "empty_text": "", "level": "ok"}
      ],
      "age_seconds": 12
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `updated`, `updated_text` | When the hub built this answer (Unix time, and ready-to-show local time) |
| `services[].name` | What to title the screen: "Claude", "ChatGPT / Codex", ... |
| `services[].note` | Where the numbers came from and how fresh they are (optional to show) |
| `services[].age_seconds` | How old this service's numbers are. Say so when it's more than a few minutes (e.g. Codex only updates when you run `codex`). |
| `meters[].label` | Which limit: "5-hour session", "Weekly (all models)", "Weekly (Opus)", ... |
| `meters[].left` | Whole percent left, 0 to 100. This is the battery level. |
| `meters[].resets` | When it refills, already formatted ("4:10 PM", "Sun 4:00 AM"), or empty |
| `meters[].resets_in` | Seconds until it refills, or `null` if unknown |
| `meters[].empty_in`, `empty_text` | At the recent pace, seconds (and "1h 40m") until it runs out. `null`/empty when it will last until it resets or there isn't enough history yet. |
| `meters[].level` | `ok` (above 50%), `low` (21–50%) or `critical` (20% or less), for coloring |

Times and levels are worked out by the hub, so small devices don't need a clock, time zones or thresholds.

## House style

The browser page and the Whisplay share a pixel-art look: a 5×7 pixel font in capitals, batteries made of 10 power blocks (one per 10% left), and green / yellow / red for `ok` / `low` / `critical`. The font's glyph table is in [whisplay/display.py](whisplay/display.py) and [hub/battery.html](../hub/battery.html); copy it to keep a new display consistent.
