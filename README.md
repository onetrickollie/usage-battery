# Usage Battery

A battery meter for your AI usage limits. Instead of digging through settings pages, Usage Battery shows how much of your Claude and ChatGPT/Codex allowance is left as a set of batteries. It uses data your tools already hand over, so there are no API keys to paste, no logins to share, and no numbers to type in.

- **Claude**: your 5-hour session limit and weekly limit, with the time until each one recharges.
- **ChatGPT / Codex**: your 5-hour and weekly Codex limits.
- Batteries are green above 50% left, yellow down to 20%, and red below that. Each one also shows "% used", so it lines up with what Claude's own usage page says.
- It refreshes every minute on its own, and picks up usage from any device: Claude Code, the desktop app, claude.ai and your phone.

![How Usage Battery works: usage from your Claude account and Codex goes to battery.py on your computer, which refreshes every 60 seconds and feeds the browser page and, later, a desk display](docs/workflow.svg)

## Quick start

Requires Python 3 (no extra packages) and [Claude Code](https://claude.com/claude-code) signed in with a Claude Pro or Max plan.

**Start the battery page:**

```bash
cd ~/Projects/usage-battery
python3 battery.py
```

Then open http://127.0.0.1:8765 and leave the terminal window open while you use it. Press Ctrl+C to stop.

**Optional:** `statusline.py` also saves your numbers whenever Claude Code replies, and shows them at the bottom of Claude Code. It's a fallback for when the live check isn't available. To use it, add this to `~/.claude/settings.json`, changing the path to where you put this folder:

```json
"statusLine": {
  "type": "command",
  "command": "python3 ~/Projects/usage-battery/statusline.py"
}
```

To try the interface without real data, run `python3 battery.py --demo`.

## How it works

```
every 60s:  battery.py ──runs──► claude -p /usage ──► "Current session: 50% used · resets 8:30pm" ...
                │
                └──► browser page shows the batteries
```

- **Claude**: once a minute, `battery.py` runs Claude Code's built-in `/usage` command in non-interactive mode and reads the percentages it prints. This only checks usage; it doesn't send a message to the model, so it doesn't use up your limit (each check takes about a second). Because limits belong to your account, the numbers include usage from every device: Claude Code, the desktop app, claude.ai and your phone.
- **Fallback**: if the live check fails, the page uses the last numbers `statusline.py` saved when Claude Code replied, if you've set it up.
- **Codex**: each time you run the Codex CLI, it saves your rate limits in `~/.codex/sessions`. `battery.py` reads the newest snapshot.
- **Privacy**: `battery.py` never reads your logins. Claude Code handles its own sign-in, the same way as when you use it yourself. The page only accepts connections from your own machine.

## Limitations

- **Needs Claude Code installed and signed in with a Pro or Max plan**, on the computer running `battery.py`. You don't have to use Claude Code, just have it signed in. People who don't have Claude Code can't use this yet. Anthropic doesn't offer outside apps a supported way to read usage, and its terms don't allow third-party tools to use Claude plan logins.
- **Relies on the text `/usage` prints.** If a Claude Code update changes that wording, the live check stops recognizing it and the page falls back to the status line snapshot (or shows an error) until the parser is updated.
- **Whole-percent precision.** Claude Code reports whole percentages, so a single short message may not move the number.
- **Codex numbers are only as fresh as your last Codex run.** A window whose reset time has passed is shown as full.
- **No ChatGPT web or OpenAI API usage.** ChatGPT doesn't offer outside tools a way to read your remaining usage, and OpenAI's API usage reports need an organization admin key.
- **Prototype.** The page has to be started by hand and only runs while its terminal window is open.

## Roadmap

The on-screen prototype is done: it reads real usage data automatically and shows it clearly.

Next steps:

1. **A physical display.** Move the battery meter off the browser and onto a small dedicated screen, such as an e-ink panel on a desk, so you can see your remaining usage at a glance without opening anything. The display only ever receives percentages, never a login.
2. **Cross-platform support.** Make it work reliably on Windows and Linux as well as macOS, and run in the background so it doesn't need a terminal window.
3. **Support for more people.** Cover users who don't use Claude Code once Anthropic offers an official way to read usage. There's an open request: [anthropics/claude-code#13585](https://github.com/anthropics/claude-code/issues/13585).
