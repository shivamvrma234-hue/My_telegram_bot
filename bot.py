import os
import asyncio
from aiohttp import web
import yt_dlp

from pyrogram import Client, filters
from pyrogram.types import Message


# =========================================================
# CONFIG
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

PORT = int(os.environ.get("PORT", "10000"))


# =========================================================
# TELEGRAM BOT
# =========================================================

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# =========================================================
# MUSIC QUEUE
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
        info = ydl.extract_info(query, download=False)

        if "entries" in info:
            if not info["entries"]:
                raise Exception("Song not found.")

            info = info["entries"][0]

        return {
            "title": info.get("title", "Unknown"),
            "url": info.get("url"),
            "webpage_url": info.get("webpage_url"),
        }


# =========================================================
# /START
# =========================================================

@bot.on_message(filters.command("start"))
async def start_command(_, message: Message):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "The bot is online and working!\n\n"
        "🎧 Voice-chat playback is temporarily disabled "
        "while the voice engine is being fixed.\n\n"
        "Commands:\n"
        "▶️ `/play <song>` — Search a song\n"
        "📜 `/queue` — Show queue\n"
        "⏭ `/skip` — Skip queued song\n"
        "⏹ `/stop` — Clear queue\n"
        "❓ `/help` — Show help"
    )


# =========================================================
# /HELP
# =========================================================

@bot.on_message(filters.command("help"))
async def help_command(_, message: Message):

    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "▶️ `/play <song>` — Search a song\n"
        "📜 `/queue` — Show queue\n"
        "⏭ `/skip` — Remove current queue item\n"
        "⏹ `/stop` — Clear the queue\n"
        "❓ `/help` — Show this message\n\n"
        "⚠️ Voice-chat playback is currently disabled."
    )


# =========================================================
# /PLAY
# =========================================================

@bot.on_message(filters.command("play"))
async def play_command(_, message: Message):

    if len(message.command) < 2:
        await message.reply_text(
            "❌ Usage:\n\n"
            "`/play song name`"
        )
        return

    query = " ".join(message.command[1:])
    chat_id = message.chat.id

    status = await message.reply_text(
        "🔎 Searching for the song..."
    )

    try:
        song = await asyncio.to_thread(
            search_song,
            query
        )

    except Exception as error:

        await status.edit_text(
            f"❌ Search failed.\n\n`{error}`"
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
        "⚠️ Voice playback is temporarily disabled."
    )


# =========================================================
# /QUEUE
# =========================================================

@bot.on_message(filters.command("queue"))
async def queue_command(_, message: Message):

    chat_id = message.chat.id
    queue = queues.get(chat_id, [])

    if not queue:
        await message.reply_text(
            "📜 **Queue is empty.**"
        )
        return

    text = "📜 **Music Queue**\n\n"

    for number, song in enumerate(queue, 1):
        title = song.get("title", "Unknown")

        text += (
            f"`{number}.` {title}\n"
        )

    await message.reply_text(text)


# =========================================================
# /SKIP
# =========================================================

@bot.on_message(filters.command("skip"))
async def skip_command(_, message: Message):

    chat_id = message.chat.id
    queue = queues.get(chat_id, [])

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
async def stop_command(_, message: Message):

    chat_id = message.chat.id

    queues.pop(chat_id, None)
    now_playing.pop(chat_id, None)

    await message.reply_text(
        "⏹ **Music queue stopped.**\n"
        "🗑 Queue cleared."
    )


# =========================================================
# HEALTH SERVER FOR RENDER
# =========================================================

async def health(request):

    return web.Response(
        text="🎵 Telegram Music Bot is running!"
    )


async def start_health_server():

    app = web.Application()

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(
        f"🌐 Health server running on port {PORT}"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print("================================")
    print("🚀 Starting Telegram Music Bot")
    print("================================")

    await start_health_server()

    print("🌐 Health server started.")

    await bot.start()

    print("🤖 Telegram bot started.")
    print("================================")
    print("🎵 BOT IS READY")
    print("================================")

    await asyncio.Event().wait()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        print("🛑 Bot stopped.")
