import os
import asyncio
from aiohttp import web

import yt_dlp

from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls
from pytgcalls import idle
from pytgcalls.types import MediaStream


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]

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
# TELEGRAM USER ACCOUNT
# This account joins the group voice chat.
# =========================================================

assistant = Client(
    "music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# =========================================================
# VOICE CHAT
# =========================================================

voice = PyTgCalls(assistant)


# =========================================================
# MUSIC QUEUES
# =========================================================

queues = {}
playing = {}


# =========================================================
# SEARCH YOUTUBE
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
            download=False,
        )

        if "entries" in info:

            if not info["entries"]:
                raise Exception("Song not found.")

            info = info["entries"][0]

        return {
            "title": info.get(
                "title",
                "Unknown"
            ),
            "url": info["url"],
        }


# =========================================================
# PLAY SONG
# =========================================================

async def play_song(chat_id, song):

    try:

        playing[chat_id] = song

        await voice.play(
            chat_id,
            MediaStream(
                song["url"],
                video_flags=MediaStream.Flags.IGNORE,
            ),
        )

        await bot.send_message(
            chat_id,
            "🎵 **Now Playing**\n\n"
            f"🎶 {song['title']}",
        )

    except Exception as error:

        playing.pop(chat_id, None)

        await bot.send_message(
            chat_id,
            "❌ **Playback failed**\n\n"
            f"`{error}`",
        )


# =========================================================
# /start
# =========================================================

@bot.on_message(filters.command("start"))
async def start_handler(_, message: Message):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "I can play music in your group's voice chat.\n\n"
        "Use:\n"
        "▶️ `/play song name`\n"
        "⏭ `/skip`\n"
        "⏹ `/stop`\n"
        "📜 `/queue`\n"
        "❓ `/help`"
    )


# =========================================================
# /help
# =========================================================

@bot.on_message(filters.command("help"))
async def help_handler(_, message: Message):

    await message.reply_text(
        "🎵 **Music Bot Commands**\n\n"
        "▶️ `/play <song>`\n"
        "Play a song.\n\n"
        "⏭ `/skip`\n"
        "Skip the current song.\n\n"
        "⏹ `/stop`\n"
        "Stop music and leave VC.\n\n"
        "📜 `/queue`\n"
        "Show the queue."
    )


# =========================================================
# /play
# =========================================================

@bot.on_message(filters.command("play"))
async def play_handler(_, message: Message):

    if len(message.command) < 2:

        await message.reply_text(
            "❌ **Usage:**\n"
            "`/play song name`"
        )

        return

    chat_id = message.chat.id

    query = " ".join(
        message.command[1:]
    )

    status = await message.reply_text(
        "🔎 Searching..."
    )

    try:

        song = await asyncio.to_thread(
            search_song,
            query,
        )

    except Exception as error:

        await status.edit_text(
            "❌ Search failed.\n\n"
            f"`{error}`"
        )

        return

    if chat_id not in queues:
        queues[chat_id] = []

    # Nothing currently playing.
    if chat_id not in playing:

        await status.edit_text(
            "🎵 Starting:\n"
            f"**{song['title']}**"
        )

        await play_song(
            chat_id,
            song,
        )

    else:

        queues[chat_id].append(song)

        position = len(
            queues[chat_id]
        )

        await status.edit_text(
            "➕ **Added to queue**\n\n"
            f"🎶 {song['title']}\n"
            f"📌 Position: {position}"
        )


# =========================================================
# /queue
# =========================================================

@bot.on_message(filters.command("queue"))
async def queue_handler(_, message: Message):

    chat_id = message.chat.id

    queue = queues.get(
        chat_id,
        [],
    )

    if not queue:

        await message.reply_text(
            "📜 **Queue is empty.**"
        )

        return

    text = "📜 **Music Queue**\n\n"

    for number, song in enumerate(
        queue,
        start=1,
    ):

        text += (
            f"{number}. "
            f"{song['title']}\n"
        )

    await message.reply_text(
        text
    )


# =========================================================
# /skip
# =========================================================

@bot.on_message(filters.command("skip"))
async def skip_handler(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in playing:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    try:

        await voice.leave_call(
            chat_id
        )

    except Exception:
        pass

    playing.pop(
        chat_id,
        None,
    )

    await message.reply_text(
        "⏭ **Skipped.**"
    )

    queue = queues.get(
        chat_id,
        [],
    )

    if queue:

        next_song = queue.pop(0)

        await asyncio.sleep(1)

        await play_song(
            chat_id,
            next_song,
        )


# =========================================================
# /stop
# =========================================================

@bot.on_message(filters.command("stop"))
async def stop_handler(_, message: Message):

    chat_id = message.chat.id

    queues.pop(
        chat_id,
        None,
    )

    playing.pop(
        chat_id,
        None,
    )

    try:

        await voice.leave_call(
            chat_id
        )

    except Exception:
        pass

    await message.reply_text(
        "⏹ **Music stopped.**\n"
        "👋 Left the voice chat."
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

async def health(request):

    return web.Response(
        text="Music Bot is running!"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health,
    )

    app.router.add_get(
        "/health",
        health,
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT,
    )

    await site.start()

    print(
        f"🌐 Web server started on port {PORT}"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print("🚀 Starting music bot...")

    await bot.start()

    print("🤖 Bot account started.")

    await assistant.start()

    print("👤 Assistant account started.")

    voice.start()

    print("🎧 Voice chat engine started.")

    await start_web_server()

    print(
        "================================"
    )

    print(
        "🎵 MUSIC BOT IS READY"
    )

    print(
        "================================"
    )

    await idle()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped."
                )
