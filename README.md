# Usage Battery

A battery meter for your AI usage limits. Instead of digging through settings pages, Usage Battery shows how much of your Claude and ChatGPT/Codex allowance is left as a set of batteries. It uses data your tools already hand over, so there are no API keys to paste, no logins to share, and no numbers to type in.

- **Claude**: your 5-hour session limit and weekly limit, with the time until each one recharges.
- **ChatGPT / Codex**: your 5-hour and weekly Codex limits.
- Batteries are green above 50% left, yellow down to 20%, and red below that. Each one also shows "% used", so it lines up with what Claude's own usage page says.
- The page refreshes every minute.

## Quick start

Requires Python 3 (no extra packages) and [Claude Code](https://claude.com/claude-code) signed in with a Claude Pro or Max plan.

**1. Tell Claude Code to share your usage.** Add this to `~/.claude/settings.json`, changing the path to wherever you put this folder:

```json
"statusLine": {
  "type": "command",
  "command": "python3 ~/Projects/usage-battery/statusline.py"
}
```

Start a new Claude Code session and send it any message. The bottom of the screen should show something like `5h 65% left · week 94% left`.

**2. Start the battery page.**

```bash
cd ~/Projects/usage-battery
python3 battery.py
```

Then open http://127.0.0.1:8765 and leave the terminal window open while you use it. Press Ctrl+C to stop.

To try the interface without real data, run `python3 battery.py --demo`.

## How it works

```
Claude Code ──(after each reply)──► statusline.py ──saves──► ~/.usage-battery/claude.json
                                                                        │
                    browser page ◄──every 60s── battery.py ◄──reads─────┘
```

- **Claude**: Claude Code has an official [status line](https://code.claude.com/docs/en/statusline) feature. After each reply, it runs a script you choose and passes it session details, including your 5-hour and weekly usage percentages and reset times. `statusline.py` saves those numbers to a small file, and `battery.py` reads that file. Your Claude login is never read, and nothing is sent over the network.
- **Codex**: each time you run the Codex CLI, it saves your rate limits in `~/.codex/sessions`. `battery.py` reads the newest snapshot.
- **Privacy**: everything stays on your computer. The page only accepts connections from your own machine.

Usage limits belong to your Claude account, not to one app, so usage from claude.ai, the desktop and mobile apps, and Claude Code all counts. The battery shows the latest total each time Claude Code replies.

## Limitations

- **Updates when you use Claude Code.** The numbers refresh on each Claude Code reply. Usage elsewhere (claude.ai, the desktop chat app, your phone) still counts against your limits, but the battery won't show it until your next Claude Code reply. The page shows how old the numbers are.
- **Needs Claude Code on a Pro or Max plan.** Claude Code only shares usage limits for those plans. People who only use Claude in a browser, the desktop chat app or on their phone can't use this yet. Anthropic doesn't offer outside apps a supported way to read usage, and its terms don't allow third-party tools to use Claude plan logins.
- **Desktop app Code tab: not confirmed yet.** It's tested with Claude Code in Terminal. Whether the Claude desktop app's Code tab runs status line scripts hasn't been verified.
- **Codex numbers are only as fresh as your last Codex run.** A window whose reset time has passed is shown as full.
- **No ChatGPT web or OpenAI API usage.** ChatGPT doesn't offer outside tools a way to read your remaining usage, and OpenAI's API usage reports need an organization admin key.
- **Prototype.** The page has to be started by hand and only runs while its terminal window is open.

## Roadmap

The on-screen prototype is done: it reads real usage data automatically and shows it clearly.

Next steps:

1. **A physical display.** Move the battery meter off the browser and onto a small dedicated screen, such as an e-ink panel on a desk, so you can see your remaining usage at a glance without opening anything. The display only ever receives percentages, never a login.
2. **Cross-platform support.** Make it work reliably on Windows and Linux as well as macOS, and run in the background so it doesn't need a terminal window.
3. **Support for more people.** Cover users who don't use Claude Code once Anthropic offers an official way to read usage. There's an open request: [anthropics/claude-code#13585](https://github.com/anthropics/claude-code/issues/13585).
