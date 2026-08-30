import os
import asyncio
import traceback

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

def required_env(name):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing Render environment variable: {name}"
        )

    return value


try:
    API_ID = int(required_env("API_ID"))
except ValueError:
    raise RuntimeError("API_ID must be a number")

API_HASH = required_env("API_HASH")
BOT_TOKEN = required_env("BOT_TOKEN")
SESSION_STRING = required_env("SESSION_STRING")

PORT = int(os.getenv("PORT", "10000"))


# =========================================================
# TELEGRAM CLIENTS
# =========================================================

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

assistant = Client(
    "music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# =========================================================
# VOICE CALL
# =========================================================

voice = PyTgCalls(assistant)


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

        if "entries" in info:

            entries = info.get("entries") or []

            if not entries:
                raise RuntimeError("Song not found.")

            info = entries[0]

        url = info.get("url")

        if not url:
            raise RuntimeError(
                "Could not get audio stream."
            )

        return {
            "title": info.get(
                "title",
                "Unknown"
            ),
            "url": url,
        }


# =========================================================
# PLAY NEXT
# =========================================================

async def play_next(chat_id):

    queue = queues.get(chat_id, [])

    if not queue:

        now_playing.pop(
            chat_id,
            None
        )

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
            (
                "🎵 **Now Playing**\n\n"
                f"🎶 {song['title']}"
            ),
        )

    except Exception as error:

        now_playing.pop(
            chat_id,
            None
        )

        print(
            f"Playback error in {chat_id}: {error}"
        )

        try:
            await bot.send_message(
                chat_id,
                (
                    "❌ **Could not play the song.**\n\n"
                    f"`{error}`"
                ),
            )
        except Exception:
            pass

        await play_next(chat_id)


# =========================================================
# SONG FINISHED
# =========================================================

@voice.on_update(
    call_filters.stream_end()
)
async def stream_finished(
    _,
    update: StreamEnded
):

    chat_id = update.chat_id

    now_playing.pop(
        chat_id,
        None
    )

    await asyncio.sleep(1)

    await play_next(chat_id)


# =========================================================
# /START
# =========================================================

@bot.on_message(
    filters.command("start")
)
async def start_command(
    _,
    message: Message
):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "Use `/play <song>` to play music "
        "in the group voice chat.\n\n"
        "Commands:\n"
        "▶️ `/play <song>`\n"
        "⏭ `/skip`\n"
        "⏹ `/stop`\n"
        "📜 `/queue`\n"
        "❓ `/help`"
    )


# =========================================================
# /HELP
# =========================================================

@bot.on_message(
    filters.command("help")
)
async def help_command(
    _,
    message: Message
):

    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "▶️ `/play <song>` — Play music\n"
        "⏭ `/skip` — Skip song\n"
        "⏹ `/stop` — Stop music\n"
        "📜 `/queue` — Show queue\n"
        "❓ `/help` — Show commands"
    )


# =========================================================
# /PLAY
# =========================================================

@bot.on_message(
    filters.command("play")
)
async def play_command(
    _,
    message: Message
):

    if len(message.command) < 2:

        await message.reply_text(
            "❌ **Usage:**\n"
            "`/play song name`"
        )

        return

    query = " ".join(
        message.command[1:]
    )

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
            (
                "❌ **Search failed.**\n\n"
                f"`{error}`"
            )
        )

        return

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append(song)

    if chat_id not in now_playing:

        await status.edit_text(
            (
                "🎵 **Starting:**\n"
                f"{song['title']}"
            )
        )

        await play_next(chat_id)

    else:

        position = len(
            queues[chat_id]
        )

        await status.edit_text(
            (
                "➕ **Added to queue**\n\n"
                f"🎶 {song['title']}\n"
                f"📌 Position: {position}"
            )
        )


# =========================================================
# /SKIP
# =========================================================

@bot.on_message(
    filters.command("skip")
)
async def skip_command(
    _,
    message: Message
):

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

    now_playing.pop(
        chat_id,
        None
    )

    await message.reply_text(
        "⏭ **Skipped!**"
    )

    await asyncio.sleep(1)

    await play_next(chat_id)


# =========================================================
# /STOP
# =========================================================

@bot.on_message(
    filters.command("stop")
)
async def stop_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    queues.pop(
        chat_id,
        None
    )

    now_playing.pop(
        chat_id,
        None
    )

    try:
        await voice.leave_call(chat_id)
    except Exception:
        pass

    await message.reply_text(
        "⏹ **Music stopped.**\n"
        "👋 Left the voice chat."
    )


# =========================================================
# /QUEUE
# =========================================================

@bot.on_message(
    filters.command("queue")
)
async def queue_command(
    _,
    message: Message
):

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

    for number, song in enumerate(
        queue,
        1
    ):

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
# MAIN
# =========================================================

async def main():

    print(
        "🚀 Starting Music Bot...",
        flush=True
    )

    # Start Render HTTP server FIRST
    health_runner = await start_health_server()

    try:

        print(
            "🤖 Starting Telegram bot...",
            flush=True
        )

        await bot.start()

        print(
            "✅ Telegram bot started.",
            flush=True
        )

        print(
            "👤 Starting assistant account...",
            flush=True
        )

        await assistant.start()

        print(
            "✅ Assistant account started.",
            flush=True
        )

        print(
            "🎧 Starting voice engine...",
            flush=True
        )

        await voice.start()

        print(
            "✅ Voice engine started.",
            flush=True
        )

        print(
            "================================",
            flush=True
        )

        print(
            "🎵 MUSIC BOT IS READY",
            flush=True
        )

        print(
            "================================",
            flush=True
        )

        await asyncio.Event().wait()

    except Exception as error:

        print(
            "❌ BOT STARTUP ERROR",
            flush=True
        )

        print(
            str(error),
            flush=True
        )

        traceback.print_exc()

        raise

    finally:

        print(
            "🛑 Shutting down...",
            flush=True
        )

        try:
            await voice.stop()
        except Exception:
            pass

        try:
            await assistant.stop()
        except Exception:
            pass

        try:
            await bot.stop()
        except Exception:
            pass

        try:
            await health_runner.cleanup()
        except Exception:
            pass


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped.",
            flush=True
)
