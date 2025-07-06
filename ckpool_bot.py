# ckpool_bot.py – v7.0
"""
Telegram bot that alerts users about new Bitcoin blocks mined by **ckpool (Solo CK)** using the mempool.space REST API.
Each fetched block is cached to disk (`blocks/<hash>.json`) and indexed by height in `blocks/index.json`.

Commands
========
• **/subscribe**   – start receiving alerts about new ckpool blocks
• **/unsubscribe** – stop receiving alerts
• **/block <height|hash>** – show cached info about a given block
• **/block** (no args) – show info on the latest cached block
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Set

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Environment variable BOT_TOKEN is required")

MEMPOOL_API_BASE = os.getenv("MEMPOOL_API_BASE", "https://mempool.space").rstrip("/")
BLOCKS_ENDPOINT = f"{MEMPOOL_API_BASE}/api/blocks"          # ~10 latest blocks
BLOCK_DETAIL_TEMPLATE = f"{MEMPOOL_API_BASE}/api/v1/block/{{}}"  # block details

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))          # seconds
MAX_PARALLEL_FETCH = int(os.getenv("MAX_PARALLEL_FETCH", "5"))   # concurrency limit

DATA_PATH = Path(os.getenv("DATA_FILE", "ckpool_bot_state.json"))
BLOCKS_DIR = Path(os.getenv("BLOCKS_DIR", "blocks"))
BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
HEIGHT_INDEX_PATH = BLOCKS_DIR / "index.json"

CKPOOL_ID = 49  # ckpool (Solo CK) pool ID in mempool.space DB

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger("ckpool_bot")

# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_state() -> Dict[str, Any]:
    if DATA_PATH.exists():
        try:
            data = json.loads(DATA_PATH.read_text())
            if isinstance(data, dict) and "chats" in data:
                return {"chats": data["chats"]}
        except json.JSONDecodeError:
            logger.warning("State file corrupted; starting fresh…")
    return {"chats": []}


def save_state(chats: Set[int]) -> None:
    DATA_PATH.write_text(json.dumps({"chats": list(chats)}, indent=2))


def load_height_index() -> Dict[str, str]:
    if HEIGHT_INDEX_PATH.exists():
        try:
            return json.loads(HEIGHT_INDEX_PATH.read_text())
        except json.JSONDecodeError:
            logger.warning("Height index corrupted; recreating…")
    return {}


def save_height_index(index: Dict[str, str]) -> None:
    HEIGHT_INDEX_PATH.write_text(json.dumps(index, indent=2))

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
state = load_state()
chats: Set[int] = set(state["chats"])
height_index: Dict[str, str] = load_height_index()  # height(str) → hash

# ---------------------------------------------------------------------------
# Telegram command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "Hi! I track <b>ckpool (Solo CK) blocks</b> and will notify you whenever a new one is mined.\n"
        "Commands:\n"
        "• /subscribe – start receiving alerts\n"
        "• /unsubscribe – stop receiving alerts\n"
        "• /block &lt;height|hash&gt; – show cached info about a block\n"
        "• /block – show the last cached block info"
    )


async def subscribe(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id in chats:
        await update.message.reply_text("You are already subscribed 🚀")
    else:
        chats.add(chat_id)
        save_state(chats)
        await update.message.reply_text("✅ Subscription activated — you will receive notifications!")


async def unsubscribe(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in chats:
        await update.message.reply_text("You are not subscribed 🙃")
    else:
        chats.remove(chat_id)
        save_state(chats)
        await update.message.reply_text("❌ Subscription cancelled.")


async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show cached block info (/block [height|hash])."""
    # Determine block hash
    if context.args:
        query = context.args[0]
        if query.isdigit():
            block_id = height_index.get(query)
            if not block_id:
                await update.message.reply_text("No cached info about that block height, sorry…")
                return
        else:
            block_id = query.lower()
    else:
        if not height_index:
            await update.message.reply_text("No cached blocks yet, sorry…")
            return
        latest_height = max(height_index.keys(), key=int)
        block_id = height_index[latest_height]

    block_path = BLOCKS_DIR / f"{block_id}.json"
    if not block_path.exists():
        await update.message.reply_text("No cached info about that block, sorry…")
        return

    try:
        detail = json.loads(block_path.read_text())
    except Exception:
        await update.message.reply_text("Cached file is corrupted, sorry…")
        return

    height = detail["height"]
    timestamp = datetime.fromtimestamp(detail["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    txs = detail.get("tx_count") or "?"
    pool_info = detail.get("pool") or detail.get("extras", {}).get("pool") or {}
    pool_name = pool_info.get("name") or "Unknown"

    msg = (
        f"<b>Cached block info</b>\n"
        f"<b>Height:</b> {height}\n"
        f"<b>Hash:</b> <code>{block_id}</code>\n"
        f"<b>Time:</b> {timestamp}\n"
        f"<b>Pool:</b> {pool_name}\n"
        f"<b>Transactions:</b> {txs}\n"
        f"🔗 <a href=\"{MEMPOOL_API_BASE}/block/{block_id}\">View on mempool.space</a>"
    )
    await update.message.reply_html(msg, disable_web_page_preview=True)

# ---------------------------------------------------------------------------
# mempool.space helpers
# ---------------------------------------------------------------------------

async def fetch_latest_blocks(session: aiohttp.ClientSession):
    async with session.get(BLOCKS_ENDPOINT, timeout=15) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_block_detail(session: aiohttp.ClientSession, block_id: str):
    async with session.get(BLOCK_DETAIL_TEMPLATE.format(block_id), timeout=15) as resp:
        resp.raise_for_status()
        return await resp.json()

# ---------------------------------------------------------------------------
# Helper logic
# ---------------------------------------------------------------------------

def is_ckpool(detail: Dict[str, Any]) -> bool:
    pool = detail.get("pool") or detail.get("extras", {}).get("pool") or {}
    if not pool:
        return False
    if pool.get("id") == CKPOOL_ID:
        return True
    name = (pool.get("name") or "").lower()
    slug = (pool.get("slug") or "").lower()
    return any(sub in name for sub in ("ckpool", "solo ck", "solock")) or "solock" in slug


async def announce_block(app: Application, detail: Dict[str, Any]) -> None:
    block_hash = detail["id"]
    height = detail["height"]
    timestamp = datetime.fromtimestamp(detail["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    txs = detail.get("tx_count") or "?"
    pool_info = detail.get("pool") or detail.get("extras", {}).get("pool") or {}
    pool_name = pool_info.get("name") or "Unknown"

    msg = (
        f"🚀 <b>New {pool_name} block!</b>\n"
        f"<b>Height:</b> {height}\n"
        f"<b>Hash:</b> <code>{block_hash}</code>\n"
        f"<b>Time:</b> {timestamp}\n"
        f"<b>Transactions:</b> {txs}\n"
        f"🔗 <a href=\"{MEMPOOL_API_BASE}/block/{block_hash}\">View on mempool.space</a>"
    )

    for chat_id in list(chats):
        try:
            await app.bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception as exc:
            logger.warning("Failed to send message to chat %s: %s", chat_id, exc)

# ---------------------------------------------------------------------------
# Background watcher
# ---------------------------------------------------------------------------

async def ckpool_watcher(app: Application) -> None:
    global height_index  # noqa: PLW0603

    sem = asyncio.Semaphore(MAX_PARALLEL_FETCH)

    async def limited_detail(bid: str, sess: aiohttp.ClientSession):
        async with sem:
            return await fetch_block_detail(sess, bid)

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                latest = await fetch_latest_blocks(session)
                known_hashes = set(height_index.values())
                new_ids = [b["id"] for b in latest if b["id"] not in known_hashes]

                tasks = [asyncio.create_task(limited_detail(bid, session)) for bid in new_ids]
                for coro in asyncio.as_completed(tasks):
                    try:
                        detail = await coro
                    except Exception as exc:
                        logger.error("Failed to fetch block details: %s", exc)
                        continue

                    block_id = detail["id"]
                    height_str = str(detail["height"])

                    # Save JSON if not cached
                    block_file = BLOCKS_DIR / f"{block_id}.json"
                    if not block_file.exists():
                        block_file.write_text(json.dumps(detail, indent=2))

                    # Update index
                    height_index[height_str] = block_id
                    save_height_index(height_index)

                    # Announce if ckpool
                    if is_ckpool(detail):
                        await announce_block(app, detail)

            except Exception as exc:
                logger.error("Watcher loop error: %s", exc, exc_info=True)

            await asyncio.sleep(CHECK_INTERVAL)

# ---------------------------------------------------------------------------
# Post-init helper
# ---------------------------------------------------------------------------

async def _post_init(app: Application) -> None:
    """Launch the background watcher after the bot is initialized."""
    asyncio.create_task(ckpool_watcher(app))

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    # Register commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(["subscribe"], subscribe))
    application.add_handler(CommandHandler(["unsubscribe"], unsubscribe))
    application.add_handler(CommandHandler("block", cmd_block))

    logger.info("Starting bot…")
    application.run_polling(poll_interval=1)
