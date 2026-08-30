import os
import asyncio
import threading
from aiohttp import web

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls
from pytgcalls import filters as call_filters
from pytgcalls.types import MediaStream, StreamEnded


# =========================================================
# CONFIG
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]

PORT = int(os.environ.get("PORT", "10000"))


# =========================================================
# TELEGRAM
# =========================================================

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# This is the Telegram USER account that joins the VC.
assistant = Client(
    "music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)

voice = PyTgCalls(assistant)


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
            "url": info["url"],
        }


# =========================================================
# PLAY NEXT
# =========================================================

async def play_next(chat_id):

    queue = queues.get(chat_id, [])

    if not queue:
        now_playing.pop(chat_id, None)

        try:
            await voice.leave_call(chat_id)
        except Exception:
            pass

        return

    song = queue.pop(0)
    now_playing[chat_id] = song

    try:

        await voice.play(
            chat_id,
            MediaStream(
                song["url"],
                video_flags=MediaStream.Flags.IGNORE,
            ),
        )

        await bot.send_message(
            chat_id,
            f"🎵 **Now Playing**\n\n"
            f"🎶 {song['title']}",
        )

    except Exception as error:

        now_playing.pop(chat_id, None)

        await bot.send_message(
            chat_id,
            f"❌ Could not play the song.\n\n"
            f"`{error}`",
        )

        await play_next(chat_id)


# =========================================================
# WHEN SONG FINISHES
# =========================================================

@voice.on_update(call_filters.stream_end())
async def stream_finished(_, update: StreamEnded):

    chat_id = update.chat_id

    now_playing.pop(chat_id, None)

    await asyncio.sleep(1)

    await play_next(chat_id)


# =========================================================
# /start
# =========================================================

@bot.on_message(filters.command("start"))
async def start_command(_, message: Message):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "Use `/play <song>` to play music in the group VC.\n\n"
        "Commands:\n"
        "▶️ `/play <song>`\n"
        "⏭ `/skip`\n"
        "⏹ `/stop`\n"
        "📜 `/queue`\n"
        "❓ `/help`"
    )


# =========================================================
# /help
# =========================================================

@bot.on_message(filters.command("help"))
async def help_command(_, message: Message):

    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "▶️ `/play <song>` — Play music\n"
        "⏭ `/skip` — Skip song\n"
        "⏹ `/stop` — Stop and leave VC\n"
        "📜 `/queue` — Show queue\n"
        "❓ `/help` — Show commands"
    )


# =========================================================
# /play
# =========================================================

@bot.on_message(filters.command("play"))
async def play_command(_, message: Message):

    if len(message.command) < 2:

        await message.reply_text(
            "❌ Usage:\n"
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
            query,
        )

    except Exception as error:

        await status.edit_text(
            f"❌ Search failed.\n\n`{error}`"
        )

        return

    if chat_id not in queues:
        queues[chat_id] = []

    # Nothing playing.
    if chat_id not in now_playing:

        queues[chat_id].append(song)

        await status.edit_text(
            f"🎵 **Starting:**\n"
            f"{song['title']}"
        )

        await play_next(chat_id)

    else:

        queues[chat_id].append(song)

        position = len(queues[chat_id])

        await status.edit_text(
            f"➕ **Added to queue**\n\n"
            f"🎶 {song['title']}\n"
            f"📌 Position: {position}"
        )


# =========================================================
# /skip
# =========================================================

@bot.on_message(filters.command("skip"))
async def skip_command(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in now_playing:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    try:
        await voice.leave_call(chat_id)
    except Exception:
        pass

    now_playing.pop(chat_id, None)

    await message.reply_text(
        "⏭ **Skipped!**"
    )

    await asyncio.sleep(1)

    await play_next(chat_id)


# =========================================================
# /stop
# =========================================================

@bot.on_message(filters.command("stop"))
async def stop_command(_, message: Message):

    chat_id = message.chat.id

    queues.pop(chat_id, None)
    now_playing.pop(chat_id, None)

    try:
        await voice.leave_call(chat_id)
    except Exception:
        pass

    await message.reply_text(
        "⏹ **Music stopped.**\n"
        "👋 Left the voice chat."
    )


# =========================================================
# /queue
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

        text += (
            f"{number}. "
            f"{song['title']}\n"
        )

    await message.reply_text(text)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

async def health(request):

    return web.Response(
        text="🎵 Music Bot is running!"
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
        PORT,
    )

    await site.start()

    print(
        f"🌐 Health server running on port {PORT}"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print("🚀 Starting Telegram bot...")

    await bot.start()

    print("🤖 Bot started.")

    await assistant.start()

    print("👤 Assistant account started.")

    voice.start()

    print("🎧 Voice engine started.")

    await start_health_server()

    print("==============================")
    print("🎵 MUSIC BOT IS READY")
    print("==============================")

    await asyncio.Event().wait()


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        print("Bot stopped.")
