import os
import asyncio
import traceback

from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import yt_dlp


# =========================================================
# CONFIG
# =========================================================

try:
    API_ID = int(os.environ["API_ID"])
    API_HASH = os.environ["API_HASH"]
    BOT_TOKEN = os.environ["BOT_TOKEN"]
except KeyError as e:
    raise RuntimeError(
        f"Missing Render environment variable: {e.args[0]}"
    )

PORT = int(os.environ.get("PORT", "10000"))


# =========================================================
# TELEGRAM BOT
# =========================================================
#
# in_memory=True is important for Render.
# The bot does not depend on a local session file.
#

bot = Client(
    name="music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)


# =========================================================
# MUSIC DATA
# =========================================================

queues = {}
now_playing = {}


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def search_song(query):
    options = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "default_search": "ytsearch1",
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            query,
            download=False
        )

        if not info:
            raise Exception("No result found.")

        if "entries" in info:
            entries = info.get("entries") or []

            if not entries:
                raise Exception("Song not found.")

            info = entries[0]

        return {
            "title": info.get("title", "Unknown"),
            "url": info.get("url"),
            "webpage_url": info.get("webpage_url"),
        }


# =========================================================
# /START
# =========================================================

@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    print(
        f"📩 /start received from "
        f"{message.from_user.id if message.from_user else 'unknown'}",
        flush=True
    )

    await message.reply_text(
        "🎵 **Music Bot**\n\n"
        "✅ Bot is online!\n\n"
        "Commands:\n"
        "▶️ `/play <song>` - Search song\n"
        "📜 `/queue` - Show queue\n"
        "⏭ `/skip` - Skip song\n"
        "⏹ `/stop` - Clear queue\n"
        "❓ `/help` - Help\n\n"
        "⚠️ Voice playback is currently disabled."
    )


# =========================================================
# /HELP
# =========================================================

@bot.on_message(filters.command("help"))
async def help_command(client, message: Message):
    print(
        f"📩 /help received from "
        f"{message.from_user.id if message.from_user else 'unknown'}",
        flush=True
    )

    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "▶️ `/play <song>`\n"
        "Search for a song.\n\n"
        "📜 `/queue`\n"
        "Show the current queue.\n\n"
        "⏭ `/skip`\n"
        "Skip the first queued song.\n\n"
        "⏹ `/stop`\n"
        "Clear the queue.\n\n"
        "❓ `/help`\n"
        "Show this help message."
    )


# =========================================================
# /PLAY
# =========================================================

@bot.on_message(filters.command("play"))
async def play_command(client, message: Message):

    if len(message.command) < 2:
        await message.reply_text(
            "❌ Usage:\n"
            "`/play song name`"
        )
        return

    query = " ".join(message.command[1:])
    chat_id = message.chat.id

    status = await message.reply_text(
        "🔎 Searching..."
    )

    try:
        song = await asyncio.to_thread(
            search_song,
            query
        )

    except Exception as error:
        await status.edit_text(
            "❌ Search failed.\n\n"
            f"`{str(error)[:1000]}`"
        )
        return

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append(song)

    position = len(queues[chat_id])

    await status.edit_text(
        "🎵 **Song found!**\n\n"
        f"🎶 **{song['title']}**\n\n"
        f"📌 Queue position: `{position}`\n\n"
        "⚠️ Voice playback is currently disabled."
    )


# =========================================================
# /QUEUE
# =========================================================

@bot.on_message(filters.command("queue"))
async def queue_command(client, message: Message):

    chat_id = message.chat.id

    queue = queues.get(
        chat_id,
        []
    )

    if not queue:
        await message.reply_text(
            "📜 **Queue is empty.**"
        )
        return

    text = "📜 **Music Queue**\n\n"

    for number, song in enumerate(queue, 1):
        text += (
            f"`{number}.` "
            f"{song.get('title', 'Unknown')}\n"
        )

    await message.reply_text(text)


# =========================================================
# /SKIP
# =========================================================

@bot.on_message(filters.command("skip"))
async def skip_command(client, message: Message):

    chat_id = message.chat.id

    queue = queues.get(
        chat_id,
        []
    )

    if not queue:
        await message.reply_text(
            "❌ Nothing is in the queue."
        )
        return

    skipped = queue.pop(0)

    await message.reply_text(
        "⏭ **Skipped!**\n\n"
        f"🎶 {skipped.get('title', 'Unknown')}"
    )


# =========================================================
# /STOP
# =========================================================

@bot.on_message(filters.command("stop"))
async def stop_command(client, message: Message):

    chat_id = message.chat.id

    queues.pop(
        chat_id,
        None
    )

    now_playing.pop(
        chat_id,
        None
    )

    await message.reply_text(
        "⏹ **Music stopped.**\n\n"
        "🗑 Queue cleared."
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

async def health(request):
    return web.Response(
        text="🎵 Telegram Music Bot is running!"
    )


async def start_health_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/health",
        health
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(
        f"🌐 Health server running on port {PORT}",
        flush=True
    )

    return runner


# =========================================================
# TELEGRAM STARTUP
# =========================================================

async def start_telegram_bot():

    print(
        "🤖 Connecting to Telegram...",
        flush=True
    )

    try:

        await bot.start()

        print(
            "✅ Telegram connection successful!",
            flush=True
        )

        me = await bot.get_me()

        print(
            "========================================",
            flush=True
        )

        print(
            f"🤖 Bot: {me.first_name}",
            flush=True
        )

        print(
            f"👤 Username: @{me.username}",
            flush=True
        )

        print(
            f"🆔 ID: {me.id}",
            flush=True
        )

        print(
            "🎵 MUSIC BOT IS READY",
            flush=True
        )

        print(
            "========================================",
            flush=True
        )

        return True

    except FloodWait as error:

        print(
            "========================================",
            flush=True
        )

        print(
            "⏳ TELEGRAM FLOOD WAIT",
            flush=True
        )

        print(
            f"Telegram requires waiting "
            f"{error.value} seconds.",
            flush=True
        )

        print(
            "Do not repeatedly restart the bot.",
            flush=True
        )

        print(
            "========================================",
            flush=True
        )

        return False

    except Exception as error:

        print(
            "========================================",
            flush=True
        )

        print(
            "❌ TELEGRAM START ERROR",
            flush=True
        )

        print(
            f"Error type: {type(error).__name__}",
            flush=True
        )

        print(
            f"Error: {error}",
            flush=True
        )

        traceback.print_exc()

        print(
            "========================================",
            flush=True
        )

        return False


# =========================================================
# MAIN
# =========================================================

async def main():

    print(
        "========================================",
        flush=True
    )

    print(
        "🚀 STARTING TELEGRAM MUSIC BOT",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # Start Render web server first
    await start_health_server()

    print(
        "🌐 Render health server started.",
        flush=True
    )

    # Start Telegram
    connected = await start_telegram_bot()

    if not connected:

        print(
            "❌ Telegram bot could not start.",
            flush=True
        )

        print(
            "⚠️ Health server will remain online.",
            flush=True
        )

        # Keep Render service alive so the logs remain available.
        await asyncio.Event().wait()

        return

    # Keep everything alive
    print(
        "💚 Bot is running and waiting for Telegram messages...",
        flush=True
    )

    await asyncio.Event().wait()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped manually.",
            flush=True
        )

    except Exception as error:

        print(
            "========================================",
            flush=True
        )

        print(
            "❌ FATAL ERROR",
            flush=True
        )

        print(
            f"{type(error).__name__}: {error}",
            flush=True
        )

        traceback.print_exc()

        print(
            "========================================",
            flush=True
)
