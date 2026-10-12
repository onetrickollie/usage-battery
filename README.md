# Usage Battery

A battery meter for your AI usage limits. Instead of digging through settings pages, Usage Battery shows how much of your Claude and ChatGPT/Codex allowance is left as a set of batteries, read automatically from the logins already on your computer. There are no API keys to paste and no numbers to type in.

- **Claude**: your 5-hour session limit and weekly limit, with the time until each one recharges.
- **ChatGPT / Codex**: your 5-hour and weekly Codex limits.
- Batteries are green above 50% left, yellow down to 20%, and red below that. Each one also shows "% used", so it lines up with what Claude's own usage page says.
- The page refreshes every minute.

## Quick start

Requires macOS and Python 3, with no extra packages.

```bash
cd usage-battery
python3 battery.py
```

Then open http://127.0.0.1:8765 and leave the terminal window open while you use it. Press Ctrl+C to stop.

The first time it runs, macOS will ask whether Python can use "Claude Code-credentials" from your Keychain. Choose **Always Allow**.

To try the interface without real data:

```bash
python3 battery.py --demo
```

## How it works

```
Browser page  --every 60s-->  battery.py (local server)  --request-->  Anthropic usage server
(battery.html)                reads your saved login                   replies with your percentages
```

- **Claude**: when you sign in to [Claude Code](https://claude.com/claude-code), it saves a login token in your macOS Keychain. `battery.py` reads that token and asks Anthropic's usage server for your current percentages. This is a balance check, not a chat with the model, so it doesn't use up any of your limit. Usage limits belong to your account, so usage from claude.ai, the desktop and mobile apps, and Claude Code all shows up here.
- **Codex**: each time you run the Codex CLI, it saves your rate limits in `~/.codex/sessions`. `battery.py` reads the newest snapshot. Nothing is sent over the network for Codex.
- **Privacy**: the server only accepts connections from your own computer. Your token stays inside `battery.py` and never reaches the browser page. The only outside request is the one to Anthropic.

## Limitations

- **macOS only for now.** It reads Claude's login from the macOS Keychain. It falls back to `~/.claude/.credentials.json`, which Claude Code uses on some other systems, but that path hasn't been tested on Linux or Windows.
- **Needs Claude Code installed and signed in.** If that login expires because Claude Code hasn't been used in a while, run `claude` once to refresh it.
- **Relies on an undocumented server address.** Anthropic hasn't published `api.anthropic.com/api/oauth/usage` as an official API, so it could change or stop working without notice.
- **Codex numbers are only as fresh as your last Codex run.** If you don't use the Codex CLI, that section shows your last snapshot along with how old it is. A window whose reset time has passed is shown as full.
- **No ChatGPT web or OpenAI API usage.** ChatGPT doesn't let outside tools read your remaining usage, and OpenAI's API usage reports need an organization admin key, which goes against the "nothing to set up" goal.
- **Prototype.** It has to be started by hand and only runs while the terminal window is open.

## Roadmap

The on-screen prototype is done: it reads real usage data automatically and shows it clearly.

Next steps:

1. **A physical display.** Move the battery meter off the browser and onto a small dedicated screen, such as an e-ink panel or LED strip on a desk, so you can see your remaining usage at a glance without opening anything.
2. **Cross-platform support.** Make it work reliably on Windows and Linux as well as macOS, including reading saved logins on each system and running in the background so it doesn't need a terminal window.
3. **More services** where their usage data can be read safely and automatically.
