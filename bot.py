import os
import asyncio
from aiohttp import web

import yt_dlp

from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls, idle
from pytgcalls import filters as call_filters
from pytgcalls.types import MediaStream


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]

PORT = int(os.environ.get("PORT", "10000"))


# ============================================================
# TELEGRAM BOT
# ============================================================

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ============================================================
# TELEGRAM USER ACCOUNT
# This account joins the Telegram voice chat.
# ============================================================

assistant = Client(
    "music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# ============================================================
# PYTGCALLS
# ============================================================

voice = PyTgCalls(assistant)


# ============================================================
# MUSIC DATA
# ============================================================

queues = {}
current_song = {}
paused_chats = set()


# ============================================================
# YOUTUBE SEARCH
# ============================================================

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


# ============================================================
# PLAY NEXT SONG
# ============================================================

async def play_next(chat_id):

    queue = queues.get(chat_id, [])

    if not queue:

        current_song.pop(
            chat_id,
            None
        )

        paused_chats.discard(chat_id)

        try:
            await voice.leave_call(chat_id)
        except Exception:
            pass

        return

    song = queue.pop(0)

    current_song[chat_id] = song
    paused_chats.discard(chat_id)

    try:

        await voice.play(
            chat_id,
            MediaStream(
                song["url"],
                video_flags=MediaStream.Flags.IGNORE
            )
        )

        await bot.send_message(
            chat_id,
            "🎵 **Now Playing**\n\n"
            f"🎶 {song['title']}"
        )

    except Exception as error:

        current_song.pop(
            chat_id,
            None
        )

        await bot.send_message(
            chat_id,
            "❌ **Playback error**\n\n"
            f"`{error}`"
        )

        await play_next(chat_id)


# ============================================================
# SONG FINISHED
# ============================================================

@voice.on_update(
    call_filters.stream_end()
)
async def song_finished(_, update):

    chat_id = update.chat_id

    if chat_id not in current_song:
        return

    current_song.pop(
        chat_id,
        None
    )

    await asyncio.sleep(1)

    await play_next(chat_id)


# ============================================================
# /START
# ============================================================

@bot.on_message(filters.command("start"))
async def start_command(_, message: Message):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "I can play music in your group's voice chat.\n\n"
        "▶️ `/play <song>`\n"
        "⏸ `/pause`\n"
        "▶️ `/resume`\n"
        "⏭ `/skip`\n"
        "⏹ `/stop`\n"
        "📜 `/queue`\n"
        "❓ `/help`"
    )


# ============================================================
# /HELP
# ============================================================

@bot.on_message(filters.command("help"))
async def help_command(_, message: Message):

    await message.reply_text(
        "🎵 **Music Bot Commands**\n\n"

        "▶️ `/play <song>`\n"
        "Play a song in VC.\n\n"

        "⏸ `/pause`\n"
        "Pause the current song.\n\n"

        "▶️ `/resume`\n"
        "Resume the current song.\n\n"

        "⏭ `/skip`\n"
        "Skip the current song.\n\n"

        "⏹ `/stop`\n"
        "Stop music and leave VC.\n\n"

        "📜 `/queue`\n"
        "Show the music queue."
    )


# ============================================================
# /PLAY
# ============================================================

@bot.on_message(filters.command("play"))
async def play_command(_, message: Message):

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
            query
        )

    except Exception as error:

        await status.edit_text(
            "❌ Search failed.\n\n"
            f"`{error}`"
        )

        return

    if chat_id not in queues:
        queues[chat_id] = []

    # Nothing currently playing
    if chat_id not in current_song:

        await status.edit_text(
            "🎵 **Starting:**\n"
            f"{song['title']}"
        )

        queues[chat_id].append(song)

        await play_next(chat_id)

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


# ============================================================
# /PAUSE
# ============================================================

@bot.on_message(filters.command("pause"))
async def pause_command(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current_song:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    if chat_id in paused_chats:

        await message.reply_text(
            "⏸ The music is already paused."
        )

        return

    try:

        await voice.pause(chat_id)

        paused_chats.add(chat_id)

        await message.reply_text(
            "⏸ **Music paused.**"
        )

    except Exception as error:

        await message.reply_text(
            "❌ Could not pause music.\n\n"
            f"`{error}`"
        )


# ============================================================
# /RESUME
# ============================================================

@bot.on_message(filters.command("resume"))
async def resume_command(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current_song:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    if chat_id not in paused_chats:

        await message.reply_text(
            "▶️ Music is not paused."
        )

        return

    try:

        await voice.resume(chat_id)

        paused_chats.discard(chat_id)

        await message.reply_text(
            "▶️ **Music resumed.**"
        )

    except Exception as error:

        await message.reply_text(
            "❌ Could not resume music.\n\n"
            f"`{error}`"
        )


# ============================================================
# /SKIP
# ============================================================

@bot.on_message(filters.command("skip"))
async def skip_command(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current_song:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    try:

        await voice.leave_call(chat_id)

    except Exception:
        pass

    current_song.pop(
        chat_id,
        None
    )

    paused_chats.discard(chat_id)

    await message.reply_text(
        "⏭ **Skipped.**"
    )

    await asyncio.sleep(1)

    await play_next(chat_id)


# ============================================================
# /STOP
# ============================================================

@bot.on_message(filters.command("stop"))
async def stop_command(_, message: Message):

    chat_id = message.chat.id

    queues.pop(
        chat_id,
        None
    )

    current_song.pop(
        chat_id,
        None
    )

    paused_chats.discard(chat_id)

    try:

        await voice.leave_call(chat_id)

    except Exception:
        pass

    await message.reply_text(
        "⏹ **Music stopped.**\n"
        "👋 Left the voice chat."
    )


# ============================================================
# /QUEUE
# ============================================================

@bot.on_message(filters.command("queue"))
async def queue_command(_, message: Message):

    chat_id = message.chat.id

    queue = queues.get(
        chat_id,
        []
    )

    text = "📜 **Music Queue**\n\n"

    if chat_id in current_song:

        text += (
            "🎵 **Playing:**\n"
            f"{current_song[chat_id]['title']}\n\n"
        )

    if not queue:

        text += "📭 Queue is empty."

        await message.reply_text(text)

        return

    text += "⏭ **Up Next:**\n"

    for number, song in enumerate(
        queue,
        start=1
    ):

        text += (
            f"{number}. "
            f"{song['title']}\n"
        )

    await message.reply_text(text)


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

async def health(request):

    return web.Response(
        text="🎵 Telegram Music Bot is running!"
    )


async def start_web_server():

    web_app = web.Application()

    web_app.router.add_get(
        "/",
        health
    )

    web_app.router.add_get(
        "/health",
        health
    )

    runner = web.AppRunner(
        web_app
    )

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


# ============================================================
# MAIN
# ============================================================

async def main():

    print("🚀 Starting Telegram Music Bot...")

    await bot.start()

    print("🤖 Bot account started.")

    await assistant.start()

    print("👤 Music assistant started.")

    await voice.start()

    print("🎧 Voice chat engine started.")

    await start_web_server()

    print(
        "===================================="
    )

    print(
        "🎵 TELEGRAM MUSIC BOT IS READY"
    )

    print(
        "===================================="
    )

    await idle()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print("🛑 Bot stopped.")
