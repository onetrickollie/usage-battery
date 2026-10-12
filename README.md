# Usage Battery

Shows your AI usage limits as batteries, read automatically from logins already on your Mac.

- **Claude**: 5-hour and weekly limits, using the login Claude Code saved (macOS Keychain or `~/.claude/.credentials.json`).
- **ChatGPT / Codex**: 5-hour and weekly limits from the notes Codex CLI saves in `~/.codex/sessions`.

## Run

```bash
python3 battery.py
```

Open http://127.0.0.1:8765. `python3 battery.py --demo` shows made-up numbers.

The first run may ask whether Python can read "Claude Code-credentials" from your Keychain; click Allow.
Your token stays in the local server and never reaches the page. Claude's usage endpoint is undocumented and may change.
