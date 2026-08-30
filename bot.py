import os
import asyncio
import logging
import tempfile

# ============================================================
# PYROGRAM / PYTGCalls COMPATIBILITY
# ============================================================

import pyrogram.errors

# PyTgCalls 2.2.x expects these older names.
# Pyrogram 2.0.106 uses slightly different names.

if not hasattr(pyrogram.errors, "GroupcallForbidden"):
    pyrogram.errors.GroupcallForbidden = (
        getattr(
            pyrogram.errors,
            "GroupCallForbidden",
            Exception
        )
    )

if not hasattr(pyrogram.errors, "GroupcallInvalid"):
    pyrogram.errors.GroupcallInvalid = (
        getattr(
            pyrogram.errors,
            "GroupCallInvalid",
            Exception
        )
    )


# ============================================================
# IMPORTS
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import StreamEnded

import yt_dlp

from aiohttp import web


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]

PORT = int(
    os.environ.get(
        "PORT",
        "10000"
    )
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger(
    "TelegramMusicBot"
)


# ============================================================
# BOT CLIENT
# ============================================================

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ============================================================
# ASSISTANT CLIENT
# ============================================================

assistant = Client(
    "music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)


# ============================================================
# VOICE CLIENT
# ============================================================

voice = PyTgCalls(
    assistant
)


# ============================================================
# MUSIC QUEUES
# ============================================================

queues = {}

current_song = {}


def get_queue(chat_id):

    if chat_id not in queues:
        queues[chat_id] = []

    return queues[chat_id]


# ============================================================
# YOUTUBE SEARCH
# ============================================================

async def search_youtube(query):

    if (
        query.startswith("http://")
        or query.startswith("https://")
    ):
        return query, query

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch1"
    }

    def search():

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                "ytsearch1:" + query,
                download=False
            )

            if not info:
                return None

            entries = info.get(
                "entries"
            )

            if not entries:
                return None

            result = entries[0]

            title = result.get(
                "title",
                query
            )

            url = (
                result.get(
                    "webpage_url"
                )
                or result.get(
                    "url"
                )
            )

            if not url:
                return None

            return title, url

    return await asyncio.to_thread(
        search
    )


# ============================================================
# DOWNLOAD AUDIO
# ============================================================

async def download_audio(url):

    folder = tempfile.mkdtemp(
        prefix="musicbot_"
    )

    output = os.path.join(
        folder,
        "audio.%(ext)s"
    )

    options = {
        "format": "bestaudio/best",
        "outtmpl": output,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }
        ]
    }

    def download():

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                info
            )

            base = os.path.splitext(
                filename
            )[0]

            mp3 = base + ".mp3"

            if os.path.exists(mp3):
                return mp3

            return filename

    return await asyncio.to_thread(
        download
    )


# ============================================================
# PLAY NEXT
# ============================================================

async def play_next(chat_id):

    queue = get_queue(
        chat_id
    )

    if not queue:

        current_song.pop(
            chat_id,
            None
        )

        return

    song = queue.pop(
        0
    )

    current_song[
        chat_id
    ] = song

    try:

        log.info(
            "Downloading: %s",
            song["title"]
        )

        audio = await download_audio(
            song["url"]
        )

        log.info(
            "Playing: %s",
            song["title"]
        )

        stream = MediaStream(
            audio
        )

        await voice.play(
            chat_id,
            stream
        )

    except Exception as e:

        log.exception(
            "Playback error"
        )

        current_song.pop(
            chat_id,
            None
        )

        await play_next(
            chat_id
        )


# ============================================================
# VOICE CHAT END
# ============================================================

@voice.on_update()
async def voice_update(
    _,
    update
):

    try:

        if isinstance(
            update,
            StreamEnded
        ):

            chat_id = update.chat_id

            current_song.pop(
                chat_id,
                None
            )

            await play_next(
                chat_id
            )

    except Exception:

        log.exception(
            "Voice update error"
        )


# ============================================================
# /START
# ============================================================

@bot.on_message(
    filters.command("start")
)
async def start_command(
    _,
    message: Message
):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "Use `/play song name` to play music.\n\n"
        "Commands:\n"
        "▶️ /play\n"
        "⏸ /pause\n"
        "▶️ /resume\n"
        "⏭ /skip\n"
        "⏹ /stop\n"
        "📜 /queue\n"
        "🚪 /leave\n"
        "ℹ️ /help"
    )


# ============================================================
# /HELP
# ============================================================

@bot.on_message(
    filters.command("help")
)
async def help_command(
    _,
    message: Message
):

    await message.reply_text(
        "🎵 **Music Commands**\n\n"
        "▶️ `/play song` — Play music\n"
        "⏸ `/pause` — Pause\n"
        "▶️ `/resume` — Resume\n"
        "⏭ `/skip` — Skip\n"
        "⏹ `/stop` — Stop\n"
        "📜 `/queue` — Queue\n"
        "🚪 `/leave` — Leave VC"
    )


