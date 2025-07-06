# ckpool-informer

**ckpool‑informer** is a lightweight Telegram bot that notifies subscribers whenever the Bitcoin solo‑mining pool **ckpool (Solo CK)** finds a new block.  Every fetched block is cached locally so historical data is available offline through the `/block` command.

---

## Features

* **Real‑time alerts** — polls `mempool.space` and posts a message as soon as ckpool mines a block.
* **Local cache** — stores full block JSON in `blocks/` and keeps a height→hash index so previously seen blocks are never re‑announced.
* **Rich look‑ups** — `/block <height|hash>` returns detailed info from cache; with no argument it shows the latest cached block.
* **Stateless restarts** — because the cache lives on disk, you can stop the bot whenever you like and it will pick up right where it left off.
* **Donation‑ready** — love the project?  Consider a small tip to sustain development.

---

## Quick start

```bash
# 1. Clone & enter the project directory
 git clone https://github.com/erav3n/ckpool‑informer.git
 cd ckpool‑informer

# 2. Create & activate a virtual environment (Python ≥ 3.10)
 python -m venv .venv
 source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
 pip install --upgrade pip
 pip install "python-telegram-bot[asyncio]==21.*" aiohttp python-dotenv

# 4. Export required environment variables
 export BOT_TOKEN="123456:ABCDEF…"            # your Telegram bot API token
 # Optional overrides:
 # export MEMPOOL_API_BASE="https://mempool.space"
 # export CHECK_INTERVAL=60       # polling interval in seconds
 # export MAX_PARALLEL_FETCH=5    # concurrent API calls

# 5. Run the bot
 python ckpool_bot.py
```

The bot will create a `blocks/` folder for cached block files (`<hash>.json`) and an `index.json` with the height→hash map.

---

## Commands

| Command                   | Description                                   |
| ------------------------- | --------------------------------------------- |
| `/start`                  | Intro message with command list               |
| `/subscribe`              | Subscribe current chat to ckpool block alerts |
| `/unsubscribe`            | Stop receiving alerts                         |
| `/block <height \| hash>` | Show cached details for the given block       |
| `/block`                  | Show the last cached block                    |

---

## Donation

If this project saved you time or you simply like it, feel free to send a coffee in Bitcoin ☕️ ❤️

```
bc1qypqxj4adqxcw2w4kms63c8rvlnrxzwj3cuc4e4
```

Thank you!

---

## License

MIT — do whatever you want, but no warranty is provided. Pull requests are welcome!