# ============================================================
# /PLAY
# ============================================================

@bot.on_message(
    filters.command("play")
)
async def play_command(
    _,
    message: Message
):

    if len(
        message.command
    ) < 2:

        await message.reply_text(
            "❌ Example:\n"
            "`/play Alan Walker Faded`"
        )

        return

    query = " ".join(
        message.command[1:]
    )

    status = await message.reply_text(
        "🔎 Searching..."
    )

    try:

        result = await search_youtube(
            query
        )

        if not result:

            await status.edit_text(
                "❌ Song not found."
            )

            return

        title, url = result

        chat_id = message.chat.id

        queue = get_queue(
            chat_id
        )

        song = {
            "title": title,
            "url": url
        }

        queue.append(
            song
        )

        if chat_id in current_song:

            await status.edit_text(
                "✅ **Added to queue**\n\n"
                f"🎵 {title}\n"
                f"📌 Position: {len(queue)}"
            )

        else:

            await status.edit_text(
                f"🎵 **Playing:** {title}"
            )

            await play_next(
                chat_id
            )

    except Exception as e:

        log.exception(
            "Play error"
        )

        await status.edit_text(
            "❌ Error:\n"
            f"`{e}`"
        )


# ============================================================
# /PAUSE
# ============================================================

@bot.on_message(
    filters.command("pause")
)
async def pause_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    try:

        await voice.pause(
            chat_id
        )

        await message.reply_text(
            "⏸ Paused."
        )

    except Exception as e:

        await message.reply_text(
            f"❌ {e}"
        )


# ============================================================
# /RESUME
# ============================================================

@bot.on_message(
    filters.command("resume")
)
async def resume_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    try:

        await voice.resume(
            chat_id
        )

        await message.reply_text(
            "▶️ Resumed."
        )

    except Exception as e:

        await message.reply_text(
            f"❌ {e}"
        )


# ============================================================
# /SKIP
# ============================================================

@bot.on_message(
    filters.command("skip")
)
async def skip_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    try:

        await voice.leave_call(
            chat_id
        )

        current_song.pop(
            chat_id,
            None
        )

        await message.reply_text(
            "⏭ Skipped."
        )

        await asyncio.sleep(
            1
        )

        await play_next(
            chat_id
        )

    except Exception as e:

        await message.reply_text(
            f"❌ {e}"
        )


# ============================================================
# /STOP
# ============================================================

@bot.on_message(
    filters.command("stop")
)
async def stop_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    get_queue(
        chat_id
    ).clear()

    current_song.pop(
        chat_id,
        None
    )

    try:

        await voice.leave_call(
            chat_id
        )

    except Exception:

        pass

    await message.reply_text(
        "⏹ **Stopped**\n"
        "Queue cleared."
    )


# ============================================================
# /LEAVE
# ============================================================

@bot.on_message(
    filters.command("leave")
)
async def leave_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    get_queue(
        chat_id
    ).clear()

    current_song.pop(
        chat_id,
        None
    )

    try:

        await voice.leave_call(
            chat_id
        )

    except Exception:

        pass

    await message.reply_text(
        "🚪 Left the voice chat."
    )


# ============================================================
# /QUEUE
# ============================================================

@bot.on_message(
    filters.command("queue")
)
async def queue_command(
    _,
    message: Message
):

    chat_id = message.chat.id

    queue = get_queue(
        chat_id
    )

    text = []

    if chat_id in current_song:

        text.append(
            "▶️ **Now Playing**\n"
            + current_song[
                chat_id
            ]["title"]
        )

    if queue:

        text.append(
            "\n📜 **Up Next**"
        )

        for i, song in enumerate(
            queue,
            start=1
        ):

            text.append(
                f"{i}. {song['title']}"
            )

    if not text:

        await message.reply_text(
            "📭 Queue is empty."
        )

        return

    await message.reply_text(
        "\n".join(text)
    )


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

async def health(
    request
):

    return web.Response(
        text="Music Bot is running."
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

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    log.info(
        "Health server running on port %s",
        PORT
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    log.info(
        "🚀 Starting Music Bot..."
    )

    await assistant.start()

    log.info(
        "👤 Assistant started."
    )

    voice.start()

    log.info(
        "🎤 Voice engine started."
    )

    await bot.start()

    log.info(
        "🤖 Bot started."
    )

    await start_health_server()

    log.info(
        "🎵 MUSIC BOT IS READY"
    )

    await asyncio.Event().wait()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        log.info(
            "Bot stopped."
    )
